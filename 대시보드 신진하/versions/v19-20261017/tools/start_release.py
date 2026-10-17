"""Run the local factory reader and a passive, explicitly scoped observer.

This launcher never starts Codex/Claude, performs a product request, changes
native settings, or writes a token. Keep it open while using the local screen.
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass

DASHBOARD_ROOT = Path(__file__).resolve().parents[1]
if str(DASHBOARD_ROOT) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_ROOT))

from backend.release_reader import ReleaseReadError, ReleaseReader


class StartError(RuntimeError):
    """A fixed, non-sensitive launcher diagnostic."""


@dataclass(frozen=True)
class Plan:
    workspace: Path
    dist: Path
    port: int
    engine: str
    observer_python: Path | None
    latest: bool = False
    no_open: bool = False

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}/"


def prepare(workspace, dist, port=8033, *, latest=False, no_open=False):
    workspace, dist = Path(workspace), Path(dist)
    if not workspace.is_absolute() or not dist.is_absolute():
        raise StartError("제품 폴더와 화면 dist는 절대 경로로 지정하세요.")
    if type(port) is not int or not 1 <= port <= 65535:
        raise StartError("포트는 1~65535 범위여야 합니다.")
    # The release reader checks the folder's own install record and each listed product file.
    # It does not read observation artifacts in this verification step.
    try:
        engine, _fingerprint = ReleaseReader(workspace)._verify()
    except (ReleaseReadError, OSError, ValueError, TypeError):
        raise StartError("제품 폴더의 파일이 그 폴더의 설치 기록(product-install.json)과 일치하는지 확인하세요.") from None
    if not dist.is_dir() or dist.is_symlink() or not (dist / "index.html").is_file():
        raise StartError("빌드된 로컬 화면 dist와 index.html을 확인하세요.")
    if latest and engine != "codex":
        raise StartError("--latest는 Codex 관찰을 명시적으로 선택할 때만 사용합니다.")
    observer_python = None
    if engine == "codex":
        observer_python = next((p for p in (workspace / ".venv/Scripts/python.exe", workspace / ".venv/bin/python") if p.is_file()), None)
        if observer_python is None or not (workspace / "web/prototypes/agent-office/office.py").is_file():
            raise StartError("제품 폴더의 정상 setup과 .venv Python 설치를 먼저 완료하세요.")
    return Plan(workspace.resolve(), dist.resolve(), port, engine, observer_python, bool(latest), bool(no_open))


def child_specs(plan, token):
    """The random view token belongs only to the server child's environment."""
    observer_env = dict(os.environ)
    for name in ("AX_HARNESS_VIEW_TOKEN", "AX_HARNESS_ALLOWED_ORIGINS", "AX_HARNESS_DB", "AX_HARNESS_PROFILE", "AX_HARNESS_MEMBERS", "AX_RELEASE_WORKSPACE", "AX_RELEASE_UI_DIST"):
        observer_env.pop(name, None)
    observer_env["PYTHONDONTWRITEBYTECODE"] = "1"
    server_env = dict(observer_env)
    server_env.update(AX_RELEASE_WORKSPACE=str(plan.workspace), AX_RELEASE_UI_DIST=str(plan.dist), AX_HARNESS_VIEW_TOKEN=token)
    if plan.engine == 'codex':
        server_env['AX_RELEASE_NATIVE_SESSIONS'] = str(Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex') / 'sessions')
    server = ([sys.executable, "-u", "-m", "backend.release_server", "--port", str(plan.port)], DASHBOARD_ROOT, server_env)
    observer = None
    if plan.engine == "codex":
        command = [str(plan.observer_python), "-u", str(plan.workspace / "web/prototypes/agent-office/office.py"), "codex", "--harness", str(plan.workspace), "--latest" if plan.latest else "--wait"]
        observer = (command, plan.workspace, observer_env)
    return server, observer


def check_port_available(port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            probe.bind(("127.0.0.1", port))
    except OSError:
        raise StartError("선택한 로컬 포트를 사용할 수 없습니다. 기존 실행을 닫거나 다른 --port를 사용하세요.") from None


def spawn(spec):
    command, cwd, environment = spec
    # No shell, inherited input, command log, token argument, or visible helper.
    return subprocess.Popen(command, cwd=str(cwd), env=environment, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise urllib.error.URLError("redirect refused")


def wait_ready(process, plan, token, *, timeout=20):
    # Bypass proxy environment settings; these two GETs never send a token.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise StartError("로컬 읽기 서버가 시작되지 않았습니다. 제품·화면 설정과 포트를 확인하세요.")
        try:
            with opener.open(plan.url + "health", timeout=.75) as response:
                health = json.loads(response.read(4097))
            if health.get("service") != "kitchen-ax-harness-reader" or health.get("ok") is not True:
                raise StartError("선택한 포트의 서버가 이번 실행과 일치하지 않습니다.")
            with opener.open(plan.url, timeout=.75) as response:
                html = response.read(4 * 1024 * 1024 + 1).decode("utf-8")
            marker = '<script type="application/json" id="ax-release-bootstrap">'
            if len(html) > 4 * 1024 * 1024 or html.count(marker) != 1:
                raise StartError("이번 실행의 로컬 화면 연결을 확인하지 못했습니다.")
            payload = json.loads(html.split(marker, 1)[1].split("</script>", 1)[0])
            correct = (payload.get("kind") == "lgax_local_release_connection" and payload.get("url") == plan.url.rstrip("/")
                       and isinstance(payload.get("token"), str) and hmac.compare_digest(payload["token"], token))
            if not correct or process.poll() is not None:
                raise StartError("선택한 포트의 화면이 이번 실행과 일치하지 않습니다.")
            return
        except StartError:
            raise
        except (urllib.error.URLError, OSError, ValueError, UnicodeError, AttributeError):
            time.sleep(.2)
    raise StartError("로컬 읽기 서버의 시작 시간이 초과되었습니다. 설정과 포트를 확인하세요.")


def stop_children(children):
    # Only handles returned from our own Popen calls are ever terminated.
    for process in reversed(children):
        if process.poll() is not None:
            continue
        try:
            process.terminate()
            process.wait(timeout=4)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
                process.wait(timeout=4)
            except (OSError, subprocess.TimeoutExpired):
                pass
        except (OSError, ProcessLookupError):
            pass


def supervise(server, observer):
    while True:
        if server.poll() is not None:
            raise StartError("로컬 읽기 서버가 종료되어 이번 연결도 닫습니다.")
        if observer is not None and observer.poll() is not None:
            if observer.returncode:
                raise StartError("관찰기가 종료되었습니다. 제품의 정상 실행·신뢰 설정을 확인하세요.")
            print("관찰기가 종료되어 로컬 연결을 닫습니다. 필요하면 다시 실행하세요.", flush=True)
            return 0
        time.sleep(.3)


def launch(plan):
    check_port_available(plan.port)
    token = secrets.token_urlsafe(48)
    server_spec, observer_spec = child_specs(plan, token)
    children = []
    try:
        server = spawn(server_spec)
        children.append(server)
        wait_ready(server, plan, token)
        observer = spawn(observer_spec) if observer_spec else None
        if observer is not None:
            children.append(observer)
        print(f"로컬 공장 화면: {plan.url}", flush=True)
        if plan.engine == "codex":
            print("명시한 폴더의 최근 세션을 관찰합니다." if plan.latest else "새 Codex 세션 대기 중입니다. 제품 폴더에서 정상 절차로 새 세션을 시작하세요.", flush=True)
        else:
            print("Claude Code의 기존 관측 훅 기록을 기다립니다. 훅 설치·설정은 자동 변경하지 않습니다.", flush=True)
        print("이 창을 열어 두세요. Ctrl+C로 이번 실행의 읽기 서버와 관찰기만 닫습니다.", flush=True)
        if not plan.no_open:
            try:
                if not webbrowser.open(plan.url, new=2):
                    print("위 로컬 주소를 브라우저에서 직접 여세요.", flush=True)
            except (OSError, webbrowser.Error):
                print("위 로컬 주소를 브라우저에서 직접 여세요.", flush=True)
        return supervise(server, observer)
    except KeyboardInterrupt:
        print("이번 로컬 연결을 닫습니다. 원본 CLI와 다른 실행은 제어하지 않습니다.", flush=True)
        return 0
    except OSError:
        raise StartError("로컬 읽기 서버 또는 관찰기 프로세스를 시작할 수 없습니다.") from None
    finally:
        stop_children(children)
        token = None


def main(argv=None):
    parser = argparse.ArgumentParser(description="KITCHEN AX 로컬 릴리즈 관찰 화면")
    parser.add_argument("--workspace", type=Path, required=True, help="설치된 codex 또는 claude 제품의 절대 경로")
    parser.add_argument("--dist", type=Path, required=True, help="대시보드 빌드 dist의 절대 경로")
    parser.add_argument("--port", type=int, default=8033)
    parser.add_argument("--no-open", action="store_true", help="브라우저를 자동으로 열지 않음")
    parser.add_argument("--latest", action="store_true", help="기본 새 세션 대기 대신 명시한 Codex 폴더의 최근 세션 관찰")
    args = parser.parse_args(argv)
    try:
        return launch(prepare(args.workspace, args.dist, args.port, latest=args.latest, no_open=args.no_open))
    except StartError as exc:
        print(str(exc), file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
