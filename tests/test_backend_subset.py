"""No-inference contracts for the portable CPU API, subsets and Excel previews.

Run with the project Python: -m unittest discover -s tests -p test_backend_subset.py -v
"""
from __future__ import annotations

import copy
from datetime import date
from io import BytesIO
import json
import math
from pathlib import Path
import socket
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
from zipfile import ZIP_DEFLATED, ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from engine import FEATURES, ROOT, WPNEngine
from import_excel import MAX_UNCOMPRESSED_BYTES, XLSX_MEDIA_TYPE, read_workbook
from server import RunService, create_server


def fixture_engine():
    """Use the real contract/formulas with predictable fitted-model outputs."""
    engine = WPNEngine.__new__(WPNEngine)
    engine.chemical_ids = tuple(f"CHEMICAL-{index:02}" for index in range(52))
    engine.defaults = {key: index + 1. for index, key in enumerate(engine.chemical_ids)}
    engine.parameters = {key: {"t0.5_adme": "24", "logVDss_adme": "0"} for key in engine.chemical_ids}
    engine.rep = {key: .5 for key in engine.chemical_ids}
    engine.default_inputs = [{"chemical": key, "ww": value} for key, value in engine.defaults.items()]
    engine.model_version = "test-model"
    engine.data_version = "test-data"
    engine.predict_log10 = lambda inputs: [math.log10(row["ww"]) for row in inputs]
    return engine


def workbook_bytes(rows, second_sheet=None):
    from openpyxl import Workbook
    workbook = Workbook()
    workbook.active.title = "Concentrations"
    for row in rows:
        workbook.active.append(row)
    if second_sheet is not None:
        for row in second_sheet:
            workbook.create_sheet("Ignored") if len(workbook.worksheets) == 1 else None
            workbook.worksheets[1].append(row)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


class PortableCPUContract(unittest.TestCase):
    def test_metadata_uses_only_packaged_52_chemical_data(self):
        engine = WPNEngine()
        self.assertEqual(engine.package_root, ROOT / "local_code")
        self.assertTrue(engine.model_dir.is_relative_to(ROOT))
        self.assertTrue(engine.checkpoint.is_relative_to(ROOT))
        self.assertEqual(len(engine.chemical_ids), 52)
        public = json.loads((ROOT / "public/data/chemical-catalog.json").read_text(encoding="utf-8"))
        defaults = {row["id"]: row["defaultWW"] for row in public["chemicals"] if row["nt52"]}
        self.assertEqual(engine.defaults, defaults)
        self.assertEqual(set(engine.parameters), set(engine.chemical_ids))
        self.assertTrue(all(math.isfinite(value) and value > 0 for value in engine.rep.values()))
        self.assertNotIn("sourceRoot", engine.config)
        self.assertNotIn("checkpoint", engine.config)

    def test_original_packaged_artifact_hashes_and_feature_contract(self):
        engine = WPNEngine()
        manifest = engine.verify_artifacts()
        self.assertEqual(manifest["features"], FEATURES)
        self.assertEqual(manifest["device"], "cpu")
        self.assertEqual(manifest["targetUnit"], "umol/day")
        engine.config["modelSHA256"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "identity"):
            engine.verify_artifacts()

    def test_package_path_cannot_escape_project(self):
        config = json.loads((ROOT / "api/config.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            for target in ("../outside", str(ROOT / "local_code")):
                config["packageRoot"] = target
                path.write_text(json.dumps(config), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "relative directory inside"):
                    WPNEngine(path)

    def test_cpu_loader_is_reused_and_original_preprocessing_order_is_kept(self):
        import numpy as np
        import pandas as pd
        engine = WPNEngine()
        key = engine.chemical_ids[0]
        engine.parameters[key] = {**engine.parameters[key], "fhlb_ifsqsar": "", "logSoliquid_ifsqsar": "2", "logSwliquid_ifsqsar": "3"}
        captured = {}

        class Imputer:
            def transform(self, values):
                captured["imputer"] = values.copy()
                return values.fillna(7).to_numpy()

        class Scaler:
            def transform(self, values):
                captured["scaler"] = values.copy()
                return values.to_numpy() * 2

        class Estimator:
            def predict(self, values):
                captured["prediction"] = values.copy()
                return np.array([-2.])

        model = SimpleNamespace(np=np, pd=pd, torch=SimpleNamespace(__version__="CPU-test"),
                                imputer=Imputer(), scaler=Scaler(), estimator=Estimator())
        with patch.object(engine, "verify_artifacts") as checked, patch("engine.load_cpu_model", return_value=model) as loaded:
            engine.initialize()
        checked.assert_called_once()
        loaded.assert_called_once_with(ROOT / "local_code")
        self.assertIs(engine.estimator, model.estimator)
        self.assertEqual(engine.runtime["device"], "cpu")
        self.assertEqual(engine.predict_log10([{"chemical": key, "ww": 1000.}]).tolist(), [-2.])
        self.assertEqual(list(captured["imputer"].columns), FEATURES)
        self.assertEqual(list(captured["scaler"].columns), FEATURES[1:])
        np.testing.assert_array_equal(captured["prediction"], [[0., 14., 4., 6.]])

    def test_prediction_shape_and_nonfinite_results_are_rejected(self):
        import numpy as np
        import pandas as pd
        engine = WPNEngine()
        engine.np, engine.pd = np, pd
        engine.imputer = SimpleNamespace(transform=lambda values: values.fillna(0).to_numpy())
        engine.scaler = SimpleNamespace(transform=lambda values: values.to_numpy())
        for output in (np.array([float("nan")]), np.array([1., 2.]), np.array([[1.]])):
            engine.estimator = SimpleNamespace(predict=lambda values, result=output: result)
            with self.assertRaisesRegex(RuntimeError, "non-finite prediction"):
                engine.predict_log10(engine.default_inputs[:1])


class PartialInputContract(unittest.TestCase):
    def setUp(self):
        self.engine = fixture_engine()

    def test_one_ten_and_fifty_two_at_default_values_remain_exact_subsets(self):
        for count in (1, 10, 52):
            with self.subTest(count=count):
                inputs = list(reversed(copy.deepcopy(self.engine.default_inputs[:count])))
                result = self.engine.run("test", inputs)
                expected = list(self.engine.chemical_ids[:count])
                self.assertEqual([row["chemical"] for row in result["rows"]], expected)
                self.assertEqual([row["chemical"] for row in result["inputs"]], expected)
                self.assertEqual(len(result["rows"]), count)
                self.assertEqual(result["totals"]["ww"], count * (count + 1) / 2)

    def test_public_snapshot_does_not_expose_intermediate_or_comparison_fields(self):
        result = self.engine.run("test", self.engine.default_inputs[:10])
        self.assertEqual(set(result), {"id", "createdAt", "modelVersion", "dataVersion", "inputs", "rows", "totals"})
        self.assertEqual(set(result["totals"]), {"ww", "beq"})
        for row in result["rows"]:
            self.assertEqual(set(row), {"chemical", "ww", "beq", "beqRank", "beqContribution"})

    def test_contribution_denominator_and_rank_use_only_submitted_chemicals(self):
        result = self.engine.run("test", self.engine.default_inputs[:10])
        total = math.fsum(row["beq"] for row in result["rows"])
        self.assertEqual(result["totals"]["beq"], total)
        self.assertAlmostEqual(math.fsum(row["beqContribution"] for row in result["rows"]), 100.)
        for row in result["rows"]:
            self.assertAlmostEqual(row["beqContribution"], row["beq"] / total * 100.)
            self.assertEqual(row["beqRank"], 1 + sum(other["beq"] > row["beq"] for other in result["rows"]))
        singleton = self.engine.run("singleton", self.engine.default_inputs[:1])["rows"][0]
        self.assertEqual(singleton["beqRank"], 1)
        self.assertEqual(singleton["beqContribution"], 100.)

    def test_scientific_translation_formula_is_unchanged(self):
        internal = self.engine.evaluate(self.engine.default_inputs[:10])
        for row in internal["rows"]:
            expected_cb = (row["ww"] / 70.) / math.log(2.)
            self.assertAlmostEqual(row["de"], row["ww"])
            self.assertAlmostEqual(row["cb"], expected_cb)
            self.assertAlmostEqual(row["beq"], expected_cb * .5 * 307.25)

    def test_ties_use_competition_rank(self):
        inputs = [{"chemical": key, "ww": 5.} for key in self.engine.chemical_ids[:3]]
        result = self.engine.run("ties", inputs)
        self.assertEqual([row["beqRank"] for row in result["rows"]], [1, 1, 1])

    def test_default_numeric_value_does_not_infer_example_origin(self):
        result = self.engine.run("user", self.engine.default_inputs[:1])
        self.assertEqual(result["inputs"][0]["origin"], "user")
        supplied = [{**self.engine.default_inputs[0], "origin": "example"}]
        self.assertEqual(self.engine.run("example", supplied)["inputs"][0]["origin"], "example")

    def test_request_and_returned_snapshots_are_independent(self):
        inputs = copy.deepcopy(self.engine.default_inputs[:2])
        result = self.engine.run("first", inputs)
        original = copy.deepcopy(result)
        inputs[0]["ww"] = 9999.
        self.engine.run("second", inputs)
        self.assertEqual(result, original)
        result["inputs"][0]["ww"] = 42.
        self.assertEqual(inputs[0]["ww"], 9999.)

    def test_invalid_counts_unknown_and_duplicate_are_rejected(self):
        invalid = [[], self.engine.default_inputs + [self.engine.default_inputs[0]],
                   [{"chemical": "unknown", "ww": 1}],
                   [self.engine.default_inputs[0], self.engine.default_inputs[0]]]
        for inputs in invalid:
            with self.subTest(inputs=inputs):
                with self.assertRaises(ValueError):
                    self.engine.validate_inputs({"inputs": inputs})

    def test_invalid_concentrations_are_rejected(self):
        for value in (None, "", "1", False, True, 0, -1, float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.engine.validate_inputs({"inputs": [{"chemical": self.engine.chemical_ids[0], "ww": value}]})

    def test_unknown_fields_and_invalid_origins_are_rejected(self):
        row = self.engine.default_inputs[0]
        payloads = [{"inputs": [row], "weight": 80}, {"inputs": [{**row, "REP": 1}]}]
        payloads += [{"inputs": [{**row, "origin": value}]} for value in (None, 1, "default", "")]
        for payload in payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    self.engine.validate_inputs(payload)


class ExcelPreviewContract(unittest.TestCase):
    def test_preserves_first_sheet_headers_blanks_and_numeric_values(self):
        body = workbook_bytes([["Chemical", "WW input (nM)"], ["BIT", 12.5], [None, 0], ["Unknown", -1]], [["Other", 999]])
        self.assertEqual(read_workbook(body), {"sheet": "Concentrations", "rows": [["Chemical", "WW input (nM)"], ["BIT", 12.5], [None, 0], ["Unknown", -1]]})

    def test_formula_without_cached_value_remains_unfilled(self):
        result = read_workbook(workbook_bytes([["BIT", "=1+2"], ["Date", date(2026, 10, 9)]]))
        self.assertEqual(result["rows"][0], ["BIT"])
        self.assertEqual(result["rows"][1][1], "2026-10-09T00:00:00")

    def test_empty_and_malformed_workbooks_are_rejected(self):
        for body in (b"", b"old xls contents", workbook_bytes([])):
            with self.subTest(size=len(body)):
                with self.assertRaises(ValueError):
                    read_workbook(body)

    def test_row_and_column_limits(self):
        for rows in ([["x"]] * 5001, [list(range(21))]):
            with self.assertRaisesRegex(ValueError, "5,000 rows and 20 columns"):
                read_workbook(workbook_bytes(rows))

    def test_uncompressed_archive_limit(self):
        output = BytesIO()
        with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("oversized.xml", b" " * (MAX_UNCOMPRESSED_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "too large"):
            read_workbook(output.getvalue())


class HTTPContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = RunService()
        cls.service.status = "ready"
        cls.service.engine = fixture_engine()
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        cls.http = create_server({"port": port}, cls.service)
        cls.base = f"http://127.0.0.1:{port}"
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join(timeout=5)

    def request(self, path, body=None, media_type="application/json", headers=None):
        request = urllib.request.Request(self.base + path, data=body, headers={"Content-Type": media_type, **(headers or {})})
        try:
            response = urllib.request.urlopen(request, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read())

    def test_http_accepts_partial_payload_and_preserves_canonical_snapshot(self):
        payload = {"inputs": list(reversed(self.service.engine.default_inputs[:10]))}
        status, submitted = self.request("/api/runs", json.dumps(payload).encode())
        self.assertEqual(status, 202)
        run_id, queued_inputs = self.service.pending.get_nowait()
        self.assertEqual(submitted["id"], run_id)
        self.assertEqual(len(queued_inputs), 10)
        result = self.service.engine.run(run_id, queued_inputs)
        self.service.jobs[run_id].update(status="succeeded", result=result)
        delivered = self.service.get_job(run_id)
        delivered["result"]["rows"][0]["beq"] = -1
        status, polled = self.request("/api/runs/" + run_id)
        self.assertEqual(status, 200)
        self.assertEqual(polled["result"], result)

    def test_http_import_works_while_model_loading(self):
        self.service.status = "loading"
        try:
            status, result = self.request("/api/import", workbook_bytes([["BIT", 5]]), XLSX_MEDIA_TYPE)
            self.assertEqual(status, 200)
            self.assertEqual(result["rows"], [["BIT", 5]])
        finally:
            self.service.status = "ready"

    def test_http_import_rejects_wrong_type_bad_workbook_and_foreign_origin(self):
        self.assertEqual(self.request("/api/import", b"bad", "text/plain")[0], 415)
        self.assertEqual(self.request("/api/import", b"bad", XLSX_MEDIA_TYPE)[0], 422)
        self.assertEqual(self.request("/api/import", b"bad", XLSX_MEDIA_TYPE, {"Origin": "https://example.invalid"})[0], 403)


if __name__ == "__main__":
    unittest.main()
