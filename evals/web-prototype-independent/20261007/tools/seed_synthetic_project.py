"""S8 setup (record 051/052): create one project under the default synthetic dataset in a test workspace DB.

The same DB is then served with the R5 public document dataset, so the web must not reuse this older-version project.
Test-only server, no model. Prints the project ID and its dataset_version; the token is read from a private file.
"""
import json
import sys
from pathlib import Path

import httpx

url, token_file, requests_file = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
token = json.loads(token_file.read_text("utf-8"))["token"]
request = json.loads(requests_file.read_text("utf-8"))[0]
request["model_ids"] = ["FRIDGE-A"]
with httpx.Client(base_url=url, headers={"Authorization": "Bearer " + token, "Origin": "http://127.0.0.1:5173"}, trust_env=False, timeout=30) as client:
    boot = client.get("/api/workspace/bootstrap")
    boot.raise_for_status()
    manifest = boot.json()["data"]["manifest"]
    created = client.post("/api/workspace/projects", json={"name": "R5 S8 합성 버전 기존 프로젝트", "request": request, "document_versions": {"FRIDGE-A": "1.0"}})
    created.raise_for_status()
    project = created.json()["data"]["project"]
    print(json.dumps({"bootstrap_source_kind": manifest.get("source_kind"), "bootstrap_version": manifest.get("version"),
                      "project_id": project["id"], "project_dataset_version": project["dataset_version"]}, ensure_ascii=False))
