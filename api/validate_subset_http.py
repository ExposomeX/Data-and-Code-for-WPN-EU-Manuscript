"""Manually validate the current API through its existing local CPU worker.

The default replay checks one bundled frozen city; --full-frozen checks all 117.
No historical report is read. Results print to stdout; --output optionally saves
this run's result. This performs several real predictions and can take minutes.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from io import BytesIO
import json
import math
from pathlib import Path
import time
import urllib.error
import urllib.request

from engine import ROOT, PANEL_FILE, WPNEngine, read_csv, sha256, utc_now
from import_excel import XLSX_MEDIA_TYPE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=4174)
    parser.add_argument("--full-frozen", action="store_true")
    parser.add_argument("--max-log10-difference", type=float, default=.005)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    base = f"http://127.0.0.1:{args.port}"
    metadata = WPNEngine()  # Reads CSV metadata only; initialize() is never called.
    checks = []
    began = time.monotonic()

    def request(path, payload=None, raw=None, media_type="application/json", expect=200):
        body = raw if raw is not None else (json.dumps(payload).encode() if payload is not None else None)
        headers = {"Content-Type": media_type} if body is not None else {}
        req = urllib.request.Request(base + path, data=body, headers=headers)
        try:
            response = urllib.request.urlopen(req, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            data = response.read()
            assert response.status == expect, (path, response.status, expect, data[:200])
            assert response.headers.get("Cache-Control") == "no-store"
            return json.loads(data)

    def run(inputs):
        queued = request("/api/runs", {"inputs": inputs}, expect=202)
        tick = time.monotonic()
        while True:
            job = request("/api/runs/" + queued["id"])
            if job["status"] in {"succeeded", "failed"}:
                assert job["status"] == "succeeded", job
                return job["result"]
            assert time.monotonic() - tick < 600, "Prediction took longer than 600 seconds."
            time.sleep(.25)

    def validate_snapshot(result, inputs):
        expected_inputs = metadata.validate_inputs({"inputs": inputs})
        assert set(result) == {"id", "createdAt", "modelVersion", "dataVersion", "inputs", "rows", "totals"}
        assert result["inputs"] == expected_inputs
        assert [row["chemical"] for row in result["rows"]] == [row["chemical"] for row in expected_inputs]
        assert set(result["totals"]) == {"ww", "beq"}
        expected_ww = {row["chemical"]: row["ww"] for row in expected_inputs}
        for row in result["rows"]:
            assert set(row) == {"chemical", "ww", "beq", "beqRank", "beqContribution"}
            assert row["ww"] == expected_ww[row["chemical"]]
            assert math.isfinite(row["beq"]) and row["beq"] > 0
            assert row["beqRank"] == 1 + sum(other["beq"] > row["beq"] for other in result["rows"])
            assert row["beqContribution"] == row["beq"] / result["totals"]["beq"] * 100.
        assert math.isclose(math.fsum(row["beqContribution"] for row in result["rows"]), 100., abs_tol=1e-12)
        for metric in ("ww", "beq"):
            assert math.fsum(row[metric] for row in result["rows"]) == result["totals"][metric]

    health = request("/api/health")
    assert health["status"] == "ready", health
    assert health["modelVersion"] == metadata.model_version, "Restart the local site with the packaged CPU backend before this check."
    identity = request("/__local/status")
    assert Path(identity["projectRoot"]).resolve() == ROOT
    assert Path(identity["serverPath"]).resolve() == ROOT / "api/server.py"
    checks.append("The running local worker belongs to this project and uses the configured CPU model.")
    snapshots = {}
    for count in (1, 10, 52):
        inputs = [{**row, "origin": "example"} for row in reversed(metadata.default_inputs[:count])]
        result = run(inputs)
        validate_snapshot(result, inputs)
        assert len(result["rows"]) == count
        snapshots[count] = result
        print(f"Partial input: {count} submitted, {len(result['rows'])} returned", flush=True)
    checks.append("1, 10 and 52 example-valued inputs return only the submitted chemicals, with subset BEQ ranks and contribution denominators.")
    complete = {row["chemical"]: row for row in snapshots[52]["rows"]}
    subset_difference = max(abs(row["beq"] / complete[row["chemical"]]["beq"] - 1.)
                            for count in (1, 10) for row in snapshots[count]["rows"])
    subset_log_difference = max(abs(math.log10(row["beq"]) - math.log10(complete[row["chemical"]]["beq"]))
                                for count in (1, 10) for row in snapshots[count]["rows"])
    # Compare batch sizes with the previously specified frozen-replay tolerance.
    # Record observed differences without assigning a cause or claiming bitwise equality.
    assert subset_log_difference <= args.max_log10_difference, subset_log_difference
    repeated_one = run(snapshots[1]["inputs"])
    validate_snapshot(repeated_one, snapshots[1]["inputs"])
    repeat_difference = abs(repeated_one["rows"][0]["beq"] / snapshots[1]["rows"][0]["beq"] - 1.)
    assert abs(math.log10(repeated_one["rows"][0]["beq"]) - math.log10(snapshots[1]["rows"][0]["beq"])) <= args.max_log10_difference

    bit = "DMSMPAJRVJJAGA-UHFFFAOYSA-N"
    altered = [{"chemical": bit, "ww": metadata.defaults[bit] * 10, "origin": "user"}]
    edited = run(altered)
    validate_snapshot(edited, altered)
    assert edited["rows"][0]["beq"] != complete[bit]["beq"]
    assert edited["rows"][0]["beqContribution"] == 100.
    checks.append("An edited BIT concentration changes its model BEQ; a single chemical has rank 1 and contribution 100%.")

    invalid = [[], [metadata.default_inputs[0], metadata.default_inputs[0]], [{"chemical": "unknown", "ww": 1}]]
    invalid += [[{"chemical": bit, "ww": value}] for value in (0, -1, None, True, "1", float("nan"), float("inf"))]
    for rows in invalid:
        assert "detail" in request("/api/runs", {"inputs": rows}, expect=422)
    checks.append("Empty, duplicated, unknown and invalid concentrations are rejected.")

    from openpyxl import Workbook
    workbook = Workbook()
    workbook.active.title = "WW concentrations"
    workbook.active.append(["Chemical", "WW input (nM)"])
    workbook.active.append([bit, 12.5])
    workbook.active.append(["Unknown entry", "check"])
    binary = BytesIO()
    workbook.save(binary)
    workbook.close()
    preview = request("/api/import", raw=binary.getvalue(), media_type=XLSX_MEDIA_TYPE)
    assert preview == {"sheet": "WW concentrations", "rows": [["Chemical", "WW input (nM)"], [bit, 12.5], ["Unknown entry", "check"]]}
    assert "detail" in request("/api/import", raw=b"not a workbook", media_type=XLSX_MEDIA_TYPE, expect=422)
    checks.append("XLSX uploads return first-sheet rows for the valid/invalid preview without modifying values.")
    for result in [*snapshots.values(), edited]:
        assert request("/api/runs/" + result["id"])["result"] == result
    checks.append("Earlier result snapshots remain unchanged after later runs, imports and rejected requests.")

    frozen = read_csv(ROOT / PANEL_FILE)
    grouped = defaultdict(list)
    for row in frozen:
        grouped[row["GUB_city_unit"]].append(row)
    cities = sorted(grouped) if args.full_frozen else sorted(grouped)[:1]
    max_log_delta = 0.
    replay_rows = 0
    for index, city in enumerate(cities, 1):
        source = grouped[city]
        inputs = [{"chemical": row["StdInChIKey"], "ww": float(row["ww_concentration_nM"])} for row in source]
        result = run(inputs)
        validate_snapshot(result, inputs)
        reference = {row["StdInChIKey"]: float(row["BEQ (ug/L Narciclasine-EQ)_one_compartment"]) for row in source}
        delta = max(abs(math.log10(row["beq"]) - math.log10(reference[row["chemical"]])) for row in result["rows"])
        max_log_delta = max(max_log_delta, delta)
        replay_rows += len(source)
        print(f"Frozen BEQ replay: city {index}/{len(cities)}, {replay_rows} rows; max log10 difference {max_log_delta:.10g}", flush=True)
    assert max_log_delta <= args.max_log10_difference
    checks.append("Frozen-city WW inputs reproduce the saved A2 BEQ within the stated numerical tolerance.")
    report = {"status": "passed", "generatedAtUTC": utc_now(), "serverPID": identity["pid"],
              "checks": checks, "subsetSizes": [1, 10, 52], "publicColumns": ["chemical", "ww", "beq", "beqRank", "beqContribution"],
              "maximumSubsetVsFullRelativeBEQDifference": subset_difference,
              "maximumSubsetVsFullAbsoluteLog10BEQDifference": subset_log_difference,
              "repeatedSingletonRelativeBEQDifference": repeat_difference,
              "allowedAbsoluteLog10BatchDifference": args.max_log10_difference,
              "frozenReplay": {"cities": len(cities), "rows": replay_rows, "maximumAbsoluteLog10BEQDifference": max_log_delta,
                               "allowedAbsoluteLog10BEQDifference": args.max_log10_difference, "sourceSHA256": sha256(ROOT / PANEL_FILE)},
              "seconds": time.monotonic() - began}
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text, flush=True)


if __name__ == "__main__":
    main()
