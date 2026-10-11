"""Portable CPU inference from the packaged WPN artifacts; never trains a model."""
from __future__ import annotations

import copy
import csv
import hashlib
import importlib.util
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ["ww_concentration_uM_log10", "fhlb_ifsqsar", "logSoliquid_ifsqsar", "logSwliquid_ifsqsar"]
PANEL_FILE = "public/downloads/city-metrics-nt52-a2.csv"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def load_cpu_model(package_root):
    """Reuse the standalone package's offline loader and CUDA-storage CPU remapping."""
    spec = importlib.util.spec_from_file_location("wpn_packaged_cpu_core", package_root / "wpn_core.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("The packaged CPU model loader is unavailable.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CPUModel()


def positive(value, label):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be a positive, finite JSON number in nM.")
    return float(value)


class WPNEngine:
    def __init__(self, config_path=None):
        self.config = json.loads(Path(config_path or ROOT / "api/config.json").read_text(encoding="utf-8-sig"))
        package = Path(self.config["packageRoot"])
        self.package_root = (ROOT / package).resolve()
        if package.is_absolute() or not self.package_root.is_relative_to(ROOT):
            raise ValueError("packageRoot must be a relative directory inside the WPN project.")
        if self.config.get("device") != "cpu":
            raise ValueError("This portable website is configured for CPU inference.")
        self.model_dir = self.package_root / "models"
        self.checkpoint = self.model_dir / "tabpfn-v2.6-regressor-v2.6_default.ckpt"
        self.model_version = self.config["modelLabel"] + " / " + self.config["modelSHA256"][:12]
        self.data_version = self.config["dataVersion"]
        self._read_parameters()

    def _read_parameters(self):
        catalog = json.loads((self.package_root / "data/chemicals.json").read_text(encoding="utf-8-sig"))
        self.catalog = {row["id"]: row for row in catalog}
        if len(catalog) != 52 or len(self.catalog) != 52:
            raise ValueError("The packaged NT52 catalog must contain 52 unique chemicals.")
        self.chemical_ids = tuple(sorted(self.catalog))
        self.defaults = {key: positive(self.catalog[key]["defaultWW"], key) for key in self.chemical_ids}
        rows = read_csv(self.package_root / "data/parameters.csv")
        self.parameters = {row["StdInChIKey"]: row for row in rows}
        if len(rows) != 52 or set(self.parameters) != set(self.chemical_ids):
            raise ValueError("The NT52 parameter table is incomplete or duplicated.")
        self.rep = {key: positive(float(self.parameters[key]["REP"]), key + " REP") for key in self.chemical_ids}
        for key in self.chemical_ids:
            parameter = self.parameters[key]
            for field in ("t0.5_adme", "logVDss_adme"):
                if not math.isfinite(float(parameter[field])):
                    raise ValueError(f"Missing {field} for {key}.")
            if float(parameter["t0.5_adme"]) <= 0 or self.rep[key] <= 0:
                raise ValueError(f"Invalid toxicokinetic/REP parameter for {key}.")
        self.default_inputs = [{"chemical": key, "ww": self.defaults[key]} for key in self.chemical_ids]

    def verify_artifacts(self):
        """Validate bundled files and scientific metadata without loading the model."""
        manifest = json.loads((self.model_dir / "manifest.json").read_text(encoding="utf-8-sig"))
        expected = manifest.get("sha256", {})
        required = {"model.joblib", "imputer.joblib", "scaler.joblib", "feature_columns.csv", "feature_preprocessing.csv", self.checkpoint.name}
        if not required.issubset(expected):
            raise RuntimeError("The packaged model manifest is incomplete.")
        if expected["model.joblib"] != self.config["modelSHA256"] or expected[self.checkpoint.name] != self.config["checkpointSHA256"]:
            raise RuntimeError("The packaged model/checkpoint identity does not match the original artifacts.")
        for name in required:
            path = self.model_dir / name
            if not path.is_file() or sha256(path) != expected[name]:
                raise RuntimeError(f"Packaged model file is missing or has the wrong SHA-256: {name}. No download was attempted.")
        features = [row["feature_name"] for row in read_csv(self.model_dir / "feature_columns.csv")]
        preprocessing = read_csv(self.model_dir / "feature_preprocessing.csv")
        standardized = [r["feature_name"] for r in preprocessing if r["standardized"].lower() in {"true", "1", "yes"}]
        if features != FEATURES or standardized != FEATURES[1:] or manifest.get("features") != FEATURES or manifest.get("targetUnit") != "umol/day" or manifest.get("device") != "cpu":
            raise RuntimeError("The original feature order, preprocessing or model target unit does not match.")
        return manifest

    def initialize(self):
        self.verify_artifacts()
        self._cpu_model = load_cpu_model(self.package_root)
        self.np, self.pd, self.torch = self._cpu_model.np, self._cpu_model.pd, self._cpu_model.torch
        self.estimator = self._cpu_model.estimator
        self.imputer, self.scaler = self._cpu_model.imputer, self._cpu_model.scaler
        self.runtime = {"python": sys.version, "executable": sys.executable, "numpy": self.np.__version__,
                        "pandas": self.pd.__version__, "torch": self.torch.__version__, "device": "cpu"}

    def validate_inputs(self, payload):
        if type(payload) is not dict or set(payload) != {"inputs"}:
            raise ValueError("The request must contain only the inputs field; model parameters cannot be submitted.")
        rows = payload["inputs"]
        if type(rows) is not list or not 1 <= len(rows) <= 52:
            raise ValueError("Provide between 1 and 52 unique NT52 chemicals.")
        lookup = {}
        for row in rows:
            if type(row) is not dict or not {"chemical", "ww"} <= set(row) <= {"chemical", "ww", "origin"}:
                raise ValueError("Each input must contain chemical and ww, with an optional origin.")
            key = row["chemical"]
            if type(key) is not str or key not in self.defaults:
                raise ValueError("An input contains an unknown NT52 chemical identifier.")
            if key in lookup:
                raise ValueError(f"Duplicate chemical: {key}.")
            origin = row.get("origin", "user")
            if type(origin) is not str or origin not in {"user", "example"}:
                raise ValueError("Input origin must be user or example.")
            lookup[key] = {"chemical": key, "ww": positive(row["ww"], key), "origin": origin}
        return [lookup[key] for key in self.chemical_ids if key in lookup]

    def predict_log10(self, inputs):
        """Predict the supplied rows, also supporting full frozen regression checks."""
        pd, np = self.pd, self.np
        raw_rows = []
        for row in inputs:
            key, ww = row["chemical"], positive(row["ww"], row["chemical"])
            parameter = self.parameters[key]
            raw_rows.append([np.log10(ww) - 3.] + [parameter[field] for field in FEATURES[1:]])
        raw = pd.DataFrame(raw_rows, columns=FEATURES).apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
        ready = pd.DataFrame(self.imputer.transform(raw[FEATURES]), columns=FEATURES)
        ready.loc[:, FEATURES[1:]] = self.scaler.transform(ready[FEATURES[1:]])
        if not np.isfinite(ready.to_numpy()).all():
            raise RuntimeError("The original preprocessing returned non-finite features.")
        predictions = np.asarray(self.estimator.predict(ready.to_numpy(float)), dtype=float)
        if predictions.shape != (len(inputs),) or not np.isfinite(predictions).all():
            raise RuntimeError("The original model returned a non-finite prediction.")
        return predictions

    def evaluate(self, inputs):
        logs = self.predict_log10(inputs)
        rows = []
        for item, log_de in zip(inputs, logs):
            key, ww = item["chemical"], item["ww"]
            parameter = self.parameters[key]
            de = 10. ** float(log_de)
            cb = (de / 70.) * (float(parameter["t0.5_adme"]) / 24.) / (10. ** float(parameter["logVDss_adme"]) * math.log(2.))
            beq = cb * self.rep[key] * 307.25
            if not all(math.isfinite(v) and v > 0 for v in (de, cb, beq)):
                raise RuntimeError("A model-derived exposure or BEQ is outside the finite positive numerical range.")
            rows.append({"chemical": key, "ww": ww, "de": de, "cb": cb, "beq": beq})
        totals = {metric: math.fsum(row[metric] for row in rows) for metric in ("ww", "de", "beq")}
        if not all(math.isfinite(total) and total > 0 for total in totals.values()):
            raise RuntimeError("The scenario totals are not finite positive numbers.")
        for metric in totals:
            value_ranks = {}
            for position, value in enumerate(sorted((r[metric] for r in rows), reverse=True), 1):
                value_ranks.setdefault(value, position)
            for row in rows:
                row[metric + "Rank"] = value_ranks[row[metric]]
                row[metric + "Contribution"] = row[metric] / totals[metric] * 100.
        return {"rows": rows, "totals": totals}

    def run(self, run_id, inputs):
        # Validate again at this boundary so internal callers cannot add chemicals,
        # fill omitted inputs or accidentally return the full example profile.
        inputs = self.validate_inputs({"inputs": inputs})
        evaluated = self.evaluate(inputs)
        public_rows = [{field: row[field] for field in ("chemical", "ww", "beq", "beqRank", "beqContribution")}
                       for row in evaluated["rows"]]
        return {"id": run_id, "createdAt": utc_now(), "modelVersion": self.model_version, "dataVersion": self.data_version,
                "rows": public_rows, "totals": {key: evaluated["totals"][key] for key in ("ww", "beq")},
                "inputs": copy.deepcopy(inputs)}
