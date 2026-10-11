# WPN frozen reference data dictionary and provenance

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
