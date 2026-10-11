"""Manually check real CPU inference against the bundled frozen A2 data.

This loads a separate CPU model. The default replays one city and 1/10/52-input
examples; --full-frozen replays all cities and can take substantial time.
No training or old validation report is required. Results print to stdout;
--output optionally saves this run's result.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import time

from engine import ROOT, PANEL_FILE, WPNEngine, read_csv, sha256, utc_now
from audit_contract import audit_numeric_contract


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-frozen", action="store_true")
    parser.add_argument("--max-log10-difference", type=float, default=.005,
                        help="Numerical replay tolerance, not a scientific uncertainty interval.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    began = time.monotonic()
    engine = WPNEngine()
    audit = audit_numeric_contract(engine)
    assert audit["passed"], audit
    frozen_path = ROOT / PANEL_FILE
    frozen_hash = sha256(frozen_path)
    print("Loading the packaged original fitted model on CPU...", flush=True)
    engine.initialize()

    def forbid_fit(*unused, **kwargs):
        raise RuntimeError("Validation must not train the model.")

    engine.estimator.fit = forbid_fit
    grouped = defaultdict(list)
    for row in read_csv(frozen_path):
        grouped[row["GUB_city_unit"]].append(row)
    cities = sorted(grouped) if args.full_frozen else sorted(grouped)[:1]
    maximum_log_delta = 0.
    replay_rows = 0
    for city in cities:
        source = grouped[city]
        inputs = [{"chemical": row["StdInChIKey"], "ww": float(row["ww_concentration_nM"])} for row in source]
        result = engine.run("frozen-" + city, inputs)
        reference = {row["StdInChIKey"]: float(row["BEQ (ug/L Narciclasine-EQ)_one_compartment"]) for row in source}
        delta = max(abs(math.log10(row["beq"]) - math.log10(reference[row["chemical"]])) for row in result["rows"])
        maximum_log_delta = max(maximum_log_delta, delta)
        replay_rows += len(source)
        print(f"Frozen replay: {city}; max absolute log10 BEQ difference {delta:.8g}", flush=True)
    assert maximum_log_delta <= args.max_log10_difference, maximum_log_delta

    scenarios = []
    for count in (1, 10, 52):
        inputs = [{**row, "origin": "example"} for row in engine.default_inputs[:count]]
        result = engine.run(f"subset-{count}", inputs)
        assert len(result["rows"]) == count
        assert result["inputs"] == inputs
        assert math.isclose(math.fsum(row["beqContribution"] for row in result["rows"]), 100., abs_tol=1e-12)
        for row in result["rows"]:
            assert row["beqRank"] == 1 + sum(other["beq"] > row["beq"] for other in result["rows"])
            assert set(row) == {"chemical", "ww", "beq", "beqRank", "beqContribution"}
        scenarios.append({"submitted": count, "returned": len(result["rows"]), "totals": result["totals"]})
    assert sha256(frozen_path) == frozen_hash
    engine.verify_artifacts()
    report = {"status": "passed", "generatedAtUTC": utc_now(), "runtime": engine.runtime,
              "modelVersion": engine.model_version, "dataVersion": engine.data_version,
              "parameterAudit": audit, "subsets": scenarios,
              "frozenReplay": {"cities": len(cities), "rows": replay_rows, "sourceSHA256": frozen_hash,
                               "maximumAbsoluteLog10BEQDifference": maximum_log_delta,
                               "allowedAbsoluteLog10BEQDifference": args.max_log10_difference},
              "seconds": time.monotonic() - began}
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
