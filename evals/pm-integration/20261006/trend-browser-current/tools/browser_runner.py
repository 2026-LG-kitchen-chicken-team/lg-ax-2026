"""Zero-auth Docker-only browser experiment over unchanged pinned product sources.

The supervisor provides no host Git, publisher, AI profile or credentials. This
helper creates ephemeral application credentials only inside the guest tmpfs.
Public outputs intentionally omit them. No planning/model execution is enabled.
"""

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import venv
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")


def wait_ready(url, headers=None):
    import httpx
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            reply = httpx.get(url, headers=headers, trust_env=False, timeout=1)
            if reply.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise RuntimeError("Isolated guest API did not become ready")


def check_api_mcp(root, credential, url, mode):
    from lgax_mcp.workspace_client import WorkspaceClient
    dataset_file = root / ("data/demo/review-trends-dated/dataset.json" if mode == "dated" else "data/demo/dataset.json")
    dataset = json.loads(dataset_file.read_text("utf-8"))
    token = json.loads(credential.read_text("utf-8"))["token"]
    proxy = WorkspaceClient(url, token, client_kind="web")
    request = json.loads((root / "data/demo/planning_requests.json").read_text("utf-8"))[0]
    request.update(model_ids=["FRIDGE-A"], dataset_version=dataset["manifest"]["version"])
    response = proxy.create_project("PM 별도 합성 동향 브라우저 검증", request, {"FRIDGE-A": "1.0"})
    project = response["data"]["project"]
    filters = {"project_id": project["id"], "model_id": "FRIDGE-A",
               "source_ids": sorted({item["source_id"] for item in dataset["reviews"] if item["model_id"] == "FRIDGE-A"}),
               "dataset_version": dataset["manifest"]["version"], "start_date": "2026-10-01",
               "end_date_exclusive": "2026-11-01", "granularity": "month", "topic_ids": [],
               "source_kind": "synthetic", "timezone": "Asia/Seoul"}
    first = proxy.review_trends(filters)
    aggregate = first["data"]["aggregate"]
    aid = aggregate["aggregate_id"]
    saved = proxy.get_review_trends(project["id"], aid)
    evidence = proxy.trend_evidence(project["id"], aid, "MONTH-2026-10", "cleaning")
    tool_file = root / "evals/web/20261006/web-integration-r3/tools/check_api_mcp_path.py"
    spec = importlib.util.spec_from_file_location("original_api_mcp_check", tool_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    via_mcp = asyncio.run(module.mcp_calls(url, credential, project["id"], filters, aid))
    topic = next(t for t in aggregate["buckets"][0]["topics"] if t["topic_id"] == "cleaning")
    checks = {"api_requery_same_aggregate": saved == first,
              "api_empty_topic_filter_kept": aggregate["filters"]["topic_ids"] == [],
              "api_evidence_same_key": (evidence["data"]["aggregate_id"], evidence["data"]["bucket_id"], evidence["data"]["topic_id"]) == (aid, "MONTH-2026-10", "cleaning"),
              "api_evidence_in_bucket_ids": sorted(e["id"] for e in evidence["data"]["evidence"]) == sorted(topic["evidence_ids"]),
              "api_evidence_document_version": {e["document_version"] for e in evidence["data"]["evidence"]} <= {"1.0"},
              "mcp_tools_present": {"review_trends", "get_review_trends", "trend_evidence"} <= set(via_mcp["tools"]),
              "mcp_query_same_id": via_mcp["query"]["data"]["aggregate"]["aggregate_id"] == aid,
              "mcp_saved_identical": via_mcp["saved"] == saved,
              "mcp_same_dataset_sha256": via_mcp["saved"]["data"]["aggregate"]["dataset_sha256"] == aggregate["dataset_sha256"],
              "mcp_evidence_identical": via_mcp["evidence"] == evidence}
    if not all(checks.values()):
        raise RuntimeError("API/MCP comparison mismatch")
    assert aggregate["counts"]["eligible_unique_review_count"] == (3 if mode == "dated" else 0)
    assert aggregate["counts"]["excluded_undated_count"] == (2 if mode == "dated" else 10)
    assert topic["topic_review_count"] == (1 if mode == "dated" else 0)
    originals = {item["id"]: item for item in dataset["evidence"]}
    assert all(item == originals[item["id"]] for item in evidence["data"]["evidence"])
    return {"kind": "pm_review_trend_consumption_path", "result": "consumption_path_ok",
            "collector": "DATA collector via PM production CLI, pinned synthetic candidate preview",
            "mode": mode, "project_id": project["id"], "aggregate_id": aid, "dataset_sha256": aggregate["dataset_sha256"],
            "filters": filters, "evidence_ids": [item["id"] for item in evidence["data"]["evidence"]],
            "counts": aggregate["counts"], "checks": checks, "api_aggregate": aggregate,
            "api_evidence": evidence["data"], "mcp_tools": via_mcp["tools"]}


def run_guest(source, dependency, out):
    out.mkdir(parents=True, exist_ok=True)
    image_site = str(Path(sys.prefix) / "lib/python3.11/site-packages")
    with tempfile.TemporaryDirectory(prefix="lgax-trend-browser-") as temp:
        temporary = Path(temp)
        root = temporary / "source"
        shutil.copytree(source, root)
        web = root / "apps/web"
        for name in ("package.json", "package-lock.json"):
            if sha(web / name) != sha(dependency / name):
                raise RuntimeError("Dependency image package/lock pin mismatch")
        modules = web / "node_modules"
        modules.mkdir()
        # Keep the root writable for Vite caches; executable dependencies remain on the image overlay.
        for entry in (dependency / "node_modules").iterdir():
            (modules / entry.name).symlink_to(entry, target_is_directory=entry.is_dir())
        supplemental = root / "evals/pm-integration/20261006/trend-browser-current/tools/supplemental.spec.ts"
        shutil.copyfile(supplemental, web / "e2e/pm-trend-browser-proof.spec.ts")
        environment = temporary / "python-env"
        venv.EnvBuilder(with_pip=False, system_site_packages=True, symlinks=True).create(environment)
        paths = [str(root / p) for p in ("packages/core/src", "packages/contracts/src", "apps/api/src", "apps/mcp/src")]
        site = next((environment / "lib").glob("python*/site-packages"))
        (site / "lgax-source.pth").write_text("\n".join(paths + [image_site]) + "\n", encoding="utf-8")
        python = environment / "bin/python"
        # Parent imports now resolve the exported sources; stdio subprocess uses the normal guest venv installation.
        sys.path[:0] = paths
        sys.executable = str(python)
        summary = {"kind": "pm_trend_browser_guest", "model_calls": 0, "application_credentials": "ephemeral guest-only; omitted",
                   "host_services_contacted": False, "dependency_package_sha256": sha(web / "package.json"),
                   "dependency_lock_sha256": sha(web / "package-lock.json"),
                   "playwright_version": json.loads((dependency / "node_modules/@playwright/test/package.json").read_text("utf-8"))["version"], "modes": {}}
        for mode in ("dated", "undated"):
            mode_out = out / mode
            mode_out.mkdir()
            secret = temporary / mode
            secret.mkdir()
            token = secrets.token_urlsafe(40)
            credentials, credential = secret / "registry.json", secret / "application-token.json"
            write_json(credentials, {"credentials": [{"principal_id": "pm-browser", "role": "editor", "token_sha256": hashlib.sha256(token.encode()).hexdigest()}]})
            write_json(credential, {"token": token})
            dataset = root / ("data/demo/review-trends-dated/dataset.json" if mode == "dated" else "data/demo/dataset.json")
            sidecar = root / ("data/demo/review-trends-dated/annotation.candidate.json" if mode == "dated" else "data/research/P2-DATA-005-trends-20261006/annotation.candidate.v1.json")
            commands = [
                [str(python), "-B", "-m", "lgax_api.server", "--port", "18867", "--dataset", str(dataset)],
                [str(python), "-B", "-m", "lgax_api.workspace_server", "--port", "18881", "--db", str(secret / "new.sqlite"),
                 "--credentials", str(credentials), "--dataset", str(dataset), "--trend-metadata", str(sidecar),
                 "--trend-metadata-sha256", sha(sidecar), "--allow-candidate-trend-metadata"],
            ]
            streams, children = [], []
            try:
                for index, command in enumerate(commands):
                    stream = (mode_out / f"api-{index}.log").open("wb")
                    streams.append(stream)
                    children.append(subprocess.Popen(command, cwd=root, stdout=stream, stderr=subprocess.STDOUT))
                wait_ready("http://127.0.0.1:18867/health")
                wait_ready("http://127.0.0.1:18881/health", {"Authorization": "Bearer " + token})
                path = check_api_mcp(root, credential, "http://127.0.0.1:18881", mode)
                path_file = mode_out / "api-mcp-path.json"
                write_json(path_file, path)
                env = {**os.environ, "LGAX_E2E_PORT": "5183", "LGAX_WORKSPACE_PROXY": "http://127.0.0.1:18881",
                       "LGAX_E2E_TREND_TOKEN_FILE": str(credential), "LGAX_E2E_TREND_PATH_FILE": str(path_file),
                       "LGAX_E2E_TREND_PROOF_DIR": str(mode_out / "browser"), "PLAYWRIGHT_CHANNEL": "",
                       "PLAYWRIGHT_BROWSERS_PATH": "/ms-playwright"}
                with (mode_out / "playwright.log").open("wb") as log:
                    result = subprocess.run(["node", str(dependency / "node_modules/@playwright/test/cli.js"), "test",
                                             "e2e/trend-consumption.spec.ts", "e2e/pm-trend-browser-proof.spec.ts",
                                             "--output", str(mode_out / "private-test-results")], cwd=web, env=env,
                                            stdout=log, stderr=subprocess.STDOUT, timeout=240)
                print(f"{mode}: API/MCP10/10; browser return={result.returncode}", flush=True)
                summary["modes"][mode] = {"browser_returncode": result.returncode, "api_mcp_checks": path["checks"],
                                          "aggregate_id": path["aggregate_id"], "counts": path["counts"]}
                if result.returncode:
                    raise RuntimeError("Browser comparison failed; inspect private playwright log")
                # No raw HTML or traces are public: only whitelist proofs/exports/screenshots after token scan.
                for item in (mode_out / "browser").iterdir():
                    if item.suffix in (".json", ".md") and token.encode() in item.read_bytes():
                        raise RuntimeError("Application credential entered a public candidate artifact")
            finally:
                for child in children:
                    child.terminate()
                for child in children:
                    try:
                        child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
                for stream in streams:
                    stream.close()
                write_json(out / "guest-summary.json", summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("/workspace"))
    parser.add_argument("--dependency", type=Path, default=Path("/opt/lgax-web-dependencies"))
    parser.add_argument("--out", type=Path, default=Path("/artifacts/browser"))
    args = parser.parse_args()
    run_guest(args.source, args.dependency, args.out)
