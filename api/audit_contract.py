"""Audit packaged identifiers, parameters and frozen data without model inference.

Prints a fresh JSON result; --output optionally saves it. No old report is needed.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from engine import ROOT, PANEL_FILE, WPNEngine, read_csv, sha256, utc_now


def numeric(value):
    if value in (None, "", "nan", "NaN"):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def audit_numeric_contract(engine):
    catalog_path = ROOT / "public/data/chemical-catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    rows = [r for r in catalog["chemicals"] if r["nt52"]]
    by_key = {row["id"]: row for row in rows}
    assert len(rows) == len(by_key) == 52 and set(by_key) == set(engine.defaults)
    defaults_match = all(by_key[key]["defaultWW"] == engine.defaults[key] for key in by_key)
    mapping = {"fhlb": "fhlb_ifsqsar", "logSoliquid": "logSoliquid_ifsqsar", "logSwliquid": "logSwliquid_ifsqsar",
               "halfLifeHours": "t0.5_adme", "logVDss": "logVDss_adme"}
    mismatches = []
    max_parameter_difference = 0.
    for key, row in by_key.items():
        for public, frozen in mapping.items():
            left, right = numeric(row[public]), numeric(engine.parameters[key][frozen])
            if left is None or right is None:
                if left != right:
                    mismatches.append({"chemical": key, "field": public, "catalog": left, "engine": right})
            else:
                max_parameter_difference = max(max_parameter_difference, abs(left - right))
                if not math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12):
                    mismatches.append({"chemical": key, "field": public, "catalog": left, "engine": right})
        if not math.isclose(row["rep"], engine.rep[key], rel_tol=1e-12, abs_tol=1e-12):
            mismatches.append({"chemical": key, "field": "rep", "catalog": row["rep"], "engine": engine.rep[key]})
    cb_errors, beq_errors = [], []
    frozen_mismatches = []
    frozen = read_csv(ROOT / PANEL_FILE)
    for row in frozen:
        key = row["StdInChIKey"]
        for field in mapping.values():
            left, right = numeric(row[field]), numeric(engine.parameters[key][field])
            if left is None or right is None:
                same = left == right
            else:
                same = math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)
            if not same:
                frozen_mismatches.append({"chemical": key, "field": field})
        if not math.isclose(float(row["REP"]), engine.rep[key], rel_tol=1e-12, abs_tol=1e-12):
            frozen_mismatches.append({"chemical": key, "field": "REP"})
        parameter = engine.parameters[key]
        de = float(row["Predicted_Daily_Exposure (umol/day)_WW_DE_fhlb"])
        cb = (de / 70.) * (float(parameter["t0.5_adme"]) / 24.) / (10. ** float(parameter["logVDss_adme"]) * math.log(2.))
        beq = cb * engine.rep[key] * 307.25
        cb_errors.append(abs(cb / float(row["Predicted_CB (umol/L)_one_compartment"]) - 1.))
        beq_errors.append(abs(beq / float(row["BEQ (ug/L Narciclasine-EQ)_one_compartment"]) - 1.))
    result = {"auditedAtUTC": utc_now(), "joinKey": "StdInChIKey / catalog.id; CAS, formula and display names are not model inputs",
              "catalogSHA256": sha256(catalog_path), "catalogNT52Rows": len(rows), "catalogDefaultsExactlyMatch": defaults_match,
              "catalogParameterMismatches": mismatches, "catalogMaximumParameterAbsoluteDifference": max_parameter_difference,
              "frozenParameterMismatches": frozen_mismatches, "frozenRows": len(frozen),
              "maximumRelativeCbDifference": max(cb_errors), "maximumRelativeBEQDifference": max(beq_errors),
              "formulaRelativeTolerance": 1e-12}
    engine.verify_artifacts()
    paths = [ROOT / PANEL_FILE, engine.package_root / "data/chemicals.json", engine.package_root / "data/parameters.csv"]
    paths += [engine.model_dir / name for name in ("model.joblib", "imputer.joblib", "scaler.joblib", "feature_columns.csv", "feature_preprocessing.csv", "manifest.json", engine.checkpoint.name)]
    result["sourceFiles"] = [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)} for path in paths]
    result["passed"] = defaults_match and not mismatches and not frozen_mismatches and max(cb_errors + beq_errors) <= 1e-12
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional path for this new audit result.")
    args = parser.parse_args()
    engine = WPNEngine()
    audit = audit_numeric_contract(engine)
    text = json.dumps(audit, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
