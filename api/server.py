"""Loopback-only WPN API and static website; one CPU worker, no model training."""
from __future__ import annotations

from datetime import datetime, timezone
STARTED_AT = datetime.now(timezone.utc).isoformat()

import argparse
import atexit
import copy
import json
import mimetypes
import os
from pathlib import Path
import queue
import socket
import threading
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

from engine import ROOT, WPNEngine
from import_excel import MAX_UPLOAD_BYTES, XLSX_MEDIA_TYPE, read_workbook


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail
        super().__init__(detail)


class RunService:
    def __init__(self):
        self.lock = threading.RLock()
        self.jobs = {}
        self.pending = queue.Queue(maxsize=16)
        self.engine = None
        self.status = "loading"
        self.message = "Loading the WPN model."
        config = json.loads((ROOT / "api/config.json").read_text(encoding="utf-8-sig"))
        self.model_version = config["modelLabel"] + " / " + config["modelSHA256"][:12]
        self.maximum_jobs = int(config.get("maximumRetainedRuns", 128))

    def start(self):
        threading.Thread(target=self.worker, name="wpn-single-cpu-worker", daemon=True).start()

    def worker(self):
        try:
            engine = WPNEngine()
            engine.initialize()
            with self.lock:
                self.engine = engine
                self.status = "ready"
                self.message = "WPN is ready."
        except Exception as error:
            traceback.print_exc()
            with self.lock:
                self.status = "error"
                self.message = f"Model initialization failed: {error}"
            return
        while True:
            run_id, inputs = self.pending.get()
            with self.lock:
                self.jobs[run_id].update(status="running", message=f"Calculating results for {len(inputs)} chemicals.")
            try:
                result = engine.run(run_id, inputs)
                with self.lock:
                    self.jobs[run_id].update(status="succeeded", message="Prediction completed.", result=result)
            except Exception as error:
                traceback.print_exc()
                with self.lock:
                    self.jobs[run_id].update(status="failed", message=f"Prediction failed: {error}")
            finally:
                self.pending.task_done()
                with self.lock:
                    while len(self.jobs) > self.maximum_jobs:
                        old_id = next((key for key, job in self.jobs.items() if job["status"] in {"succeeded", "failed"}), None)
                        if old_id is None:
                            break
                        del self.jobs[old_id]

    def health(self):
        with self.lock:
            return {"status": self.status, "message": self.message, "modelVersion": self.model_version}

    def submit(self, payload):
        with self.lock:
            if self.status != "ready":
                raise HTTPException(status_code=503, detail=self.message)
            try:
                inputs = self.engine.validate_inputs(payload)
            except (ValueError, TypeError, OverflowError) as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
            run_id = uuid.uuid4().hex
            job = {"id": run_id, "status": "queued", "message": "Waiting for the local CPU worker."}
            self.jobs[run_id] = job
            try:
                self.pending.put_nowait((run_id, inputs))
            except queue.Full:
                del self.jobs[run_id]
                raise HTTPException(status_code=429, detail="The local prediction queue is full; please wait for existing runs.") from None
            return {"id": run_id, "status": "queued"}

    def get_job(self, run_id):
        with self.lock:
            if run_id not in self.jobs:
                raise HTTPException(status_code=404, detail="This local run is unavailable. Runs are kept in memory for this session.")
            return copy.deepcopy(self.jobs[run_id])


def create_server(identity, service=None):
    service = service or RunService()
    dist = (ROOT / "dist").resolve()
    allowed_hosts = {f"127.0.0.1:{identity['port']}", f"localhost:{identity['port']}"}

    class Handler(BaseHTTPRequestHandler):
        # HTTP/1.0 closes each connection, so invalid request bodies cannot be reused.
        server_version = "WPNLocal/1.0"

        def setup(self):
            super().setup()
            self.connection.settimeout(20)

        def headers_for(self, status, length, media_type):
            self.send_response(status)
            self.send_header("Content-Type", media_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store" if self.path.startswith(("/api/", "/__local/")) else "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()

        def json_response(self, value, status=200):
            body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.headers_for(status, len(body), "application/json; charset=utf-8")
            if self.command != "HEAD":
                self.wfile.write(body)

        def read_body(self, maximum):
            if self.headers.get("Transfer-Encoding"):
                raise HTTPException(400, "Transfer encoding is unsupported; send a body with Content-Length.")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise HTTPException(400, "Invalid Content-Length.") from None
            if length > maximum:
                raise HTTPException(413, "The upload is too large." if maximum == MAX_UPLOAD_BYTES else "The concentration request is too large.")
            if length <= 0:
                raise HTTPException(422, "A request body is required.")
            body = self.rfile.read(length)
            if len(body) != length:
                raise HTTPException(400, "The request body is incomplete.")
            return body

        def dispatch(self):
            try:
                if self.headers.get("Host", "").lower() not in allowed_hosts:
                    raise HTTPException(403, "Only the loopback website host is allowed.")
                path = unquote(urlsplit(self.path).path, errors="strict").replace("\\", "/")
                if "\x00" in path:
                    raise HTTPException(400, "Invalid path.")
                origin = self.headers.get("Origin")
                if path.startswith("/api/") and origin and origin not in {f"http://{host}" for host in allowed_hosts}:
                    raise HTTPException(403, "Only this local website may call the model API.")
                if self.command in {"GET", "HEAD"}:
                    if path == "/__local/status":
                        return self.json_response(identity)
                    if path == "/api/health":
                        return self.json_response(service.health())
                    if path.startswith("/api/runs/"):
                        return self.json_response(service.get_job(path.removeprefix("/api/runs/")))
                    if path.startswith(("/api/", "/__local/")):
                        raise HTTPException(404, "Unknown local API route.")
                    return self.website(path.lstrip("/"))
                if self.command == "POST" and path == "/api/import":
                    if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != XLSX_MEDIA_TYPE:
                        raise HTTPException(415, "Choose an Excel .xlsx file.")
                    body = self.read_body(MAX_UPLOAD_BYTES)
                    try:
                        preview = read_workbook(body)
                    except ValueError as error:
                        raise HTTPException(422, str(error)) from error
                    return self.json_response(preview)
                if self.command == "POST" and path == "/api/runs":
                    if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                        raise HTTPException(415, "The request must use application/json.")
                    body = self.read_body(65536)
                    try:
                        payload = json.loads(body)
                    except (ValueError, UnicodeDecodeError):
                        raise HTTPException(422, "The request is not valid JSON.") from None
                    return self.json_response(service.submit(payload), 202)
                raise HTTPException(405, "This route does not support the requested method.")
            except HTTPException as error:
                self.json_response({"detail": error.detail}, error.status_code)
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                pass
            except (UnicodeError, ValueError):
                self.json_response({"detail": "Invalid request."}, 400)
            except Exception:
                traceback.print_exc()
                self.json_response({"detail": "The local server could not handle this request."}, 500)

        def website(self, requested):
            candidate = (dist / requested).resolve()
            if not candidate.is_relative_to(dist):
                raise HTTPException(404, "Not found.")
            if candidate.is_dir():
                candidate = candidate / "index.html"
            if not candidate.is_file():
                static_prefix = requested.split("/", 1)[0].lower() in {"assets", "data", "datasets", "figures", "downloads", "notices", "fonts", "images", "media"}
                if static_prefix or Path(requested).suffix:
                    raise HTTPException(404, "Not found.")
                candidate = dist / "index.html"
            if not candidate.is_file():
                raise HTTPException(503, "The local website has not been built. Please rebuild it before opening the interface.")
            media_type = {".bin": "application/octet-stream", ".gz": "application/gzip", ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json"}.get(candidate.suffix.lower()) or mimetypes.guess_type(candidate)[0] or "application/octet-stream"
            with candidate.open("rb") as handle:
                self.headers_for(200, os.fstat(handle.fileno()).st_size, media_type)
                if self.command != "HEAD":
                    for chunk in iter(lambda: handle.read(256 * 1024), b""):
                        self.wfile.write(chunk)

        do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = dispatch

    class LocalServer(ThreadingHTTPServer):
        daemon_threads = True
        allow_reuse_address = False

        def server_bind(self):
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()

    server = LocalServer(("127.0.0.1", identity["port"]), Handler)
    server.service = service
    return server


def main():
    parser = argparse.ArgumentParser(description="Serve the local WPN model platform.")
    parser.add_argument("--port", type=int, default=4174)
    parser.add_argument("--no-state", action="store_true", help="For isolated test ports only: do not replace the site's launcher PID record.")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("The loopback port must be between 1024 and 65535.")
    config_file = ROOT / "项目配置.json"
    display_name = "WPN model platform"
    if config_file.exists():
        display_name = json.loads(config_file.read_text(encoding="utf-8-sig")).get("name") or display_name
    identity = {"app": "paper-platform-local", "name": display_name, "port": args.port, "home": "/", "projectRoot": str(ROOT),
                "serverPath": str(Path(__file__).resolve()), "pid": os.getpid(), "startedAt": STARTED_AT}
    state_file = ROOT / ".runtime/server.pid.json"
    # Bind before writing launcher state or initializing the model. A busy port is never taken over.
    try:
        server = create_server(identity)
    except OSError as error:
        raise SystemExit(f"Local port {args.port} is unavailable: {error}") from error
    if not args.no_state:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(identity, ensure_ascii=False, indent=2), encoding="utf-8")

    def cleanup():
        if args.no_state:
            return
        try:
            current = json.loads(state_file.read_text(encoding="utf-8-sig"))
            if current.get("pid") == os.getpid() and current.get("serverPath") == identity["serverPath"]:
                state_file.unlink()
        except (OSError, ValueError):
            pass

    atexit.register(cleanup)
    server.service.start()
    print(f"WPN local website: http://127.0.0.1:{args.port}/", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        cleanup()


if __name__ == "__main__":
    main()
