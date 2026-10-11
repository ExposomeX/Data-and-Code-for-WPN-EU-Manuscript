"""Exercise a relocated, offline CPU website with real model predictions.

Run with .venv/Scripts/python.exe tools/validate_portable_site.py. This copies
runtime resources into a temporary Chinese path containing spaces, starts its
own loopback server, and removes the temporary copy after the worker exits. It
does not call the existing website, launch a browser, or retrain a model.

Python audit hooks deny non-loopback networking, original project resources,
and other non-runtime files. They are process-level instrumentation, not an OS
firewall or a second-computer test. The installed Python runtime is reused;
project models, parameters and website resources must come from the copy.
Results print to stdout. Only an explicit --output saves a report, under
.runtime/checks. Real inference can take several minutes.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
from io import BytesIO
import ipaddress
import json
import math
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RESULT_MARKER = "WPN_PORTABLE_RESULT="
TEMP_PREFIX = "WPN 离线迁移验证 "


def progress(message):
    print(message, file=sys.stderr, flush=True)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def normalized(path):
    return os.path.normcase(os.path.realpath(os.fsdecode(path)))


def within(path, directory):
    return path == directory or path.startswith(directory + os.sep)


class IsolationGuard:
    """Guard Python file/socket operations in the disposable worker only."""

    def __init__(self, source, temporary):
        self.source = normalized(source)
        self.temporary = normalized(temporary)
        self.runtime_roots = tuple(dict.fromkeys(normalized(path) for path in (sys.prefix, sys.base_prefix)))
        self.windows = normalized(os.environ.get("SystemRoot", r"C:\Windows"))
        self.base_site_packages = normalized(Path(sys.base_prefix) / "Lib/site-packages")
        self.phase = "probe"
        self.events = Counter()
        self.denied = []
        self.file_reads = Counter()
        self.optional_system_probes = 0
        self.original_project_attempts = 0

    def deny(self, event, target):
        self.events[f"{self.phase}:denied:{event}"] += 1
        entry = {"phase": self.phase, "event": event, "target": str(target)}
        if event == "subprocess.Popen":
            frame = sys._getframe(1)
            entry["callers"] = []
            for _ in range(10):
                if frame is None:
                    break
                entry["callers"].append({"file": frame.f_code.co_filename, "line": frame.f_lineno, "function": frame.f_code.co_name})
                frame = frame.f_back
            # NumPy 1.26 probes Linux SVE instructions even on Windows and
            # catches OSError to return False. Keep it blocked; this narrow,
            # identified optional probe is not a website/runtime dependency.
            numpy_probe = normalized(Path(sys.prefix) / "Lib/site-packages/numpy/testing/_private/utils.py")
            optional = self.phase == "runtime" and target.get("arguments") == "lscpu" and any(
                caller["function"] == "check_support_sve" and normalized(caller["file"]) == numpy_probe
                for caller in entry["callers"]
            )
            if optional:
                self.optional_system_probes += 1
                entry["classification"] = "Blocked optional NumPy SVE CPU probe; its normal OSError fallback returns False."
        if len(self.denied) < 30:
            self.denied.append(entry)
        raise PermissionError(f"Offline relocation guard denied {event}: {target}")

    def file(self, event, raw, writing=False):
        if not isinstance(raw, (str, bytes, os.PathLike)):
            return
        path = normalized(raw)
        if path == normalized(os.devnull):
            return
        if within(path, self.temporary):
            group = "temporary_copy"
        elif writing:
            return self.deny(event, path)
        elif within(path, self.source) and not within(path, self.runtime_roots[0]):
            if self.phase == "runtime":
                self.original_project_attempts += 1
            return self.deny(event, path)
        elif within(path, self.base_site_packages) and not within(path, self.runtime_roots[0]):
            return self.deny(event, path)
        elif any(within(path, root) for root in self.runtime_roots):
            group = "installed_python_runtime"
        elif within(path, self.windows):
            group = "windows_runtime"
        else:
            return self.deny(event, path)
        if not writing:
            self.file_reads[group] += 1

    def network(self, event, host):
        if isinstance(host, bytes):
            host = host.decode("ascii", errors="replace")
        allowed = str(host).lower() == "localhost"
        if not allowed:
            try:
                allowed = ipaddress.ip_address(host).is_loopback
            except ValueError:
                allowed = False
        if not allowed:
            self.deny(event, host)
        self.events[f"{self.phase}:allowed_loopback:{event}"] += 1

    def __call__(self, event, args):
        if event == "open":
            mode, flags = args[1:3]
            writing = (isinstance(mode, str) and any(char in mode for char in "wax+")) or bool(
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
            )
            self.file(event, args[0], writing)
        elif event in {"os.listdir", "os.scandir"} and args and args[0] is not None:
            self.file(event, args[0])
        elif event in {"os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.utime", "os.truncate"}:
            self.file(event, args[0], writing=True)
        elif event in {"os.rename", "os.link", "os.symlink"}:
            self.file(event, args[0], writing=True)
            self.file(event, args[1], writing=True)
        elif event in {"socket.connect", "socket.bind"}:
            self.network(event, args[1][0])
        elif event in {"socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr"}:
            self.network(event, args[0])
        elif event == "socket.getnameinfo":
            self.network(event, args[0][0])
        elif event == "socket.sendto":
            self.network(event, args[-1][0])
        elif event in {"subprocess.Popen", "os.system", "os.posix_spawn", "os.startfile"}:
            self.deny(event, {"executable": args[0], "arguments": args[1]} if event == "subprocess.Popen" else args[0])

    def probes(self, source):
        probes = [
            ("original_config", lambda: (source / "api/config.json").read_bytes()),
            ("original_model", lambda: (source / "local_code/models/model.joblib").read_bytes()),
            ("external_dns", lambda: socket.getaddrinfo("example.invalid", 443)),
        ]
        with socket.socket() as connection:
            probes.append(("external_connection", lambda: connection.connect(("203.0.113.1", 443))))
            for label, operation in probes:
                try:
                    operation()
                except PermissionError:
                    continue
                raise AssertionError(f"Isolation probe was not blocked: {label}")
        self.phase = "runtime"
        return [label for label, _ in probes]

    def report(self):
        denied = sum(value for key, value in self.events.items() if key.startswith("runtime:denied:"))
        return {"scope": "Python audit hooks; not an operating-system firewall",
                "runtimeRootsAllowed": list(self.runtime_roots),
                "originalResourcesAllowed": False,
                "freshTemporaryCaches": True,
                "events": dict(self.events), "fileAccessCounts": dict(self.file_reads),
                "blockedOperations": self.denied,
                "runtimeDeniedOperations": denied, "blockedOptionalSystemProbes": self.optional_system_probes,
                "unexpectedRuntimeDeniedOperations": denied - self.optional_system_probes,
                "originalProjectAccessAttempts": self.original_project_attempts,
                "externalNetworkAttempts": sum(value for key, value in self.events.items() if key.startswith("runtime:denied:socket."))}


class IndexResources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        value = attrs.get("src") if tag in {"script", "img"} else attrs.get("href") if tag == "link" else None
        if value and not value.startswith("data:"):
            self.paths.append(value)


def validate_worker(args):
    began = time.perf_counter()
    source = args.source.resolve()
    temporary = args.temporary.resolve()
    require(ROOT.is_relative_to(temporary), "The worker must run from its temporary copy.")
    require(" " in str(ROOT) and any(ord(char) > 127 for char in str(ROOT)), "The copied site path must contain spaces and Chinese text.")
    require(normalized(sys.prefix) == normalized(source / ".venv"), "Use the project's newly installed .venv runtime.")
    guard = IsolationGuard(source, temporary)
    report = {"status": "failed", "generatedAtUTC": datetime.now(timezone.utc).isoformat(),
              "testKind": "Same-computer relocated website with blocked external access",
              "copiedProject": str(ROOT), "originalProject": str(source), "pythonExecutable": sys.executable,
              "pythonVersion": sys.version, "platform": platform.platform(), "checks": [], "scenarios": []}
    http_server = None
    server_thread = None
    sys.addaudithook(guard)
    try:
        report["isolationProbes"] = guard.probes(source)
        progress("Isolation probes passed; loading the copied website on a separate loopback port.")
        sys.path.insert(0, str(ROOT / "api"))
        import engine as backend
        import server as website
        from import_excel import XLSX_MEDIA_TYPE

        require(backend.ROOT == ROOT, "The API must belong to the copied project.")
        require(Path(website.__file__).resolve() == ROOT / "api/server.py", "The copied HTTP server must be used.")
        prediction_calls = []
        original_predict = backend.WPNEngine.predict_log10

        def observed_predict(self, inputs):
            started = time.perf_counter()
            logs = original_predict(self, inputs)
            prediction_calls.append({"inputs": copy.deepcopy(inputs), "logs": [float(value) for value in logs],
                                     "seconds": time.perf_counter() - started})
            return logs

        backend.WPNEngine.predict_log10 = observed_predict
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        require(port != 4174, "The validation must never use the existing website's port.")
        identity = {"app": "paper-platform-local", "name": "WPN isolated validation", "port": port,
                    "home": "/", "projectRoot": str(ROOT), "serverPath": str(ROOT / "api/server.py"),
                    "pid": os.getpid(), "startedAt": report["generatedAtUTC"]}
        http_server = website.create_server(identity)
        # Suppress only repetitive access logs; responses and model behavior are unchanged.
        http_server.RequestHandlerClass.log_message = lambda self, *_: None
        server_thread = threading.Thread(target=http_server.serve_forever, kwargs={"poll_interval": .1}, daemon=True)
        server_thread.start()
        base = f"http://127.0.0.1:{port}"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        report["loopbackPort"] = port

        def request(path, payload=None, raw=None, media_type="application/json", expect=200):
            body = raw if raw is not None else json.dumps(payload).encode() if payload is not None else None
            headers = {"Content-Type": media_type} if body is not None else {}
            req = urllib.request.Request(base + path, data=body, headers=headers)
            try:
                response = opener.open(req, timeout=30)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                body = response.read()
                require(response.status == expect, f"{path}: expected {expect}, got {response.status}: {body[:200]!r}")
                if path.startswith(("/api/", "/__local/")):
                    require(response.headers.get("Cache-Control") == "no-store", f"The API response must not be cached: {path}")
                return json.loads(body)

        require(request("/__local/status") == identity, "The isolated server identity is incorrect.")
        index_bytes = (ROOT / "dist/index.html").read_bytes()
        parser = IndexResources()
        parser.feed(index_bytes.decode("utf-8-sig"))
        require(parser.paths, "The built index must reference its static assets.")
        for resource in parser.paths:
            parsed = urllib.parse.urlsplit(resource)
            require(not parsed.scheme and not parsed.netloc, f"The initial webpage requires an external resource: {resource}")
            target = (ROOT / "dist" / urllib.parse.unquote(parsed.path).lstrip("/")).resolve()
            require(target.is_relative_to(ROOT / "dist") and target.is_file(), f"Missing index resource: {resource}")
        routes = ["/", "/introduction/Description", "/introduction/Data?view=concentrations", "/introduction/Figure",
                  "/chemical/Description", "/chemical/Data", "/wpn/Data", "/wpn/Figure", "/rank/Figure?source=current"]
        for route in routes:
            with opener.open(base + route, timeout=30) as response:
                require(response.status == 200 and response.read() == index_bytes, f"SPA route did not serve the built website: {route}")
        asset_count = 0
        asset_bytes = 0
        for path in sorted((ROOT / "dist").rglob("*")):
            if not path.is_file():
                continue
            url = "/" + urllib.parse.quote(path.relative_to(ROOT / "dist").as_posix())
            received = hashlib.sha256()
            size = 0
            with opener.open(base + url, timeout=60) as response:
                require(response.status == 200, f"Static asset unavailable: {url}")
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    received.update(chunk)
                    size += len(chunk)
                require(size == int(response.headers["Content-Length"]), f"Incorrect length for {url}")
            require(received.hexdigest() == digest(path), f"Static bytes changed while served: {url}")
            asset_count += 1
            asset_bytes += size
        report["staticWebsite"] = {"spaRoutes": routes, "filesServedAndHashed": asset_count, "bytesServed": asset_bytes,
                                   "browserRenderingTested": False}
        report["checks"].append("Built SPA routes and every packaged static resource are served from the relocated copy with matching bytes.")
        progress(f"Static website passed: {asset_count} files, {asset_bytes:,} bytes. Starting the real CPU model.")

        loading = time.perf_counter()
        http_server.service.start()
        while True:
            health = request("/api/health")
            if health["status"] == "ready":
                break
            require(health["status"] != "error", health["message"])
            require(time.perf_counter() - loading < args.timeout, "Model loading exceeded the validation timeout.")
            time.sleep(.5)
        model = http_server.service.engine
        report["modelLoadSeconds"] = time.perf_counter() - loading
        require(model.runtime["device"] == "cpu", "The website must use CPU inference.")
        require(model.torch.version.cuda is None and not model.torch.cuda.is_initialized(), "The installed PyTorch must be CPU-only.")
        require(all(str(device) == "cpu" for device in model.estimator.devices_), "All estimator devices must be CPU.")
        require(model.package_root == ROOT / "local_code", "The model loader must use the copied local_code directory.")
        report["modelSHA256"] = model.config["modelSHA256"]
        report["checkpointSHA256"] = model.config["checkpointSHA256"]
        report["modelVersion"] = model.model_version
        report["runtime"] = {**model.runtime, "torchCUDA": model.torch.version.cuda,
                             "cudaInitialized": model.torch.cuda.is_initialized(), "estimatorDevices": [str(device) for device in model.estimator.devices_]}

        def no_fit(*_args, **_kwargs):
            raise AssertionError("The validation must never train or refit the model.")

        model.estimator.fit = no_fit
        progress(f"Real CPU model ready in {report['modelLoadSeconds']:.1f}s; testing input subsets.")

        def run_scenario(inputs, label):
            before = len(prediction_calls)
            started = time.perf_counter()
            queued = request("/api/runs", {"inputs": inputs}, expect=202)
            while True:
                job = request("/api/runs/" + queued["id"])
                if job["status"] in {"succeeded", "failed"}:
                    require(job["status"] == "succeeded", job["message"])
                    break
                require(time.perf_counter() - started < args.timeout, f"{label} exceeded the validation timeout.")
                time.sleep(.3)
            require(len(prediction_calls) == before + 1, "Each submitted job must perform exactly one model prediction.")
            result = job["result"]
            require(set(result) == {"id", "createdAt", "modelVersion", "dataVersion", "inputs", "rows", "totals"}, "Unexpected public result fields.")
            expected = sorted([{"chemical": row["chemical"], "ww": float(row["ww"]), "origin": row.get("origin", "user")} for row in inputs], key=lambda row: row["chemical"])
            require(result["inputs"] == expected, "Submitted inputs or origins were changed.")
            require([row["chemical"] for row in result["rows"]] == [row["chemical"] for row in expected], "Unsubmitted chemicals were added or submitted chemicals were omitted.")
            require(set(result["totals"]) == {"ww", "beq"}, "Unexpected public totals.")
            logs = {row["chemical"]: value for row, value in zip(prediction_calls[-1]["inputs"], prediction_calls[-1]["logs"])}
            ww = {row["chemical"]: row["ww"] for row in expected}
            maximum_formula_relative_difference = 0.
            for row in result["rows"]:
                require(set(row) == {"chemical", "ww", "beq", "beqRank", "beqContribution"}, "Internal exposure or model parameters escaped the API.")
                require(row["ww"] == ww[row["chemical"]], "Input concentrations changed.")
                parameter = model.parameters[row["chemical"]]
                de = 10. ** logs[row["chemical"]]
                cb = de * (float(parameter["t0.5_adme"]) / 24.) / (70. * 10. ** float(parameter["logVDss_adme"]) * math.log(2.))
                expected_beq = cb * float(parameter["REP"]) * 307.25
                require(all(math.isfinite(value) and value > 0 for value in (de, cb, row["beq"], expected_beq)), "Non-finite or nonpositive scientific result.")
                difference = abs(row["beq"] / expected_beq - 1.)
                maximum_formula_relative_difference = max(maximum_formula_relative_difference, difference)
                require(difference <= 1e-12, "BEQ differs from the independent formula reconstruction.")
                require(row["beqRank"] == 1 + sum(other["beq"] > row["beq"] for other in result["rows"]), "BEQ ranking is incorrect.")
                require(row["beqContribution"] == row["beq"] / result["totals"]["beq"] * 100., "The contribution denominator is incorrect.")
            require(math.isclose(math.fsum(row["beqContribution"] for row in result["rows"]), 100., abs_tol=1e-10), "Contributions must sum to 100 percent.")
            for metric in ("ww", "beq"):
                require(math.fsum(row[metric] for row in result["rows"]) == result["totals"][metric], f"Incorrect {metric} total.")
            details = {"name": label, "submitted": len(inputs), "returned": len(result["rows"]),
                       "httpSeconds": time.perf_counter() - started, "predictionSeconds": prediction_calls[-1]["seconds"],
                       "maximumFormulaRelativeDifference": maximum_formula_relative_difference}
            report["scenarios"].append(details)
            progress(f"{label}: {len(result['rows'])} rows passed in {details['httpSeconds']:.1f}s.")
            return result

        snapshots = {}
        for count in (1, 10, 52):
            inputs = [{**row, "origin": "example"} for row in reversed(model.default_inputs[:count])]
            snapshots[count] = run_scenario(inputs, f"Example subset {count}")
        full = {row["chemical"]: row["beq"] for row in snapshots[52]["rows"]}
        subset_delta = max(abs(math.log10(row["beq"]) - math.log10(full[row["chemical"]]))
                           for count in (1, 10) for row in snapshots[count]["rows"])
        require(subset_delta <= args.max_log10_difference, "CPU subset/full batch difference exceeds the replay tolerance.")
        report["maximumSubsetVsFullLog10BEQDifference"] = subset_delta
        report["allowedLog10ReplayDifference"] = args.max_log10_difference

        frozen_path = ROOT / "dist/downloads/city-metrics-nt52-a2.csv"
        frozen_hash = digest(frozen_path)
        grouped = defaultdict(list)
        for row in backend.read_csv(frozen_path):
            grouped[row["GUB_city_unit"]].append(row)
        city = sorted(grouped)[0]
        rows = grouped[city]
        replay = run_scenario([{"chemical": row["StdInChIKey"], "ww": float(row["ww_concentration_nM"])} for row in rows], "Frozen city replay")
        reference = {row["StdInChIKey"]: float(row["BEQ (ug/L Narciclasine-EQ)_one_compartment"]) for row in rows}
        replay_delta = max(abs(math.log10(row["beq"]) - math.log10(reference[row["chemical"]])) for row in replay["rows"])
        require(replay_delta <= args.max_log10_difference, "Frozen city replay exceeds the numerical tolerance.")
        require(digest(frozen_path) == frozen_hash, "The frozen reference data changed.")
        report["frozenReplay"] = {"city": city, "rows": len(rows), "maximumLog10BEQDifference": replay_delta, "sourceSHA256": frozen_hash}
        report["checks"].append("Real 1/10/52-input HTTP predictions preserve inputs, return only selected chemicals, obey the original BEQ formula, and sum to 100 percent.")
        report["checks"].append("One 52-chemical frozen city is reproduced within the documented numerical replay tolerance; no historical validation report or GPU service is consulted.")

        first = model.default_inputs[0]
        invalid = [{"inputs": []}, {"inputs": [first, first]}, {"inputs": [{"chemical": "unknown", "ww": 1}]},
                   {"inputs": [first], "parameters": {}}, {"inputs": [{**first, "extra": 1}]},
                   {"inputs": [{**first, "origin": "unexpected"}]}]
        invalid.extend({"inputs": [{**first, "ww": value}]} for value in (0, -1, None, True, "1", float("nan"), float("inf")))
        for payload in invalid:
            require("detail" in request("/api/runs", payload, expect=422), "Invalid inputs must return a readable 422 error.")
        require("detail" in request("/api/runs", raw=b"{", expect=422), "Malformed JSON must be rejected.")
        report["rejectedInputRequests"] = len(invalid) + 1

        from openpyxl import Workbook
        workbook = Workbook()
        workbook.active.title = "WW concentrations"
        matrix = [["Chemical", "WW input (nM)"], [first["chemical"], 12.5], ["Unknown entry", "check"]]
        for row in matrix:
            workbook.active.append(row)
        workbook.create_sheet("Ignored").append(["Not the first sheet", 999])
        binary = BytesIO()
        workbook.save(binary)
        workbook.close()
        preview = request("/api/import", raw=binary.getvalue(), media_type=XLSX_MEDIA_TYPE)
        require(preview == {"sheet": "WW concentrations", "rows": matrix}, "Excel preview must preserve first-sheet rows and values, including invalid entries.")
        require("detail" in request("/api/import", raw=b"not a workbook", media_type=XLSX_MEDIA_TYPE, expect=422), "Malformed Excel must be rejected.")
        report["excelImport"] = {"validWorkbookStatus": 200, "malformedWorkbookStatus": 422, "previewRowsPreserved": len(matrix)}
        for snapshot in [*snapshots.values(), replay]:
            require(request("/api/runs/" + snapshot["id"])["result"] == snapshot, "An earlier result snapshot changed.")
        require(len(prediction_calls) == 4, "Imports and rejected inputs must not submit extra inference jobs.")
        model.verify_artifacts()
        require(not (ROOT / ".runtime/server.pid.json").exists(), "The isolated test must not write launcher state.")
        require(not (ROOT / "local_code/inputs").exists() and not (ROOT / "local_code/results").exists(), "User input/results must not be copied or modified.")
        report["checks"].append("Excel import preserves rows for preview, 14 invalid JSON input requests and malformed Excel return 422, and stored snapshots remain unchanged.")
        report["realPredictionCalls"] = len(prediction_calls)
        report["realPredictionRows"] = sum(len(call["inputs"]) for call in prediction_calls)
        require(guard.report()["unexpectedRuntimeDeniedOperations"] == 0, "The website attempted an unexpected original-file, external-network, or subprocess operation.")
        report["checks"].append("External networking and original project resources remain blocked; only NumPy's identified optional lscpu probe may be blocked with its normal fallback.")
        report["status"] = "passed"
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
        report["traceback"] = traceback.format_exc()
        progress(report["error"])
    finally:
        if http_server is not None:
            http_server.shutdown()
            http_server.server_close()
        if server_thread is not None:
            server_thread.join(timeout=5)
        report["isolation"] = guard.report()
        report["workerSeconds"] = time.perf_counter() - began
        print(RESULT_MARKER + json.dumps(report, ensure_ascii=False, allow_nan=False), flush=True)
    return 0 if report["status"] == "passed" else 1


def validate_controller(args):
    began = time.perf_counter()
    require(os.name == "nt" and platform.architecture()[0] == "64bit", "This validation targets 64-bit Windows.")
    python = ROOT / ".venv/Scripts/python.exe"
    require(python.is_file(), "Install the project CPU .venv before running this validation.")
    require((ROOT / "dist/index.html").is_file(), "Build the website before relocation validation.")
    output = None
    if args.output is not None:
        output = args.output.resolve()
        require(output.is_relative_to((ROOT / ".runtime/checks").resolve()), "Reports may be saved only under .runtime/checks.")
    temporary = Path(tempfile.mkdtemp(prefix=TEMP_PREFIX)).resolve()
    clone = temporary / "独立 交付网站"
    process = None
    report = None
    try:
        progress("Copying runtime resources to a temporary Chinese path with spaces; user inputs and results are excluded.")
        ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".venv", ".runtime", ".git", "inputs", "results")
        for directory in ("api", "local_code", "dist"):
            shutil.copytree(ROOT / directory, clone / directory, ignore=ignore)
        config = ROOT / "项目配置.json"
        if config.is_file():
            shutil.copy2(config, clone / config.name)
        (clone / "tools").mkdir()
        worker = clone / "tools/validate_portable_site.py"
        shutil.copy2(Path(__file__).resolve(), worker)
        copied_files = [path for path in clone.rglob("*") if path.is_file()]
        copy_bytes = sum(path.stat().st_size for path in copied_files)
        environment = dict(os.environ)
        for key in ("PYTHONPATH", "PYTHONHOME", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            environment.pop(key, None)
        cache = temporary / "empty caches"
        cache.mkdir()
        for key in ("HOME", "USERPROFILE", "TEMP", "TMP", "XDG_CACHE_HOME", "HF_HOME", "TORCH_HOME", "MPLCONFIGDIR", "TABPFN_MODEL_CACHE_DIR"):
            environment[key] = str(cache)
        environment.update(PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                           HF_HUB_DISABLE_TELEMETRY="1", TABPFN_DISABLE_TELEMETRY="1", DO_NOT_TRACK="1", CUDA_VISIBLE_DEVICES="-1")
        command = [str(python), "-I", "-B", "-X", "utf8", str(worker), "--worker", "--source", str(ROOT), "--temporary", str(temporary),
                   "--timeout", str(args.timeout), "--max-log10-difference", str(args.max_log10_difference)]
        process = subprocess.Popen(command, cwd=clone, env=environment, stdout=subprocess.PIPE, stderr=None,
                                   text=True, encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            stdout, _ = process.communicate(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, _ = process.communicate(timeout=30)
            raise TimeoutError(f"The isolated worker exceeded {args.timeout} seconds. It was terminated without affecting the existing website.") from None
        lines = [line[len(RESULT_MARKER):] for line in stdout.splitlines() if line.startswith(RESULT_MARKER)]
        require(len(lines) == 1, f"The isolated worker did not return one result (exit {process.returncode}): {stdout[-2000:]}")
        report = json.loads(lines[0])
        require((process.returncode == 0) == (report["status"] == "passed"), "Worker exit status and report disagree.")
        report["copiedFileCount"] = len(copied_files)
        report["copiedBytes"] = copy_bytes
    except Exception as error:
        report = {"status": "failed", "error": f"{type(error).__name__}: {error}", "traceback": traceback.format_exc()}
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=15)
        # Check the final absolute target before removing this script's own copy.
        require(temporary.parent == Path(tempfile.gettempdir()).resolve() and temporary.name.startswith(TEMP_PREFIX)
                and temporary != ROOT and not ROOT.is_relative_to(temporary), "Refusing to remove an unexpected temporary path.")
        shutil.rmtree(temporary)
    report["temporaryDirectoryRemoved"] = not temporary.exists()
    report["totalSeconds"] = time.perf_counter() - began
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    print(text, flush=True)
    return 0 if report["status"] == "passed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=1800, help="Maximum total worker seconds (default: 1800).")
    parser.add_argument("--max-log10-difference", type=float, default=.005, help="Numerical replay tolerance; not scientific uncertainty.")
    parser.add_argument("--output", type=Path, help="Optional report path inside .runtime/checks; otherwise stdout only.")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--source", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--temporary", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    require(args.timeout > 0 and args.max_log10_difference >= 0, "Timeout must be positive and tolerance nonnegative.")
    return validate_worker(args) if args.worker else validate_controller(args)


if __name__ == "__main__":
    raise SystemExit(main())
