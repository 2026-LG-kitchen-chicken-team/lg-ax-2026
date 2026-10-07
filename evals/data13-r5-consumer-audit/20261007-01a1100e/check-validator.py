"""Synthetic validator checks only; no product repository or runtime execution."""

import copy
import csv
import hashlib
import importlib.util
import io
import json
import tempfile
from pathlib import Path

OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("data13_own_audit", OUT / "consumer-audit.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def build():
    files, documents, captures, evidence = {}, [], [], {}
    for model in ("SYNTH-A", "SYNTH-B"):
        suffix = model[-1]
        did, rid, eid = "SYNTH-CSV-" + suffix, "SYNTH-REVIEW-" + suffix, "SYNTH-EVIDENCE-" + suffix
        text = "합성 검수 문장 가\n둘째 줄 " + suffix
        review = {"id": rid, "model_id": model, "text": text, "source_kind": "synthetic",
                  "document_version": "SYNTH-DOC-v1", "source_id": did, "evidence_id": eid, "locator": {"row": 2}}
        item = {k: review[k] for k in ("model_id", "document_version", "source_kind", "source_id", "locator", "text")}
        item.update(id=eid, source_type="review", feature_ids=[])
        evidence[model] = item
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(module.FIELDS)
        writer.writerow([review[k] if k != "row" else "2" for k in module.FIELDS])
        raw = stream.getvalue().encode()
        source = suffix + "-source.csv"
        files[source] = raw
        dataset = {"artifact_kind": "document_dataset", "dataset_version": "SYNTH-validator-v1",
                   "products": [{"model_id": model}], "reviews": [review], "features": [], "evidence": [item]}
        origins = [{"evidence_id": eid, "source_id": did, "document_version": "SYNTH-DOC-v1",
                    "source_kind": "synthetic", "sha256": sha(raw), "row": 2, "end_row": 3,
                    "text_sha256": sha(text.encode()), "original_role": "uploaded_review_csv", "parser": "stdlib.csv"}]
        files[suffix + "-dataset.json"] = dump(dataset)
        files[suffix + "-origins.json"] = dump(origins)
        doc = {"document_id": did, "kind": "review_csv", "source_file": source,
               "expected_dataset_ref": {"file": suffix + "-dataset.json", "pointer": ""},
               "expected_origins_ref": {"file": suffix + "-origins.json", "pointer": ""}}
        record = {"document_id": did, "sha256": sha(raw), "dataset": dataset, "origins": origins,
                  "scope_sha256": "c" * 64, "parser": "stdlib.csv", "source_kind": "synthetic",
                  "original_role": "uploaded_review_csv", "review_count": 1, "idempotent": False}
        for phase in ("before", "after"):
            db_name, metadata_name, original_name = suffix + "-db-" + phase + ".json", suffix + "-metadata-" + phase + ".json", suffix + "-original-" + phase + ".csv"
            files[db_name] = dump(record)
            files[metadata_name] = dump({"ok": True, "data": record})
            files[original_name] = raw
            doc["stored_" + phase + "_ref"] = {"file": db_name, "pointer": ""}
            doc["metadata_" + phase + "_ref"] = {"file": metadata_name, "pointer": ""}
            doc["original_" + phase + "_file"] = original_name
            for operation,path in (("metadata","/api/documents/"+did),("original","/api/documents/"+did+"/original")):
                doc[operation+"_"+phase+"_request"]={"method":"GET","path":path,"params":{}}
                doc[operation+"_"+phase+"_http_status"]=200
            evidence_name = suffix + "-evidence-" + phase + ".json"
            files[evidence_name] = dump({"ok": True, "data": {"evidence": item, "contract_version": "0.1.0"}})
            captures.append({"id": suffix + "-evidence-" + phase, "phase": phase, "kind": "evidence",
                             "request": {"method": "GET", "path": "/api/evidence/" + eid, "params": {}},
                             "http_status": 200, "server_profile": "documents", "expected_evidence_id": eid,
                             "response_ref": {"file": evidence_name, "pointer": ""}})
        documents.append(doc)
    for phase in ("before", "after"):
        for case in ("selected-model", "other-valid-model", "invalid-model", "invalid-version"):
            model = "SYNTH-B" if case == "other-valid-model" else "SYNTH-UNREGISTERED" if case == "invalid-model" else "SYNTH-A"
            version = "SYNTH-WRONG-VERSION" if case == "invalid-version" else "SYNTH-DOC-v1"
            filename = case + "-" + phase + ".json"
            capture = {"id": case + "-" + phase, "phase": phase, "kind": "search", "case_id": case,
                       "request": {"method": "GET", "path": "/api/evidence/search", "params": {"q": "문장", "model_id": model, "document_version": version}},
                       "server_profile": "documents", "response_ref": {"file": filename, "pointer": ""}}
            if case in ("invalid-model", "invalid-version"):
                code = "INVALID_MODEL_ID" if case == "invalid-model" else "INVALID_DOCUMENT_VERSION"
                files[filename] = dump({"ok": False, "error": {"code": code}})
                capture.update(expect="error", expected_error_code=code, http_status=404 if case == "invalid-model" else 400)
            else:
                files[filename] = dump({"ok": True, "data": {"query": "문장", "model_id": model,
                    "document_version": version, "items": [evidence[model]], "total": 1,
                    "contract_version": "0.1.0", "search_method": "literal_token_count"}})
                capture.update(expect="success", http_status=200)
            captures.append(capture)
    files["synthetic-restart-receipt.json"] = dump({"role": "synthetic fixture only; not a real restart", "model_calls": 0})
    packet = {"audit_input_format": module.FORMAT, "input_role": "synthetic_validator_fixture_not_runtime",
              "producer_commit": "a" * 40, "consumer_commit": "b" * 40,
              "dataset_version": "SYNTH-validator-v1", "documents": documents, "captures": captures,
              "restart_receipt_file": "synthetic-restart-receipt.json"}
    return packet, files


def mutate_json(files, name, fn):
    value = json.loads(files[name]); fn(value); files[name] = dump(value)


def checks():
    cases = []
    cases.append(("synthetic full pair", "MATCH", lambda p,f: None))
    cases.append(("after DB text changed", "MISMATCH", lambda p,f: mutate_json(f,"A-db-after.json",lambda v:v["dataset"]["reviews"][0].update(text="변경된 합성 문장"))))
    cases.append(("after API foreign model", "MISMATCH", lambda p,f: mutate_json(f,"A-evidence-after.json",lambda v:v["data"]["evidence"].update(model_id="SYNTH-B"))))
    cases.append(("after API wrong document version", "MISMATCH", lambda p,f: mutate_json(f,"A-evidence-after.json",lambda v:v["data"]["evidence"].update(document_version="SYNTH-DOC-v2"))))
    cases.append(("after API wrong canonical ID", "MISMATCH", lambda p,f: mutate_json(f,"A-evidence-after.json",lambda v:v["data"]["evidence"].update(id="SYNTH-FOREIGN-ID"))))
    cases.append(("after original bytes changed", "MISMATCH", lambda p,f:f.__setitem__("A-original-after.csv",f["A-original-after.csv"]+b'\n')))
    cases.append(("NFC to NFD text substitution", "MISMATCH", lambda p,f: mutate_json(f,"A-evidence-after.json",lambda v:v["data"]["evidence"].update(text=v["data"]["evidence"]["text"].replace("가","\u1100\u1161")))))
    cases.append(("bool replaces count 1", "MISMATCH", lambda p,f: mutate_json(f,"A-db-after.json",lambda v:v.update(review_count=True))))
    cases.append(("foreign model search leak", "MISMATCH", lambda p,f: mutate_json(f,"other-valid-model-after.json",lambda v:v["data"]["items"][0].update(model_id="SYNTH-A"))))
    cases.append(("wrong-version error code", "MISMATCH", lambda p,f: mutate_json(f,"invalid-version-after.json",lambda v:v["error"].update(code="INVALID_MODEL_ID"))))
    cases.append(("local version status incorrectly 404", "MISMATCH", lambda p,f:next(c for c in p["captures"] if c["id"]=="invalid-version-after").update(http_status=404)))
    cases.append(("absent DB-after capture", "UNCONFIRMED", lambda p,f:p["documents"][0].pop("stored_after_ref")))
    cases.append(("absent original-after capture", "UNCONFIRMED", lambda p,f:p["documents"][0].pop("original_after_file")))
    cases.append(("absent evidence-after capture", "UNCONFIRMED", lambda p,f:p["captures"].remove(next(c for c in p["captures"] if c["id"]=="A-evidence-after"))))
    cases.append(("absent restart receipt", "UNCONFIRMED", lambda p,f:p.pop("restart_receipt_file")))
    def empty(p,f):
        for phase in ("before","after"):
            mutate_json(f,"selected-model-"+phase+".json",lambda v:v["data"].update(items=[],total=0))
    cases.append(("empty positive control", "UNCONFIRMED", empty))
    def public(p,f):
        for c in p["captures"]:
            c["server_profile"]="public_api"
            if c.get("case_id")=="invalid-version": c["http_status"]=404
    cases.append(("public API version error 404", "MATCH", public))
    def request_change(p,f):
        next(c for c in p["captures"] if c["id"]=="selected-model-after")["request"]["params"]["q"]="changed-query"
    cases.append(("restart query scope changed", "MISMATCH", request_change))
    cases.append(("duplicate capture ID", "MISMATCH", lambda p,f:p["captures"].append(copy.deepcopy(p["captures"][0]))))
    cases.append(("missing producer pin", "UNCONFIRMED", lambda p,f:p.update(producer_commit=None)))
    cases.append(("metadata request is a write", "MISMATCH", lambda p,f:p["documents"][0]["metadata_after_request"].update(method="POST")))
    cases.append(("wrong original GET document", "MISMATCH", lambda p,f:p["documents"][0]["original_after_request"].update(path="/api/documents/SYNTH-FOREIGN/original")))
    results = []
    with tempfile.TemporaryDirectory(prefix="lgax-data13-synthetic-validator-") as task_temp:
        root = Path(task_temp).resolve()
        for index,(name,expected,mutation) in enumerate(cases):
            folder = root / str(index); folder.mkdir()
            packet,files=build(); mutation(packet,files)
            for path,raw in files.items(): (folder/path).write_bytes(raw)
            packet["files"]=[{"path":p,"sha256":sha(raw)} for p,raw in files.items()]
            (folder/"manifest.json").write_bytes(dump(packet))
            result=module.Audit(folder/"manifest.json").run()
            results.append({"case":name,"expected":expected,"observed":result["status"],"passed":result["status"]==expected,
                            "operating_origin_verified":result["operating_origin_verified"],"pm_approval_verified":result["pm_approval_verified"]})
    report={"purpose":"synthetic comparison-validator checks only; not DB/API/runtime tests",
            "validator_sha256":sha((OUT/"consumer-audit.py").read_bytes()),"cases":results,"passed":sum(r["passed"] for r in results),
            "total":len(results),"new_product_network_calls":0,"new_model_calls":0,"new_OCR_calls":0,"service_restart_calls":0}
    (OUT/"validator-self-checks.json").write_bytes(dump(report))
    print(json.dumps({k:v for k,v in report.items() if k!="cases"}))
    if not all(r["passed"] for r in results):
        print(json.dumps([r for r in results if not r["passed"]])); raise SystemExit(1)


if __name__ == "__main__":
    checks()
