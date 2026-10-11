"""Build the BW manuscript content, exact DOCX figures and chemical catalogue.

Uses Python's standard library only. Reads the manuscripts and frozen research
tables without fitting or running a model. Output ownership is limited to
src/content/{paper,content-provenance,catalog-provenance,catalog-synonyms-provenance}.json,
public/data/chemical-catalog.json and public/figures/*.

--synonyms-only updates only the catalogue's synonyms fields and their separate
audit JSON. It never rebuilds manuscript content, figures or model input values.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import posixpath
import re
import statistics
import struct
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent.parent
CODE = WORKSPACE / "【投稿版本】" / "WPN_code"
TABLES = WORKSPACE / "Data_and_Table" / "Table_S_2026.09.25"
MAIN = WORKSPACE / "Main Text_20261004_BW.docx"
SM = WORKSPACE / "SM_20261004_BW.docx"
VERSION = "2026-10-08-BW-A2"
SOURCES = {
    "cohort": CODE / "data_raw/preparation/cohort/chemical_metadata.csv",
    "identity52": CODE / "data_raw/preparation/REP_52_identity.csv",
    "parameters": CODE / "data_raw/models/chemical_parameters.csv",
    "identityMaster": CODE / "data_raw/models/chemical_mass.csv",
    "massAudit": CODE / "data_raw/preparation/matrices/mass_mapping_audit.csv",
    "coverage": CODE / "data_raw/preparation/cohort/correlation_support_eligibility_audit.csv",
    "cityMetrics": CODE / "results/Step4/A2_predictions/step10a_gub_city_chemical_cb_rep_beq_with_cb_nM.csv",
    "ranks": CODE / "results/Step4/A2_predictions/chemical_summary_and_ranks_REP52.csv",
    "concentrations": CODE / "results/Step2/A2_after_supplement/matrices/concentration_long_final_imputed_nM.csv",
    "norman": CODE / "data_raw/figures/selection/NORMAN_inventory.xlsx",
    "literature": CODE / "results/Step5/frozen/tables/Table S2. Literature-derived candidate chemicals.xlsx",
    "literature355": WORKSPACE / "Data_and_Table/Neurotoxic_chemical_Literature.xlsx",
    "rep": CODE / "data_raw/figures/selection/Science_REP.xlsx",
    "training": TABLES / "Table S14. Chemical-level WW-DE model training data for 472 chemicals.xlsx",
    "useSource": CODE / "data_raw/fao/chemical_use_source_classification.csv",
}
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_record(path):
    data = path.read_bytes()
    return {"path": str(path.relative_to(WORKSPACE)), "bytes": len(data), "sha256": sha(data)}


def number(value):
    if value is None or str(value).strip().lower() in {"", "nan", "none", "na"}:
        return None
    try:
        value = float(value)
    except (ValueError, TypeError):
        return None
    return value if math.isfinite(value) else None


def clean(value):
    return str(value).strip() if value is not None and str(value).strip() else None


def valid_cas(value):
    value = (clean(value) or "").lstrip("^")
    if not re.fullmatch(r"\d{2,7}-\d{2}-\d", value):
        return None
    digits = value.replace("-", "")
    return value if sum((i + 1) * int(x) for i, x in enumerate(reversed(digits[:-1]))) % 10 == int(digits[-1]) else None


def valid_formula(value):
    value = clean(value)
    # Only retain explicit formula cells; never infer a formula from aliases.
    return value if value and re.fullmatch(r"(?:[A-Z][a-z]?\d*)+(?:[+-]\d*)?", value) else None


def valid_dtxsid(value):
    value = clean(value)
    return value if value and re.fullmatch(r"DTXSID\d+", value) else None


def choose_valid(candidates, validator=clean):
    for source, raw in candidates:
        value = validator(raw)
        if value is not None:
            return value, source, raw
    return None, None, None


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def extract_synonyms(identity, display_name):
    """Retain name tokens from one exact-key local identity record.

    The source Synonyms cell is a mixed caret-delimited export, not a clean list
    of names. Preserve retained spellings verbatim after trimming; do not split
    IUPAC punctuation, infer names or join records by a similar name/CAS number.
    """
    if not clean(identity.get("Synonyms")):
        return [], []
    known_structures = {clean(identity.get(k)) for k in [
        "SMILES", "SMILES_EPA_Dashboard", "SMILES_from_Inchikey_SMILES",
        "summary_smiles_matched",
    ]} - {None}
    known_identifiers = {clean(identity.get(k)) for k in [
        "DTXSID", "CAS", "EX_ID", "Formula", "StdInChIKey",
        "Average_mass_g_mol", "Monoisotopic_mass",
    ]} - {None}
    database_code = re.compile(
        r"^(?:DTX(?:SID|CID)|EX:|NOCAS[_ :]|(?:S?CHEMBL|CHEBI|MFCD|NCGC|MLS|SMR|"
        r"AKOS|ACMC|CCRIS|HSDB|DSSTox|EINECS|BRN|NSC|NCI|PubChem|UNII|GTPL|"
        r"ZINC|CPD|BCP|CHC|BDBM|starbld|Spectrum|SpecPlus|DivK\d|SPBio|Oprea\d|FEMA)(?:\b|[_ :.-]|\d)|"
        r"(?:DB|PD|AB|AC|FT|HY|J|L|Q|Z)[- ]?\d{4,})", re.I)
    smiles_syntax = re.compile(r"(?:Br|Cl|Si|Se|Na|Li|Mg|Ca|Zn|[BCNOHPSFIbcnops0-9@+\-=#%\[\]().\\/])+")
    aliases, rejected = [], []
    seen = {(clean(display_name) or "").casefold()}
    for index, raw in enumerate((identity.get("Synonyms") or "").split("^"), start=1):
        token = raw.strip()
        reason = None
        if not token or token.casefold() in {"nan", "na", "n/a", "none", "null", "unknown"}:
            reason = "empty_or_placeholder"
        elif token.casefold() in seen:
            reason = "display_name_or_case_insensitive_duplicate"
        elif token in known_identifiers:
            reason = "source_identifier_formula_or_mass"
        elif token in known_structures:
            reason = "source_structure_string"
        elif re.search(r"(?<!\d)\d{2,7}-\d{2}-\d(?!\d)", token):
            reason = "cas_number_or_mixed_name_identifier_cell"
        elif re.search(r"[A-Z]{14}-[A-Z]{10}-[A-Z]", token) or token.startswith("InChI="):
            reason = "inchi_identifier"
        elif database_code.search(token):
            reason = "database_or_catalogue_identifier"
        elif re.fullmatch(r"[A-Z0-9]{10}", token) and re.search(r"\d", token):
            reason = "unii_shaped_identifier"
        elif re.fullmatch(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", token):
            reason = "numeric_value"
        elif re.fullmatch(r"(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\d{4}", token):
            reason = "date_shaped_label"
        elif len(token) > 12 and smiles_syntax.fullmatch(token):
            reason = "structure_syntax"
        elif re.search(r"analytical standard|PESTANAL|,\s*\d+\s*(?:GM|MG|ML)\b|,\s*NEAT\b", token, re.I):
            reason = "commercial_product_description"
        if reason:
            rejected.append({"sourceToken": index, "value": token, "reason": reason})
        else:
            aliases.append(token)
            seen.add(token.casefold())
    return aliases, rejected


def catalog_without_synonyms(catalog):
    return {**catalog, "chemicals": [{k: v for k, v in c.items() if k != "synonyms"} for c in catalog["chemicals"]]}


def enrich_catalog_synonyms(catalog):
    """Add only string[] synonyms, returning a separate reproducible audit."""
    source_rows = csv_rows(SOURCES["identityMaster"])
    by_key = {r["StdInChIKey"]: (i, r) for i, r in enumerate(source_rows, start=1)}
    assert len(by_key) == len(source_rows), "Duplicate identity-master InChIKeys require review."
    before = json.dumps(catalog_without_synonyms(catalog), ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
    records = []
    for chemical in catalog["chemicals"]:
        source_record_number, identity = by_key.get(chemical["id"], (None, {}))
        aliases, rejected = extract_synonyms(identity, chemical["name"])
        source_tokens = {t.strip() for t in (identity.get("Synonyms") or "").split("^")}
        assert all(a in source_tokens for a in aliases)
        assert len({a.casefold() for a in aliases}) == len(aliases)
        assert chemical["name"].strip().casefold() not in {a.casefold() for a in aliases}
        chemical["synonyms"] = aliases
        records.append({
            "id": chemical["id"], "name": chemical["name"], "nt52": chemical["nt52"],
            "sourceRecord1Based": source_record_number,
            "sourceInChIKey": identity.get("StdInChIKey"),
            "rawSynonymsSha256": sha(identity["Synonyms"].encode("utf-8")) if identity.get("Synonyms") else None,
            "status": "source_names_available" if aliases else "no_usable_name_tokens" if identity else "no_exact_key_source_record",
            "synonyms": aliases, "rejectedTokens": rejected,
        })
    after = json.dumps(catalog_without_synonyms(catalog), ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
    assert before == after, "Synonyms enrichment must not change any other catalogue field."
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "catalogVersion": catalog["version"], "source": source_record(SOURCES["identityMaster"]),
        "sourceField": "Synonyms", "joinKey": "StdInChIKey = catalogue.id (full, exact InChIKey)",
        "separator": "^", "missingValue": [],
        "rules": [
            "Retain source spelling and order after outer whitespace trimming; case-insensitive deduplication and removal of the displayed canonical name.",
            "Remove identifiers, CAS-containing mixed cells, formula/mass cells, SMILES/InChI strings, database/catalogue codes and commercial product descriptions; retain each rejected token and reason below.",
            "Do not split names on commas or other IUPAC punctuation. No aliases are invented, translated, corrected or transferred from a name/CAS/fuzzy match.",
            "A retained alias is a name recorded by the local identity source, not an independent external verification of every synonym, salt form or stereochemical equivalence.",
            "The displaced chemical_parameters.Synonyms column is not used as a fallback. Missing exact-key source records receive an empty list.",
        ],
        "counts": {
            "sourceRecords": len(source_rows), "catalogChemicals": len(records),
            "exactKeySourceMatches": sum(r["sourceRecord1Based"] is not None for r in records),
            "chemicalsWithSynonyms": sum(bool(r["synonyms"]) for r in records),
            "nt52WithSynonyms": sum(bool(r["synonyms"]) for r in records if r["nt52"]),
            "chemicalsWithoutSynonyms": sum(not r["synonyms"] for r in records),
            "retainedNames": sum(len(r["synonyms"]) for r in records),
            "rejectionsByReason": dict(Counter(t["reason"] for r in records for t in r["rejectedTokens"])),
        },
        "validation": {
            "uniqueSourceKeys": True, "allNamesPresentInExactSourceRecord": True,
            "caseInsensitiveUniqueWithinChemical": True, "allOtherCatalogFieldsUnchanged": before == after,
            "nonSynonymContentSha256Before": sha(before), "nonSynonymContentSha256After": sha(after),
        },
        "records": records,
    }


def update_synonyms_only():
    path = ROOT / "public/data/chemical-catalog.json"
    catalog = json.loads(path.read_text(encoding="utf-8-sig"))
    audit = enrich_catalog_synonyms(catalog)
    write_json(path, catalog)
    write_json(ROOT / "src/content/catalog-synonyms-provenance.json", audit)
    print(json.dumps({"mode": "synonyms-only", "counts": audit["counts"], "validation": audit["validation"]}, ensure_ascii=False))


def xlsx_rows(path, header=0):
    """Read the first sheet, retaining text and numeric cell values as supplied."""
    s = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with ZipFile(path) as z:
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            strings = ["".join(x.itertext()) for x in ET.fromstring(z.read("xl/sharedStrings.xml"))]
        workbook = ET.fromstring(z.read("xl/workbook.xml"))
        rels = {x.attrib["Id"]: x.attrib["Target"] for x in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
        rid = workbook.find(s + "sheets")[0].attrib["{" + NS["r"] + "}id"]
        target = rels[rid]
        target = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
        raw = ET.fromstring(z.read(target))
        parsed = []
        for row in raw.findall(".//" + s + "sheetData/" + s + "row"):
            # Sparse worksheet XML can omit blank physical rows; header indices
            # refer to Excel row positions, not to the number of XML elements.
            while len(parsed) < int(row.attrib["r"]) - 1:
                parsed.append([])
            values = {}
            for c in row:
                letters = re.match(r"[A-Z]+", c.attrib["r"]).group()
                col = 0
                for letter in letters:
                    col = col * 26 + ord(letter) - 64
                typ = c.attrib.get("t")
                node = c.find(s + "v")
                value = node.text if node is not None else None
                if typ == "s" and value is not None:
                    value = strings[int(value)]
                elif typ == "inlineStr":
                    value = "".join(t.text or "" for t in c.findall(".//" + s + "t"))
                elif value is not None and typ not in {"str", "e"}:
                    value = float(value)
                values[col - 1] = value
            parsed.append([values.get(i) for i in range(max(values, default=-1) + 1)])
    headings = parsed[header]
    return [{name: row[i] if i < len(row) else None for i, name in enumerate(headings) if name}
            for row in parsed[header + 1:] if any(v is not None for v in row)]


def build_catalog():
    tables = {k: csv_rows(p) for k, p in SOURCES.items() if p.suffix == ".csv"}
    norman = xlsx_rows(SOURCES["norman"])
    literature = xlsx_rows(SOURCES["literature"])
    extra = xlsx_rows(SOURCES["literature355"])
    rep_rows = xlsx_rows(SOURCES["rep"], header=6)
    training = xlsx_rows(SOURCES["training"])
    norm = {r["InChIKey"]: r for r in norman if r.get("InChIKey")}
    lit = {r["InChIKey"]: r for r in literature}
    extra_by_key = {r["InChIKey"]: r for r in extra}
    reps = {r["InChIKey"]: r for r in rep_rows if (number(r.get("Rep")) or 0) > 0}
    train_ids = {clean(r["DTXSID"]) for r in training}
    params = {r["StdInChIKey"]: r for r in tables["parameters"]}
    identities = {r["StdInChIKey"]: r for r in tables["identityMaster"]}
    masses = {r["StdInChIKey"]: r for r in tables["massAudit"]}
    eligibility = {r["StdInChIKey"]: r for r in tables["coverage"]}
    use_notes = {r["StdInChIKey"]: r for r in tables["useSource"]}
    nt = {r["StdInChIKey"] for r in tables["identity52"]}
    metric_rows = {}
    city_ww = defaultdict(list)
    observed_counts = Counter()
    for r in tables["cityMetrics"]:
        metric_rows.setdefault(r["StdInChIKey"], r)
        city_ww[r["StdInChIKey"]].append(number(r["ww_concentration_nM"]))
        if r["is_observed"].lower() == "true":
            observed_counts[r["StdInChIKey"]] += 1
    final = defaultdict(list)
    full_observed = Counter()
    for r in tables["concentrations"]:
        final[r["StdInChIKey"]].append(number(r["final_imputed_concentration_nM"]))
        if r["is_observed"].lower() == "true":
            full_observed[r["StdInChIKey"]] += 1
    ww_ranks = {r["StdInChIKey"]: r for r in tables["ranks"] if r["metric"] == "WW_nM"}
    cohort_keys = {r["StdInChIKey"] for r in tables["cohort"]}
    assert len(cohort_keys) == 663 and len(nt) == 52 and nt <= cohort_keys
    assert len(norm) == 1034 and len(norman) == 1035
    assert len(lit) == 1554 and len(reps) == 97 and len(train_ids) == 472
    assert set(reps) & cohort_keys == nt | {"DDRJAANPRJIHGJ-UHFFFAOYSA-N"}
    chemicals = []
    for row in tables["cohort"]:
        key = row["StdInChIKey"]
        p, n, l, m = params.get(key, {}), norm.get(key, {}), lit.get(key, {}), masses.get(key, {})
        identity = identities.get(key, {})
        city = metric_rows.get(key, {})
        target = key in nt
        # Step4 inherited upstream metadata displacement: some CAS fields hold
        # ExposomeX IDs and some Formula cells hold synonyms. Cross-check the
        # independent exact-InChIKey identity master, never relabel aliases.
        cas, cas_source, cas_raw = choose_valid([("chemical_mass.CAS", identity.get("CAS")), ("NORMAN_inventory.CAS", n.get("CAS")), ("TableS2.CAS", l.get("CAS")), ("chemical_parameters.CAS", p.get("CAS"))], valid_cas)
        dtx, dtx_source, _ = choose_valid([("chemical_mass.DTXSID", identity.get("DTXSID")), ("chemical_parameters.DTXSID", p.get("DTXSID")), ("NORMAN_inventory.DTXSID", n.get("DTXSID"))], valid_dtxsid)
        formula, formula_source, _ = choose_valid([("chemical_mass.Formula", identity.get("Formula")), ("chemical_parameters.Formula", p.get("Formula"))], valid_formula)
        smiles, smiles_source, _ = choose_valid([("chemical_mass.SMILES", identity.get("SMILES")), ("mass_mapping_audit.SMILES", m.get("SMILES")), ("chemical_parameters.SMILES", p.get("SMILES")), ("TableS2.SMILES", l.get("SMILES"))])
        corrections = []
        for field, validator, corrected in [("CAS", valid_cas, cas), ("Formula", valid_formula, formula)]:
            raw_value = clean(p.get(field))
            if raw_value and validator(raw_value) is None:
                corrections.append({"field": field, "rejectedSource": "chemical_parameters." + field, "rejectedValue": raw_value, "reason": "Not a valid " + field + " value; source metadata displacement or placeholder.", "replacement": corrected})
        descriptor_missing = any(number(p.get(k)) is None for k in ["fhlb_ifsqsar", "logSoliquid_ifsqsar", "logSwliquid_ifsqsar"])
        reason = "Retained in the A2 reconstruction background: at least three observed urban areas and a supported same-cohort correlation partner; urban areas also meet minimum chemical coverage."
        if target:
            reason += " Member of the literature candidate inventory with a positive numerical REP for neurite-outgrowth inhibition; included in the 53-compound overlap after excluding endogenous creatinine. Panel membership was fixed before exposure translation and effect ranking."
        elif key in reps:
            reason += " Positive REP is available, but this endogenous creatinine marker was excluded from the exogenous NT52 panel."
        else:
            reason += " Not included in the fixed NT52 effect panel; no positive numerical REP from the selected endpoint source is assigned here."
        evidence = ["NORMAN wastewater archive; frozen A2 coverage and correlation-support audit."]
        if key in lit:
            evidence.append("Literature candidate inventory (Table S2).")
        if key in reps:
            evidence.append("Positive molar relative effect potency, neurite-outgrowth inhibition; Braun et al., Science 386, 301–309 (2024), source Table S13 (Science_REP.xlsx).")
        if key in extra_by_key:
            e = extra_by_key[key]
            evidence.append(" ".join(str(e.get(k) or "") for k in ["Evidence basis", "Reference", "DOI"]))
        default = statistics.median(city_ww[key]) if target else None
        if target:
            assert len(final[key]) == 117 and len(city_ww[key]) == 117
            assert math.isclose(default, statistics.median(final[key]), rel_tol=1e-12, abs_tol=1e-14)
            assert default == number(ww_ranks[key]["median"])
        chemical = {
            "id": key,
            "name": clean(city.get("Name")) or clean(p.get("Name")) or clean(m.get("Name")) or clean(row.get("compound_names")) or clean(n.get("Name")),
            "category": clean(city.get("Category_II")) or clean(p.get("Category_II")),
            "nt52": target,
            "cas": cas,
            "dtxsid": dtx,
            "smiles": smiles,
            "formula": formula,
            "molecularWeight": number(city.get("Average_mass_g_mol")) if target else number(m.get("Average_mass_g_mol")),
            "trainingMember": (dtx in train_ids) if dtx else None,
            "trainingMembershipBasis": "Exact DTXSID match against the 472-chemical Table S14 training list." if dtx else "Not documented: source DTXSID is missing, and no name/CAS guess was used to classify training membership.",
            "selectionReason": reason,
            "evidence": " ".join(evidence),
            "identitySource": "Exact InChIKey join to chemical_mass identity master, supplemented by the A2 mass audit, NORMAN inventory and Table S2. CAS syntax/check digit and formula syntax checked; displaced source metadata rejected. See identityFieldSources and identityCorrections.",
            "identityFieldSources": {"cas": cas_source, "dtxsid": dtx_source, "formula": formula_source, "smiles": smiles_source},
            "identityCorrections": corrections,
            "categorySource": clean(p.get("category_source")),
            "defaultWW": default,
            "fhlb": number(p.get("fhlb_ifsqsar")),
            "logSoliquid": number(p.get("logSoliquid_ifsqsar")),
            "logSwliquid": number(p.get("logSwliquid_ifsqsar")),
            "halfLifeHours": number(city.get("t0.5_adme")) if target else number(p.get("t0.5_adme")),
            "logVDss": number(city.get("logVDss_adme")) if target else number(p.get("logVDss_adme")),
            "rep": number(city.get("REP")) if target else number(reps.get(key, {}).get("Rep")),
            "descriptorImputed": descriptor_missing,
            "descriptorStatus": "Raw descriptor missing; any model calculation must use the saved training-set imputer." if descriptor_missing else "All three raw IFSQSAR descriptors are available.",
            "casSourceValue": cas_raw,
            "categoryLLMStatus": clean(p.get("category_llm_status")),
            "categoryNote": clean(p.get("category_llm_note")),
            "useSourceNote": clean(use_notes.get(key, {}).get("Use_Source_Note")),
            "literatureMember": key in lit,
            "positiveREPMember": key in reps,
            "observedCityCount": full_observed[key],
            "retainedCorrelationPartners": number(eligibility.get(key, {}).get("partners_within_final_cohort")),
            "referenceWW": {"median": number(ww_ranks.get(key, {}).get("median")), "mean": number(ww_ranks.get(key, {}).get("mean")), "p25": number(ww_ranks.get(key, {}).get("p25")), "p75": number(ww_ranks.get(key, {}).get("p75")), "minimum": number(ww_ranks.get(key, {}).get("minimum")), "maximum": number(ww_ranks.get(key, {}).get("maximum"))} if target else None,
        }
        assert chemical["id"] and chemical["name"]
        chemical["synonyms"], _ = extract_synonyms(identity, chemical["name"])
        assert re.fullmatch(r"[A-Z]{14}-[A-Z]{10}-[A-Z]", key)
        assert chemical["cas"] is None or valid_cas(chemical["cas"])
        assert chemical["dtxsid"] is None or valid_dtxsid(chemical["dtxsid"])
        assert chemical["formula"] is None or valid_formula(chemical["formula"])
        assert chemical["smiles"] is None or ("^" not in chemical["smiles"] and "EX:" not in chemical["smiles"] and "DTXSID" not in chemical["smiles"])
        if target:
            assert all(chemical[k] is not None for k in ["cas", "dtxsid", "smiles", "formula", "molecularWeight", "defaultWW", "halfLifeHours", "logVDss", "rep"])
            assert chemical["rep"] > 0 and chemical["defaultWW"] > 0
            assert math.isclose(chemical["rep"], number(reps[key]["Rep"]), rel_tol=1e-12)
        chemicals.append(chemical)
    chemicals.sort(key=lambda r: (not r["nt52"], r["name"].casefold(), r["id"]))
    counts = {
        "chemicals": 663, "nt52": 52, "cities": 117, "normanEntries": 1035,
        "normanValidInChIKeys": 1034, "literatureCandidates": 1554,
        "positiveREP": 97, "positiveREPInCohort": 53, "creatinineExcluded": 1,
        "trainingChemicals": 472, "trainingMembersInCatalog": sum(r["trainingMember"] is True for r in chemicals),
        "trainingMembershipUnknown": sum(r["trainingMember"] is None for r in chemicals),
        "trainingMembersInNT52": sum(r["trainingMember"] is True for r in chemicals if r["nt52"]),
        "nt52RawDescriptorMissing": sum(r["descriptorImputed"] for r in chemicals if r["nt52"]),
        "nt52ObservedCells": sum(observed_counts.values()), "nt52ReconstructedCells": 6084 - sum(observed_counts.values()),
        "identityRowsWithRejectedUpstreamFields": sum(bool(r["identityCorrections"]) for r in chemicals),
        "categoryCountsNT52": dict(Counter(r["category"] for r in chemicals if r["nt52"])),
        "availableFields": {k: sum(r[k] is not None for r in chemicals) for k in ["cas", "dtxsid", "smiles", "formula", "molecularWeight", "category", "defaultWW", "fhlb", "logSoliquid", "logSwliquid", "halfLifeHours", "logVDss", "rep"]},
    }
    assert counts["nt52RawDescriptorMissing"] == 3 and counts["trainingMembersInNT52"] == 27
    return {
        "version": VERSION,
        "defaultSource": "Per-chemical median of the 117 final A2 ww_concentration_nM values in the frozen Step4 city table, in nM. This is the WW input actually used for reference translation; original observed cells remain identifiable. Defaults exist only for NT52. Step2 values can differ at floating-point serialization precision.",
        "counts": counts,
        "units": {"defaultWW": "nM", "molecularWeight": "g/mol", "fhlb": "IFSQSAR reference-fish whole-body biotransformation half-life descriptor (source scale)", "logSoliquid": "log10(mol/L), dry-octanol solubility", "logSwliquid": "log10(mol/L), water solubility", "halfLifeHours": "hours", "logVDss": "log10(L/kg)", "rep": "dimensionless molar potency relative to narciclasine"},
        "notes": ["663, 472 and 52 describe different roles, not a nested training-selection funnel.", "descriptorImputed flags missing raw IFSQSAR inputs; null values have not been replaced in the catalogue. The saved model imputer supplies training medians during calculation.", "Category labels can be source-provided, LLM-assigned or manually overridden; categorySource records this provenance.", "A positive REP on creatinine does not make it a selectable NT52 target.", "Predictions for a median-input scenario are not the median of the 117 city-specific predictions; custom results must be separated from manuscript reference statistics."],
        "chemicals": chemicals,
    }


class Manuscript:
    def __init__(self, path):
        self.path = path
        self.zip = ZipFile(path)
        self.hash = sha(path.read_bytes())
        self.root = ET.fromstring(self.zip.read("word/document.xml"))
        self.paragraphs = self.root.findall("./w:body/w:p", NS)
        self.text = ["".join(t.text or "" for t in p.findall(".//w:t", NS)).strip() for p in self.paragraphs]
        self.rels = {r.attrib["Id"]: r.attrib["Target"] for r in ET.fromstring(self.zip.read("word/_rels/document.xml.rels"))}

    def figure(self, identifier, pattern):
        candidates = [i for i, text in enumerate(self.text) if re.match(pattern, text)]
        assert len(candidates) == 1, (identifier, candidates)
        ci = candidates[0]
        image_i = next((i for i in range(ci - 1, max(ci - 5, -1), -1) if self.paragraphs[i].findall(".//a:blip", NS)), None)
        assert image_i is not None, identifier
        images = self.paragraphs[image_i].findall(".//a:blip", NS)
        assert len(images) == 1
        rid = images[0].attrib["{" + NS["r"] + "}embed"]
        media = posixpath.normpath("word/" + self.rels[rid])
        data = self.zip.read(media)
        assert data.startswith(b"\x89PNG\r\n\x1a\n"), (identifier, media)
        width, height = struct.unpack(">II", data[16:24])
        url = "/figures/" + identifier + ".png"
        indices = [ci]
        if ci + 1 < len(self.text) and self.text[ci + 1]:
            indices.append(ci + 1)
        record = {"id": identifier, "title": self.text[ci], "url": url, "src": url, "caption": "\n".join(self.text[i] for i in indices), "sourceDocument": self.path.name}
        warnings = {
            "ED2": "The source caption says the first-column NT52 label requires verification against the fixed-panel union; the original is retained.",
            "ED6": "Historical 42-chemical DeepToxLab-weighted comparison, separate from the current NT52 neurite-outgrowth BEQ analysis.",
            "FigS5": "The source image/caption reports 193 strong positive associations, whereas the BW main text and supplementary Section 2 report 201. The original figure is retained; the discrepancy remains unresolved.",
        }
        if identifier in warnings:
            record["note"] = warnings[identifier]
        provenance = {**record, "source_document_sha256": self.hash, "source_media": media, "relationship_id": rid, "image_paragraph_index": image_i, "caption_paragraph_indices": indices, "paragraph_index_basis": "zero-based direct body paragraphs in word/document.xml", "bytes": len(data), "sha256": sha(data), "width": width, "height": height, "transformation": "none; exact embedded PNG bytes"}
        return record, provenance, data


def section(identifier, title, paragraphs, figures=()):
    return {"id": identifier, "title": title, "paragraphs": paragraphs, "figureIds": list(figures)}


def descriptions():
    """Load approved interface copy independently of scientific source extraction."""
    return json.loads((ROOT / "src/content/platform-copy.json").read_text(encoding="utf-8"))["descriptions"]

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")


def validate_structure(catalog):
    """Use the existing RDKit runtime, or a cache bound to exact source values.

    Formula cells remain source values; calculated formulas are audit evidence,
    never a substitute for absent source formulas. No package is installed.
    """
    cache_path = ROOT / "src/content/catalog-structure-audit.json"
    signature = sha(json.dumps([(c["id"], c["smiles"], c["formula"]) for c in catalog["chemicals"]], ensure_ascii=False).encode("utf-8"))
    try:
        import rdkit
        from rdkit import Chem, RDLogger
        from rdkit.Chem import inchi, rdMolDescriptors
    except ImportError:
        if not cache_path.exists():
            return {"status": "not_run", "reason": "RDKit unavailable; source-column and identifier checks still apply."}
        audit = json.loads(cache_path.read_text(encoding="utf-8"))
        if audit.get("inputSignature") != signature:
            raise ValueError("Structure audit cache is stale. Rerun with the existing RDKit research runtime.")
    else:
        RDLogger.DisableLog("rdApp.*")
        records = []
        for c in catalog["chemicals"]:
            mol = Chem.MolFromSmiles(c["smiles"])
            if mol is None:
                raise ValueError("Invalid source SMILES: " + c["id"])
            generated = inchi.MolToInchiKey(mol)
            if generated.split("-")[0] != c["id"].split("-")[0]:
                raise ValueError("Source structure connectivity does not match identifier: " + c["id"])
            calc_formula = rdMolDescriptors.CalcMolFormula(mol)
            status = "exact_inchikey" if generated == c["id"] else "same_connectivity_stereochemistry_review"
            formula_status = "not_available" if not c["formula"] else "exact" if calc_formula == c["formula"] else "charge_notation_only" if re.sub(r"[+-]\d*$", "", calc_formula) == c["formula"] else "requires_review"
            records.append({"id": c["id"], "nt52": c["nt52"], "computedInChIKey": generated, "structureStatus": status, "sourceFormula": c["formula"], "computedFormulaForAudit": calc_formula, "formulaStatus": formula_status})
        audit = {"status": "checked", "inputSignature": signature, "rdkitVersion": rdkit.__version__, "rows": records, "counts": {"structures": dict(Counter(x["structureStatus"] for x in records)), "formulas": dict(Counter(x["formulaStatus"] for x in records))}}
        write_json(cache_path, audit)
    lookup = {r["id"]: r for r in audit["rows"]}
    for c in catalog["chemicals"]:
        a = lookup[c["id"]]
        c["structureIdentityStatus"] = a["structureStatus"]
        c["formulaIdentityStatus"] = a["formulaStatus"]
        c["computedStructureInChIKey"] = a["computedInChIKey"]
        c["structureNote"] = "Source SMILES has the same connectivity block but a different stereochemical InChIKey layer; original identifier and source structure retained for review." if a["structureStatus"] != "exact_inchikey" else None
    catalog["structureAudit"] = {k: v for k, v in audit.items() if k != "rows"}
    return catalog["structureAudit"]


def main():
    catalog = build_catalog()
    synonym_audit = enrich_catalog_synonyms(catalog)
    structure_audit = validate_structure(catalog)
    main_doc, supplement = Manuscript(MAIN), Manuscript(SM)
    figures, image_manifest, image_payloads = [], [], []
    specifications = [(f"Fig{i}", rf"^Fig\. {i}\s*[|.]", main_doc) for i in range(1, 5)]
    specifications += [(f"ED{i}", rf"^Extended Data Fig\. {i}\s*[|.]", main_doc) for i in [1, 2, 3, 4, 6]]
    specifications += [(f"FigS{i}", rf"^Fig\. S{i}\s*[|.]", supplement) for i in range(1, 7)]
    for identifier, pattern, document in specifications:
        f, record, data = document.figure(identifier, pattern)
        figures.append(f); image_manifest.append(record); image_payloads.append((f["url"], data))
    assert len(figures) == 15
    paper_path = ROOT / "src/content/paper.json"
    paper = json.loads(paper_path.read_text(encoding="utf-8-sig"))
    paper["title"] = main_doc.text[0]
    paper["longName"] = "Wastewater-based Framework for Prioritizing Neurotoxic Chemical Mixtures"
    paper["team"] = {
        "authorsText": main_doc.text[1].removeprefix("Author:").strip(),
        "affiliations": [s for s in main_doc.text[2:19] if re.match(r"^\d+ ", s)],
        "correspondence": [s for s in main_doc.text[:23] if s.startswith("*Correspondence")],
    }
    assert len(paper["team"]["affiliations"]) == 17
    assert not any("???" in s for s in paper["team"]["affiliations"])
    paper["citation"] = {"text": "Fu, N. et al. Mapping Neurotoxic Mixture Burdens Across European Cities.", "status": "Manuscript; publication details pending"}
    platform_copy = ROOT / "src/content/platform-copy.json"
    if platform_copy.exists():
        paper["license"] = json.loads(platform_copy.read_text(encoding="utf-8"))["license"]
    paper["descriptions"] = descriptions()
    paper["descriptionSections"] = {k: v["sections"] for k, v in paper["descriptions"].items()}
    paper["figures"] = figures
    paper["figureGroups"] = {"main": ["Fig1", "Fig2", "Fig3", "Fig4"], "extended": ["ED1", "ED2", "ED3", "ED4", "ED6"], "supplementary": [f"FigS{i}" for i in range(1, 7)]}
    paper["unavailableFigures"] = [{"id": "ED5", "title": "Extended Data Fig. 5 | Overview of the WPN web platform.", "reason": "The BW manuscript says 待补充 and provides no image; none has been fabricated."}]
    paper["sourceVersions"] = {
        "mainText": {**source_record(MAIN), "version": "2026-10-04 BW"},
        "supplement": {**source_record(SM), "version": "2026-10-04 BW"},
        "researchCode": {"directory": "【投稿版本】/WPN_code", "versionNote": "Frozen 2026-09-25 A2 numerical analysis; manuscript prose and embedded images use 2026-10-04 BW."},
        "thirdPartyNotices": paper.get("sourceVersions", {}).get("thirdPartyNotices", []),
        "figureManifest": "/figures/manifest.json", "catalogVersion": VERSION,
        "extractedOn": "2026-10-08",
    }
    paper["notes"] = [
        "The current BW manuscript supplies the complete affiliation 15, including Uppsala SE-75007, Sweden; the former unresolved-address note no longer applies.",
        "All 15 figure images are exact embedded PNGs from the BW documents: four main figures, five extended-data figures and six supplementary figures. ED5 remains unavailable.",
        "The ED2 source caption explicitly says that its first-column NT52 label requires verification against the fixed-panel union. The original image and caption are retained with a visible note.",
        "The BW main text and supplementary Section 2 report 201 strong positive FAO associations, while Fig. S5's original caption reports 193. The source discrepancy is retained and not silently corrected.",
        "Supplementary Section 4 reports 8,399 distinct A2 masking cells, but the BW main Results, ED3 and frozen validation CSV support 8,339. Website reconstruction summaries use the verified 8,339.",
        "The main Methods contains an E-BIO-based exclusion statement, whereas the supplementary table description states that recognition was not an additional NT52 selection criterion. The implemented fixed-panel selection follows the audited REP/coverage intersection minus creatinine; the wording conflict remains documented.",
        "ED6 uses historical 42-chemical DeepToxLab-weighted scores and is not independent validation of current NT52 neurite-outgrowth BEQ.",
        "No publication journal, DOI or publication date has been invented. Manuscript and frozen-data version dates are separate.",
        "The 52 default input medians are derived from the frozen final A2 WW matrix. Model outputs from this one input profile must not be labelled as the medians of 117 city-specific output profiles.",
    ]
    for url, data in image_payloads:
        target = ROOT / "public" / url.lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    write_json(ROOT / "public/figures/manifest.json", image_manifest)
    write_json(ROOT / "public/data/chemical-catalog.json", catalog)
    write_json(ROOT / "src/content/catalog-synonyms-provenance.json", synonym_audit)
    write_json(paper_path, paper)
    provenance = {
        "version": VERSION, "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sources": {k: source_record(v) for k, v in SOURCES.items()},
        "fieldRules": {"id": "Exact frozen-cohort StdInChIKey", "trainingMember": "Exact DTXSID membership in Table S14 (472 chemicals)", "defaultWW": "statistics.median of all 117 frozen Step4 ww_concentration_nM values per NT52, matching the backend input contract. Near equality checked against Step2 final values and frozen ranking CSV; serialization-level differences are not different scientific scenarios.", "rep": "Positive numerical Rep from Science_REP.xlsx; NT52 checked against Step4 REP", "identity": "Exact-InChIKey chemical_mass identity master first, then mass audit/NORMAN/literature; CAS check digits and formula syntax reject upstream displaced metadata; per-field sources recorded", "category": "Category_II from original parameter source, with category_source and category_llm_status retained", "molecularWeight": "Step4 mass for NT52; A2 mass_mapping_audit for other chemicals", "descriptorImputed": "Missing raw fhlb/logSoliquid/logSwliquid flag; values remain null for the model's saved imputer", "halfLifeHours": "ADMETlab t0.5_adme; raw hours, not fish fhlb", "logVDss": "ADMETlab log10(L/kg)"},
        "counts": catalog["counts"], "notes": catalog["notes"], "structureAudit": structure_audit,
    }
    write_json(ROOT / "src/content/catalog-provenance.json", provenance)
    write_json(ROOT / "src/content/content-provenance.json", {"version": VERSION, "documents": [source_record(MAIN), source_record(SM)], "descriptionBasis": "Editorial website summaries of BW main Results/Methods/Discussion and SM Sections 1–4; custom-platform workflow reflects user-authorized operation. Exact captions remain distinct from summaries.", "figures": image_manifest, "unresolvedSourceIssues": paper["notes"][2:7], "generator": "tools/prepare_catalog.py"})
    data_manifest_path = ROOT / "public/data/manifest.json"
    if data_manifest_path.exists():
        data_manifest = json.loads(data_manifest_path.read_text(encoding="utf-8-sig"))
        data_manifest.setdefault("versions", {})["manuscript"] = "2026-10-04 BW"
        data_manifest["manuscriptVersion"] = "2026-10-04 BW"
        data_manifest["manuscriptVersionNote"] = "Current prose and figures: BW documents, recorded in src/content/content-provenance.json. Original numeric-data generation provenance is retained as historical evidence; frozen CSV bytes are unchanged."
        write_json(data_manifest_path, data_manifest)
    print(json.dumps({"catalog": catalog["counts"], "figures": len(figures), "descriptionSections": {k: len(v["sections"]) for k, v in paper["descriptions"].items()}, "title": paper["title"]}, ensure_ascii=False))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:] == ["--synonyms-only"]:
        update_synonyms_only()
    elif sys.argv[1:]:
        raise SystemExit("Usage: prepare_catalog.py [--synonyms-only]")
    else:
        main()
