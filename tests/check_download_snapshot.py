"""Compare downloaded five-column result CSV files with a specified API snapshot.

The new user CSV intentionally omits run IDs. Supply --run-id from the successful
API job. Example: python tests/check_download_snapshot.py --run-id ID result.csv
The check report is saved under .runtime/checks.
"""
import argparse
import csv
import json
from pathlib import Path
import re
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--port", type=int, default=4174)
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{32}", args.run_id):
        parser.error("--run-id must be the 32-character ID returned by the API.")
    root = Path(__file__).resolve().parents[1]
    with urlopen(f"http://127.0.0.1:{args.port}/api/runs/{args.run_id}", timeout=30) as response:
        job = json.load(response)
    assert job["status"] == "succeeded", job
    result = job["result"]
    catalog = json.loads((root / "public/data/chemical-catalog.json").read_text(encoding="utf-8"))
    labels = {row["id"]: row["name"] + (" (BIT)" if row["id"] == "DMSMPAJRVJJAGA-UHFFFAOYSA-N" else "")
              for row in catalog["chemicals"] if row["nt52"]}
    assert len(set(labels.values())) == len(labels), "Download names must be unambiguous."
    actual = {labels[row["chemical"]]: row for row in result["rows"]}
    columns = ["Rank", "Chemical", "WW input (nM)", "BEQ (μg/L Narciclasine-EQ)", "Contribution (%)"]
    checks = []
    for filename in args.files:
        path = Path(filename)
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            assert reader.fieldnames == columns, reader.fieldnames
            rows = list(reader)
        assert rows, f"Empty download: {path.name}"
        assert len({row["Chemical"] for row in rows}) == len(rows), "Duplicate downloaded chemicals."
        for row in rows:
            reference = actual[row["Chemical"]]
            assert int(row["Rank"]) == reference["beqRank"]
            assert float(row["WW input (nM)"]) == reference["ww"]
            assert float(row["BEQ (μg/L Narciclasine-EQ)"]) == reference["beq"]
            assert float(row["Contribution (%)"]) == reference["beqContribution"]
        checks.append({"file": str(path), "runId": result["id"], "rows": len(rows), "status": "passed",
                       "numericComparison": "Exact full-precision values from the supplied API snapshot; only the five user columns."})
    report = {"status": "passed", "checks": checks}
    folder = root / ".runtime/checks"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "download-snapshot.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
