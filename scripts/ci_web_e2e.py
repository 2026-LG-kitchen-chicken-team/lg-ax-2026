"""Run three browser E2E cases in an isolated Linux CI workspace; --probe never opens a browser."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web"
HOST = "127.0.0.1"


class CheckFailure(RuntimeError):
    """Only fixed non-sensitive reason codes are printed."""


def write_json(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    path.chmod(0o600)


def reserve_ports(count: int) -> list[int]:
    # Hold all sockets together so no port is selected twice. Never stop a listener.
    with contextlib.ExitStack() as stack:
        ports = []
        for _ in range(count):
            sock = stack.enter_context(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
            sock.bind((HOST, 0))
            ports.append(sock.getsockname()[1])
        return ports


def port_available(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((HOST, port))
        return True
    except OSError:
        return False


def request_json(url: str, *, token: str | None = None, origin: str | None = None,
                 method: str = "GET") -> tuple[int, dict]:
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    if origin:
        headers["Origin"] = origin
    request = Request(url, headers=headers, method=method, data=b"{}" if method == "POST" else None)
    if method == "POST":
        request.add_header("Content-Type", "application/json")
    # Never send an ephemeral credential through an environment HTTP proxy.
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(request, timeout=2) as response:
            return response.status, json.loads(response.read(1048576))
    except HTTPError as error:
        return error.code, json.loads(error.read(1048576))


def stop_child(process: subprocess.Popen) -> None:
    if os.name == "posix":
        # A separate session is created for every child. Kill only this helper's group,
        # including the Playwright workers/Chromium if a test run was interrupted.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        # Windows venv python.exe may be a redirector with an actual Python child.
        # Terminate this owned PID's tree, never a process selected by a name/port.
        subprocess.run(["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=False, timeout=10)
        if process.poll() is None:
            process.kill()
    process.wait(timeout=8)


def wait_ready(process: subprocess.Popen, url: str, *, json_health: bool = True) -> None:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise CheckFailure("owned_service_exited_before_ready")
        try:
            if json_health:
                status, value = request_json(url)
                if status == 200 and value.get("status") == "ok":
                    return
            else:
                with build_opener(ProxyHandler({})).open(url, timeout=2) as response:
                    if response.status == 200:
                        return
        except (OSError, URLError, ValueError):
            pass
        time.sleep(0.15)
    raise CheckFailure("owned_service_readiness_timeout")


def serve(kind: str, directory: Path, port: int, web_port: int) -> None:
    """Internal owned child. Exact origins apply only to this synthetic CI instance."""
    directory = directory.resolve()
    if not directory.is_relative_to(ROOT / "private") or not 1024 <= port <= 65535:
        raise CheckFailure("invalid_isolated_service_settings")
    import uvicorn
    if kind == "bootstrap":
        from lgax_api.server import app
    else:
        from lgax_api import workspace_server
        from lgax_api.workspace_auth import TokenRegistry
        workspace_server.ORIGINS = {f"http://{HOST}:{web_port}"}
        app = workspace_server.create_workspace_app(
            directory / "workspace.sqlite", TokenRegistry.from_file(directory / "server-credentials.json")
        )
    uvicorn.run(app, host=HOST, port=port, access_log=False, log_level="warning")


def config_files(directory: Path, ports: list[int]) -> tuple[Path, Path]:
    api_port, workspace_port, web_port = ports
    # Resolve installed JS packages from apps/web. Temporary configs stay in private,
    # and the tracked Vite/Playwright settings and existing dev services are untouched.
    web_json = json.dumps(WEB.as_posix())
    contracts_json = json.dumps((ROOT / "packages" / "contracts").as_posix())
    vite = directory / "vite.config.mjs"
    vite.write_text(f"""import {{ createRequire }} from 'node:module';
import {{ pathToFileURL }} from 'node:url';
const require = createRequire(pathToFileURL({web_json} + '/package.json'));
const {{ defineConfig }} = await import(pathToFileURL(require.resolve('vite')));
const {{ default: react }} = await import(pathToFileURL(require.resolve('@vitejs/plugin-react')));
export default defineConfig({{
  root: {web_json}, plugins: [react()],
  server: {{ host: '{HOST}', port: {web_port}, strictPort: true,
    fs: {{ allow: [{web_json}, {contracts_json}] }},
    proxy: {{ '/api/workspace': 'http://{HOST}:{workspace_port}',
      '/api': 'http://{HOST}:{api_port}', '/health': 'http://{HOST}:{api_port}' }}
  }}
}});
""", encoding="utf-8")
    playwright = directory / "playwright.config.mjs"
    playwright.write_text(f"""import {{ createRequire }} from 'node:module';
import {{ pathToFileURL }} from 'node:url';
const require = createRequire(pathToFileURL({web_json} + '/package.json'));
const {{ defineConfig }} = require('@playwright/test');
export default defineConfig({{
  testDir: {json.dumps((WEB / 'e2e').as_posix())}, testMatch: 'planner-flow.spec.ts',
  timeout: 60000, fullyParallel: false, workers: 1, retries: 0, forbidOnly: true,
  reporter: [['json', {{ outputFile: {json.dumps((directory / 'raw-report.json').as_posix())} }}]],
  outputDir: {json.dumps((directory / 'browser-output').as_posix())},
  use: {{ baseURL: 'http://{HOST}:{web_port}', browserName: 'chromium',
    acceptDownloads: true, viewport: {{ width: 1280, height: 900 }},
    trace: 'off', screenshot: 'off', video: 'off' }}
}});
""", encoding="utf-8")
    return vite, playwright


def browser_cases(raw: dict) -> list[dict]:
    """Publish known case labels and bounded statuses; never raw errors/requests/console."""
    labels = {
        "fixture: request questions": "fixture_planning",
        "fixture: a cancelled measurement": "fixture_unmeasured",
        "live: connect, save a request": "live_workspace",
    }
    allowed_statuses = {"passed", "failed", "timedOut", "skipped", "interrupted"}
    allowed_outcomes = {"expected", "unexpected", "flaky", "skipped"}
    result = []

    def visit(suites):
        for suite in suites:
            for spec in suite.get("specs", []):
                label = next((value for prefix, value in labels.items()
                              if spec.get("title", "").startswith(prefix)), "unrecognized_case")
                for test in spec.get("tests", []):
                    outcome = test.get("status")
                    result.append({
                        "case": label,
                        "outcome": outcome if outcome in allowed_outcomes else "unknown",
                        "results": [row.get("status") if row.get("status") in allowed_statuses else "unknown"
                                    for row in test.get("results", [])],
                    })
            visit(suite.get("suites", []))

    visit(raw.get("suites", []))
    return result


def run(*, probe: bool) -> dict:
    if not probe and not sys.platform.startswith("linux"):
        raise CheckFailure("browser_run_is_reserved_for_linux_ci_use_probe_locally")
    private = ROOT / "private"
    private.mkdir(exist_ok=True)
    private = private.resolve()
    if not private.is_relative_to(ROOT.resolve()):
        raise CheckFailure("private_directory_escapes_repository")
    report = {"schema_version": 1, "mode": "api_probe" if probe else "browser_e2e",
              "synthetic_data_only": True, "planning_agent_executed": False,
              "private_credentials": True, "screenshots_traces_videos": False,
              "status": "fail", "checks": {}, "browser_stats": None}
    children: list[subprocess.Popen] = []
    ports = reserve_ports(3)
    # The tmpdir and subprocess console/report are never uploaded as artifacts.
    with tempfile.TemporaryDirectory(prefix="ci-web-e2e-", dir=private) as value:
        directory = Path(value).resolve()
        # Verify the exact absolute cleanup target before TemporaryDirectory recurses.
        if directory.parent != private or not directory.is_relative_to(private):
            raise CheckFailure("temporary_directory_escapes_private_root")
        directory.chmod(0o700)
        with contextlib.ExitStack() as stack:
            def start(args: list[str], name: str, *, env: dict | None = None) -> subprocess.Popen:
                console = stack.enter_context((directory / f"{name}.log").open("wb"))
                process = subprocess.Popen(args, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                           stdout=console, stderr=subprocess.STDOUT,
                                           start_new_session=os.name == "posix")
                children.append(process)
                return process

            editor, viewer = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
            write_json(directory / "editor-client.json", {"token": editor})
            write_json(directory / "server-credentials.json", {"credentials": [
                {"principal_id": "ci-synthetic", "role": role, "token_sha256": sha256(token.encode()).hexdigest()}
                for role, token in (("editor", editor), ("viewer", viewer))]})
            try:
                for kind, port in zip(("bootstrap", "workspace"), ports[:2], strict=True):
                    process = start([sys.executable, str(Path(__file__).resolve()), "--serve", kind,
                                     "--directory", str(directory), "--port", str(port),
                                     "--web-port", str(ports[2])], kind)
                    wait_ready(process, f"http://{HOST}:{port}/health")
                workspace_url = f"http://{HOST}:{ports[1]}/api/workspace/projects"
                status, payload = request_json(f"http://{HOST}:{ports[0]}/api/bootstrap")
                report["checks"]["real_synthetic_bootstrap_ready"] = status == 200 and bool(payload.get("data"))
                report["checks"]["unauthenticated_denied"] = request_json(workspace_url)[0] == 401
                status, payload = request_json(workspace_url, token=editor)
                report["checks"]["new_private_workspace_is_empty"] = (
                    status == 200 and payload.get("data", {}).get("projects") == [])
                report["checks"]["viewer_write_denied"] = (
                    request_json(workspace_url, token=viewer, method="POST")[0] == 403)
                report["checks"]["exact_origin_allowed"] = (
                    request_json(workspace_url, token=editor, origin=f"http://{HOST}:{ports[2]}")[0] == 200)
                report["checks"]["other_origin_denied"] = (
                    request_json(workspace_url, token=editor, origin="https://invalid.example")[0] == 403)
                if not all(report["checks"].values()):
                    raise CheckFailure("api_preflight_failed")
                if not probe:
                    node = shutil.which("node")
                    if not node:
                        raise CheckFailure("node_not_found")
                    vite, playwright = config_files(directory, ports)
                    web = start([node, str(WEB / "node_modules/vite/bin/vite.js"), "--config", str(vite),
                                 "--configLoader", "native"], "vite")
                    wait_ready(web, f"http://{HOST}:{ports[2]}/", json_health=False)
                    env = {**os.environ, "LGAX_E2E_TOKEN_FILE": str(directory / "editor-client.json"),
                           "PLAYWRIGHT_CHANNEL": "", "CI": "true"}
                    tests = start([node, str(WEB / "node_modules/@playwright/test/cli.js"),
                                   "test", "--config", str(playwright)], "playwright", env=env)
                    try:
                        exit_code = tests.wait(timeout=300)
                    except subprocess.TimeoutExpired as error:
                        raise CheckFailure("browser_tests_timeout") from error
                    if not (directory / "raw-report.json").is_file():
                        raise CheckFailure("browser_report_missing")
                    raw = json.loads((directory / "raw-report.json").read_text("utf-8"))
                    report["browser_stats"] = {key: raw.get("stats", {}).get(key)
                                               for key in ("expected", "unexpected", "skipped", "flaky")}
                    report["browser_cases"] = browser_cases(raw)
                    report["checks"]["all_three_browser_cases_pass_without_skip"] = (
                        exit_code == 0 and not raw.get("errors")
                        and report["browser_stats"] == {"expected": 3, "unexpected": 0, "skipped": 0, "flaky": 0}
                        and len(report["browser_cases"]) == 3
                        and {row["case"] for row in report["browser_cases"]}
                        == {"fixture_planning", "fixture_unmeasured", "live_workspace"}
                        and all(row["outcome"] == "expected" and row["results"] == ["passed"]
                                for row in report["browser_cases"]))
                    if not report["checks"]["all_three_browser_cases_pass_without_skip"]:
                        raise CheckFailure("browser_cases_did_not_all_pass")
                report["status"] = "pass"
            except (CheckFailure, OSError, ValueError, KeyboardInterrupt) as error:
                report["failure"] = str(error) if isinstance(error, CheckFailure) else type(error).__name__
            finally:
                cleanup_errors = False
                for process in reversed(children):
                    try:
                        stop_child(process)
                    except (OSError, subprocess.TimeoutExpired):
                        cleanup_errors = True
                report["checks"]["owned_children_reaped"] = (
                    not cleanup_errors and all(p.poll() is not None for p in children))
                report["checks"]["isolated_ports_released"] = all(port_available(port) for port in ports)
                if not all(report["checks"].values()):
                    report["status"] = "fail"
        # TemporaryDirectory removes raw logs/results/DB and credential material here.
    report["checks"]["temporary_material_removed"] = not directory.exists()
    report["credentials_retained"] = False
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true", help="API preparation and child cleanup only; no browser")
    parser.add_argument("--report", type=Path, help="Write only the sanitized public summary to a new file")
    parser.add_argument("--serve", choices=("bootstrap", "workspace"), help=argparse.SUPPRESS)
    parser.add_argument("--directory", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--web-port", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.serve:
        serve(args.serve, args.directory, args.port, args.web_port)
        return 0
    if args.report and args.report.exists():
        parser.error("Existing report is preserved; select a new report path")
    def interrupted(_signal, _frame):
        raise CheckFailure("helper_interrupted")

    previous_handler = signal.signal(signal.SIGTERM, interrupted)
    try:
        report = run(probe=args.probe)
    except (CheckFailure, OSError, ValueError, KeyboardInterrupt) as error:
        report = {"status": "fail", "failure": str(error) if isinstance(error, CheckFailure) else type(error).__name__}
    finally:
        signal.signal(signal.SIGTERM, previous_handler)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
