"""Prepare the WPN website from frozen A2 tables without running scientific models.

Run with Python 3.10+: python tools/prepare_data.py
Only WPN/public/data, WPN/public/downloads and the WPN data audit report are written.
Upstream manuscripts, scientific code, models and frozen results remain read-only.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAPER_ROOT = ROOT.parent.parent
SOURCE_ROOT = PAPER_ROOT / "【投稿版本】" / "WPN_code"
DATA_DIR = ROOT / "public" / "data"
DOWNLOAD_DIR = ROOT / "public" / "downloads"
VERSIONS = {"manuscript": "2026-10-04 BW", "analysis": "2026-09-25 A2"}
BIT = "DMSMPAJRVJJAGA-UHFFFAOYSA-N"
METRICS = ("WW_nM", "DE_umol_day", "BEQ_ugL")
SOURCES = {
    "cities": "data_raw/preparation/cohort/city_metadata.csv",
    "chemicals": "data_raw/preparation/cohort/chemical_metadata.csv",
    "concentrations": "results/Step2/A2_after_supplement/matrices/concentration_long_final_imputed_nM.csv",
    "ranks": "results/Step4/A2_predictions/chemical_summary_and_ranks_REP52.csv",
    "city_metrics": "results/Step4/A2_predictions/step10a_gub_city_chemical_cb_rep_beq_with_cb_nM.csv",
    "validation_predictions": "results/Step2/A2_after_supplement/imputation/validation_predictions.csv",
    "validation_summary": "results/Step2/A2_after_supplement/imputation/validation_summary.csv",
    "city_totals": "results/Step4/A2_predictions/city_summary_BEQ_ugL.csv",
}
DOWNLOADS = {
    "cities": ("cities-a2.csv", "Urban-area metadata", "117 urban areas with country and centroid coordinates.", "coordinates in decimal degrees; area in km²"),
    "chemicals": ("chemicals-a2.csv", "Chemical metadata", "Identifiers and names for the 663 reconstructed chemicals.", "identifiers / names"),
    "concentrations": ("concentrations-a2.csv", "Observed and reconstructed wastewater concentrations", "Complete 117 × 663 A2 matrix in long format; observed values remain identifiable.", "nM"),
    "city_metrics": ("city-metrics-nt52-a2.csv", "WW, exposure and BEQ for the 52 target chemicals", "Frozen city-by-chemical estimates, parameter values, original provenance fields and observed/reconstructed flags.", "WW: nM; DE: μmol/day; BEQ: μg/L narciclasine-EQ"),
    "ranks": ("chemical-ranks-nt52-a2.csv", "Chemical priorities and summary statistics", "Original six-metric table, including the three WW/DE/BEQ metrics displayed by the website. Mean and median ranks remain distinct.", "metric-specific; contribution in %"),
    "validation_predictions": ("imputation-validation-predictions-a2.csv", "Imputation validation predictions", "10 frozen validation repeats, 1,275 held-out cells per repeat. These are validation results, not uncertainty bounds.", "log10 concentration (nM)"),
    "validation_summary": ("imputation-validation-summary-a2.csv", "Imputation validation summary", "Original validation metrics for repeats 1–10 and the pooled overall row.", "R² / r: dimensionless; RMSE / MAE: log10(nM)"),
    "city_totals": ("city-beq-totals-nt52-a2.csv", "City-level total BEQ", "Frozen totals across the fixed panel of 52 target chemicals for each of 117 urban areas.", "μg/L narciclasine-EQ"),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def numeric(value: str | int | float | None) -> float | None:
    if value is None or str(value).strip().lower() in {"", "nan", "na", "null", "none"}:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def required_number(value: str, field: str) -> float:
    result = numeric(value)
    if result is None:
        raise ValueError(f"Missing/non-finite required value in {field}: {value!r}")
    return result


def boolean(value: str) -> bool:
    if value.lower() in {"true", "1"}:
        return True
    if value.lower() in {"false", "0"}:
        return False
    raise ValueError(f"Unrecognized source boolean: {value!r}")


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def write_json(path: Path, value: object) -> None:
    # Python emits enough digits for an exact binary64 round trip; no display rounding.
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n", encoding="utf-8")


def close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-20)


def main() -> None:
    tables = {key: read_csv(SOURCE_ROOT / relative) for key, relative in SOURCES.items()}
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, details: object) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})
        if not passed:
            raise AssertionError(f"Data acceptance failed: {name}: {details}")

    cities = [{"id": row["GUB_city_unit"], "name": row["cities"], "country": row["countries"],
               "lon": required_number(row["GUB_centroid_lon"], "longitude"),
               "lat": required_number(row["GUB_centroid_lat"], "latitude")} for row in tables["cities"]]
    city_ids = {row["id"] for row in cities}
    category_by_id: dict[str, str] = {}
    panel_names: dict[str, str] = {}
    for row in tables["city_metrics"]:
        chemical = row["StdInChIKey"]
        if chemical in category_by_id and category_by_id[chemical] != row["Category_II"]:
            raise ValueError(f"Inconsistent chemical classification: {chemical}")
        category_by_id[chemical] = row["Category_II"]
        panel_names[chemical] = row["Name"]
    target_ids = set(category_by_id)
    chemicals = [{"id": row["StdInChIKey"],
                  "name": panel_names.get(row["StdInChIKey"], row["compound_names"]),
                  "category": category_by_id.get(row["StdInChIKey"], ""),
                  "nt52": row["StdInChIKey"] in target_ids} for row in tables["chemicals"]]
    chemical_ids = {row["id"] for row in chemicals}
    concentrations = [{"city": row["GUB_city_unit"], "chemical": row["StdInChIKey"],
                       "observed": numeric(row["observed_concentration_nM"]),
                       "value": numeric(row["final_imputed_concentration_nM"]),
                       "deterministic": numeric(row["deterministic_concentration_nM"]),
                       "isObserved": boolean(row["is_observed"])} for row in tables["concentrations"]]
    concentration_index = {(row["city"], row["chemical"]): row for row in concentrations}
    ranks = [{"chemical": row["StdInChIKey"], "metric": row["metric"],
              "mean": required_number(row["mean"], "mean"), "median": required_number(row["median"], "median"),
              "meanRank": required_number(row["mean_rank"], "mean_rank"),
              "medianRank": required_number(row["median_rank"], "median_rank"),
              "contribution": required_number(row["mean_based_contribution_percent"], "contribution")}
             for row in tables["ranks"] if row["metric"] in METRICS]
    city_metrics = [{"city": row["GUB_city_unit"], "chemical": row["StdInChIKey"],
                     "ww": required_number(row["ww_concentration_nM"], "ww"),
                     "de": required_number(row["Predicted_Daily_Exposure (umol/day)_WW_DE_fhlb"], "de"),
                     "beq": required_number(row["BEQ (ug/L Narciclasine-EQ)_one_compartment"], "beq"),
                     "isObserved": boolean(row["is_observed"])} for row in tables["city_metrics"]]
    predictions = [{"repeat": int(row["validation_repeat"]), "city": row["GUB_city_unit"],
                    "chemical": row["Chemical"],
                    "trueLog10": required_number(row["true_log10"], "true_log10"),
                    "predictedLog10": required_number(row["predicted_log10"], "predicted_log10")}
                   for row in tables["validation_predictions"]]
    summary = [{key: (value if key == "validation_repeat" else int(value) if key == "masked_cells" else required_number(value, key))
                for key, value in row.items()} for row in tables["validation_summary"]]
    counts = {"cities": len(cities), "countries": len({row["country"] for row in cities}),
              "chemicals": len(chemicals), "targetChemicals": len(target_ids),
              "concentrations": len(concentrations), "observed": sum(row["isObserved"] for row in concentrations),
              "reconstructed": sum(not row["isObserved"] for row in concentrations)}
    expected = {"cities": 117, "countries": 18, "chemicals": 663, "targetChemicals": 52,
                "concentrations": 77571, "observed": 12746, "reconstructed": 64825}
    check("A2 cohort counts", counts == expected, counts)
    check("Unique city and chemical metadata identifiers", len(city_ids) == 117 and len(chemical_ids) == 663, {"cities": len(city_ids), "chemicals": len(chemical_ids)})
    check("Complete and unique 117 × 663 concentration matrix", len(concentration_index) == 77571 and set(concentration_index) == {(c, k) for c in city_ids for k in chemical_ids}, len(concentration_index))
    check("Observed wastewater values are unchanged", all(row["observed"] == row["value"] for row in concentrations if row["isObserved"]), "Exact binary64 equality for all 12,746 observed entries; no re-estimation.")
    check("Observed/missing flags agree with source-value availability", all(row["isObserved"] == (row["observed"] is not None) for row in concentrations), "Missing observed measurements become JSON null, never zero.")
    check("Final concentrations are finite and positive", all(row["value"] is not None and row["value"] > 0 for row in concentrations), "All 77,571 final values support logarithmic display.")
    panel_keys = {(row["city"], row["chemical"]) for row in city_metrics}
    check("Complete and unique 117 × 52 effect panel", len(city_metrics) == len(panel_keys) == 6084 and panel_keys == {(c, k) for c in city_ids for k in target_ids}, {"rows": len(city_metrics), "uniqueKeys": len(panel_keys)})
    check("Panel WW and observed flags agree with A2 reconstruction", all(close(row["ww"], concentration_index[(row["city"], row["chemical"])]["value"]) and row["isObserved"] == concentration_index[(row["city"], row["chemical"])]["isObserved"] for row in city_metrics), "Linked by GUB_city_unit + StdInChIKey; relative tolerance 1e-10.")
    totals: dict[str, list[float]] = defaultdict(list)
    for row in city_metrics:
        totals[row["city"]].append(row["beq"])
    absolute_differences = [abs(math.fsum(totals[row["GUB_city_unit"]]) - required_number(row["total"], "city total")) for row in tables["city_totals"]]
    check("BEQ city totals match the frozen summary", len(tables["city_totals"]) == 117 and all(int(row["n_chemicals"]) == 52 and close(math.fsum(totals[row["GUB_city_unit"]]), required_number(row["total"], "city total")) for row in tables["city_totals"]), {"cities": len(tables["city_totals"]), "maximumAbsoluteDifference": max(absolute_differences), "unit": "μg/L narciclasine-EQ"})
    check("Three frozen ranking metrics for all 52 chemicals", len(ranks) == 156 and {(row["chemical"], row["metric"]) for row in ranks} == {(k, m) for k in target_ids for m in METRICS}, dict(Counter(row["metric"] for row in ranks)))
    bit_beq = next(row for row in ranks if row["chemical"] == BIT and row["metric"] == "BEQ_ugL")
    bit_ww = next(row for row in ranks if row["chemical"] == BIT and row["metric"] == "WW_nM")
    check("BIT contribution and ranking reproduce the manuscript", round(bit_beq["contribution"], 2) == 92.03 and bit_beq["meanRank"] == 1 and bit_ww["meanRank"] == 23, {"BIT_meanBEQContributionPercent": bit_beq["contribution"], "BIT_meanBEQRank": bit_beq["meanRank"], "BIT_meanWWRank": bit_ww["meanRank"]})
    top = {metric: {row["chemical"] for row in sorted((row for row in ranks if row["metric"] == metric), key=lambda row: row["meanRank"])[:10]} for metric in METRICS}
    check("WW and BEQ mean Top 10 overlap is two chemicals", len(top["WW_nM"] & top["BEQ_ugL"]) == 2, sorted(top["WW_nM"] & top["BEQ_ugL"]))
    check("Ten frozen validation repeats and pooled summary", Counter(row["repeat"] for row in predictions) == Counter({repeat: 1275 for repeat in range(1, 11)}) and len(summary) == 11 and any(row["validation_repeat"] == "overall" and row["masked_cells"] == 12750 for row in summary), {"predictionRows": len(predictions), "summaryRows": len(summary)})
    check("Validation identifiers link to the A2 matrix", all((row["city"], row["chemical"]) in concentration_index for row in predictions), "All held-out cells have valid city and chemical identifiers.")
    check("Concentration units are nM despite legacy matrix labels", {row["concentration_unit"] for row in tables["concentrations"]} == {"nM"}, "matrix_column contains historical [µg/l] text and is never used as the displayed unit.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    sources = []
    files = []
    for key, relative in SOURCES.items():
        source = SOURCE_ROOT / relative
        filename, label, description, unit = DOWNLOADS[key]
        destination = DOWNLOAD_DIR / filename
        source_hash = digest(source)
        shutil.copyfile(source, destination)
        check(f"Download preserves original bytes: {filename}", digest(destination) == source_hash, source_hash)
        source_info = {"key": key, "path": source.relative_to(PAPER_ROOT).as_posix(), "sha256": source_hash, "bytes": source.stat().st_size, "rows": len(tables[key])}
        sources.append(source_info)
        files.append({"name": key, "label": label, "url": f"/downloads/{filename}", "description": description, "rows": len(tables[key]), "unit": unit, "sha256": source_hash})
    for filename in ("Main Text_20261004_BW.docx", "SM_20261004_BW.docx"):
        manuscript = PAPER_ROOT / filename
        sources.append({"key": "manuscript" if filename.startswith("Main") else "supplement", "path": filename, "sha256": digest(manuscript), "bytes": manuscript.stat().st_size})
    payloads = {"cities.json": cities, "chemicals.json": chemicals, "concentrations.json": concentrations,
                "ranks.json": ranks, "city-metrics.json": city_metrics,
                "validation.json": {"predictions": predictions, "summary": summary}}
    for filename, payload in payloads.items():
        write_json(DATA_DIR / filename, payload)
    generated = datetime.now(timezone.utc).isoformat()
    report = {"status": "passed", "generatedAtUTC": generated, "versions": VERSIONS, "counts": counts,
              "additionalCounts": {"cityMetrics": len(city_metrics), "rankRows": len(ranks), "validationPredictions": len(predictions), "validationSummary": len(summary)},
              "checks": checks,
              "policy": "Read frozen source tables only. No model fitting, imputation, inference, sensitivity reruns or upstream edits were performed."}
    write_json(DATA_DIR / "validation-report.json", report)
    dictionary = """# WPN frozen reference data dictionary and provenance

This dictionary describes the frozen study reference tables, not custom model-scenario outputs. Current manuscript prose and figures use the 4 October 2026 BW documents. Numerical reference tables retain the frozen 25 September 2026 A2 analysis. These version labels have different meanings. Downloaded reference CSV files remain byte-for-byte copies of their frozen sources; their SHA-256 hashes are recorded in `/data/manifest.json`.

## Browser reference JSON fields

- `cities.json`: `id` = GUB_city_unit; `name` = cities; `country` = countries; `lon`/`lat` = GUB centroid coordinates in decimal degrees. Join by city ID rather than display name.
- `chemicals.json`: legacy reference metadata; `id` = StdInChIKey; target names use the NT52 table, other names use compound_names; `category` = Category_II for NT52 or an empty string for unsupported classifications. Empty category is not a chemical class. This file is distinct from the richer and audited `chemical-catalog.json`.
- `concentrations.json`: `city` + `chemical` is the unique row key; `observed` = observed_concentration_nM, `value` = final_imputed_concentration_nM, `deterministic` = deterministic_concentration_nM, all in nM. `isObserved` retains the original observation status. Missing observations are null, not zero. Final values retain observations and reconstruct missing combinations.
- `ranks.json`: `chemical` + `metric` is the unique key. Reference views expose WW_nM, DE_umol_day and BEQ_ugL. `mean`/`median` retain the across-117-city summaries; `meanRank`/`medianRank` are distinct rankings. `contribution` is mean_based_contribution_percent even when median ranks are selected; it must not be relabelled as a median contribution. Filtering does not recompute reference ranks.
- `city-metrics.json`: `city` + `chemical` joins 6,084 NT52 rows; `ww` = ww_concentration_nM (nM); `de` = Predicted_Daily_Exposure (umol/day)_WW_DE_fhlb (μmol/day); `beq` = BEQ (ug/L Narciclasine-EQ)_one_compartment (μg/L narciclasine-EQ). `isObserved` describes WW only. DE and BEQ are always model-derived.
- `validation.json.predictions`: `repeat` is 1–10; `city` = GUB_city_unit; `chemical` = Chemical (StdInChIKey); `trueLog10` = true_log10; `predictedLog10` = predicted_log10. Both axes represent log10 concentration in nM. Repeated held-out predictions are not new measurements or propagated uncertainty intervals.
- `validation.json.summary`: source column names remain unchanged. validation_repeat is `1`–`10` or `overall`; masked_cells is an integer and the four performance statistics are numeric frozen values. `overall` is the pooled summary, not another experiment.

## Audited Chemical catalogue

`chemical-catalog.json` documents 663 background chemicals and flags the fixed NT52 panel. Identities are joined by InChIKey; training membership uses an exact DTXSID match to the 472-chemical training list. Missing DTXSID yields `trainingMember: null`, not a claim of non-membership. Category provenance and raw missing-descriptor status remain explicit.

The catalogue rejects displaced upstream identity metadata: some original CAS cells contain ExposomeX IDs and some Formula cells contain alias strings. Correct display identities are taken from independent source fields, with `identityFieldSources` and `identityCorrections` retained. The original frozen CSV files are preserved, including their historical metadata; they have not been silently rewritten. Catalogue structure-audit flags also distinguish exact InChIKey matches from six background structures requiring stereochemical review.

For NT52, `defaultWW` is the median of the 117 final A2 `ww_concentration_nM` values in the actual Step4 input table and exactly matches `ranks.json` WW_nM.median. Non-target background chemicals have no default input. Missing raw fhlb/logSoliquid/logSwliquid values remain null; model calculations use the saved training-set imputer.

## Units and reference summaries

WW is nM. Historical `matrix_column` strings containing `[µg/l]` do not determine the displayed unit. DE is μmol/day; BEQ is μg/L narciclasine-EQ, not target-chemical mass concentration. The reference molecular mass is 307.25 g/mol. The original rank CSV additionally retains CB_uM, CB_ugL and BEQ_umolL.

Reference city totals sum the fixed NT52 panel. The reported BIT share of 92.03% is an across-city mean-based BEQ contribution. Median rankings and mean shares remain separate. A rank of 23 for mean WW does not imply the same median rank.

## Custom model scenarios are separate

The WPN module can request a new calculation using all 52 submitted WW concentrations and the configured local model service. These custom outputs are distinct from the frozen tables documented above. A model output from median WW inputs is not generally the median of 117 city-specific outputs. Reference values must not substitute for an unavailable or failed custom calculation.

For scenario formulas, model operation, service/API use and local startup, consult `README_使用说明.md` and the retained source/model manifests in the project folder. This reference dictionary does not define a new inference endpoint or a new training procedure.

## Reproduction and interpretation

`python tools/prepare_data.py` prepares the frozen reference data only: it copies original CSV bytes, writes browser JSON without display rounding, and verifies keys, units and reference summaries. That preparation script does not run models; this is a statement about data preparation, not a claim that the platform lacks a calculation service. Run `python tools/prepare_catalog.py` afterwards to prepare BW content, the audited catalogue and exact embedded figures, then rebuild the website. The old `_fn` extraction tool is historical.

Missing values are null and JSON has no NaN/Infinity. Browser display rounding must not alter downloaded raw values. Model-derived priorities guide screening research rather than precise individual dose or city-level disease risk. Source-specific attribution and rights continue to apply; local copies and calculations do not assign a new licence.
"""
    (DOWNLOAD_DIR / "data-dictionary.md").write_text(dictionary, encoding="utf-8")
    files.append({"name": "dictionary", "label": "Frozen reference data dictionary", "url": "/downloads/data-dictionary.md", "description": "Reference fields, units, identity corrections and distinction from custom model scenarios.", "rows": None, "unit": "documentation", "sha256": digest(DOWNLOAD_DIR / "data-dictionary.md")})
    manifest = {"counts": counts, "versions": VERSIONS, "files": files,
                "generatedAtUTC": generated, "provenance": {"sources": sources, "generatedFiles": [{"name": filename, "sha256": digest(DATA_DIR / filename), "bytes": (DATA_DIR / filename).stat().st_size} for filename in payloads], "preparationScript": "tools/prepare_data.py", "preparationScriptSHA256": digest(Path(__file__))},
                "validation": {"status": "passed", "reportUrl": "/data/validation-report.json", "checksPassed": len(checks), "bitMeanBEQContributionPercent": bit_beq["contribution"], "maximumCityBEQAbsoluteDifference": max(absolute_differences)},
                "defaults": {"chemicalPanel": "NT52", "rankMetric": "BEQ_ugL", "rankStatistic": "mean", "validationScale": "log10(nM)"}}
    write_json(DATA_DIR / "manifest.json", manifest)
    lines = ["# WPN 数据核验报告", "", "状态：全部通过。", "", f"生成时间（UTC）：{generated}", "", "论文文字与图片版本：2026-10-04 `BW`；数值分析版本：2026-09-25 A2。", "", "本次只转换、复制及核对冻结数据，没有训练模型、重新插补、预测或修改上游材料。", "", "| 项目 | 数量 |", "|---|---:|"]
    lines += [f"| {key} | {value} |" for key, value in {**counts, **report["additionalCounts"]}.items()]
    lines += ["", f"BIT的mean BEQ贡献为 **{bit_beq['contribution']:.14f}%**（页面可显示92.03%）；BEQ mean rank为1，WW mean rank为23。", f"117座城市BEQ总量核对的最大绝对差为 `{max(absolute_differences):.17g}` μg/L narciclasine-EQ，仅为浮点求和差异。", "", "## 核验记录", ""]
    lines += [f"- 通过：{entry['name']}。" for entry in checks]
    lines += ["", "字段说明：`public/downloads/data-dictionary.md`。机器可读报告：`public/data/validation-report.json`。源文件及前端JSON的SHA-256记录：`public/data/manifest.json`。", "", "所有CSV下载文件保持原始字节；前端JSON保留标准双精度数值精度，缺测值用null，不输出NaN或Infinity。", ""]
    (ROOT / "数据核验报告.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status": "passed", "counts": counts, "additionalCounts": report["additionalCounts"], "checks": len(checks), "bitContribution": bit_beq["contribution"], "maximumBEQDifference": max(absolute_differences)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
