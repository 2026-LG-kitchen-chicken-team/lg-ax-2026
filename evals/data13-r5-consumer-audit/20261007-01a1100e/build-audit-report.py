"""Save this preparation's source pins, missing-input table and preservation proof."""

import csv
import hashlib
import io
import json
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BASE = "8b41fd4785bc149593f04d913ef974f29fb341fe"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    target = (OUT / name).resolve()
    if not target.is_relative_to(OUT):
        raise ValueError("report path escapes unique directory")
    target.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


baseline = json.loads((OUT / "protected-baseline.json").read_bytes())
changed = [f["path"] for f in baseline["files"] if not (ROOT/f["path"]).is_file() or sha(ROOT/f["path"]) != f["sha256"]]
if changed:
    raise ValueError("original files changed: " + repr(changed))
pending = json.loads((OUT / "current-unreceived/result.json").read_bytes())
self_checks = json.loads((OUT / "validator-self-checks.json").read_bytes())
if pending["status"] != "UNCONFIRMED" or pending["declared_captures"] != 0 or pending["declared_documents"] != 0:
    raise ValueError("unreceived packet cannot become actual product verification")
if self_checks["passed"] != self_checks["total"] or self_checks["validator_sha256"] != sha(OUT / "consumer-audit.py"):
    raise ValueError("validator checks do not cover current source")

sources = [
    ("packages/contracts/schemas/lgax.schema.json", [92, 154], "canonical Evidence/Review; dataset version and SHA are outside entity fields"),
    ("packages/core/src/lgax_core/review_csv.py", [15, 149, 194, 211], "eight original CSV columns, DB documents record; store reparses original CSV"),
    ("packages/core/src/lgax_core/review_import.py", [127, 166], "physical CSV row/end_row, original text and UTF8 SHA origins"),
    ("packages/core/src/lgax_core/documents.py", [111, 141], "PDF original SHA, expected excerpts, origins character ranges"),
    ("packages/core/src/lgax_core/documents_server.py", [35, 55, 76], "GET metadata/original/evidence/search; local error status mapping"),
    ("packages/core/src/lgax_core/retrieval.py", [81, 100, 106], "current literal_token_count response and full evidence payload"),
    ("packages/core/src/lgax_core/evidence_catalog.py", [118, 139], "model/version scopes and scoped ID SOURCE_MISMATCH"),
    ("packages/core/src/lgax_core/source_ranges.py", [133], "source byte and range verification are separate from table/OCR structure"),
    ("apps/api/src/lgax_api/server.py", [36], "public API invalid document version uses404 rather than local400"),
    ("evals/data003-compare/20261006-01a10834/prepared/13-handoff-contract.json", [6], "historical handoff preparation, not an R5 capture"),
]
records=[]
for path, lines, observation in sources:
    blob=subprocess.check_output(["git","rev-parse",BASE+":"+path],cwd=ROOT).decode().strip()
    raw=subprocess.check_output(["git","show",BASE+":"+path],cwd=ROOT)
    if raw != (ROOT/path).read_bytes():
        raise ValueError("working source does not match pinned Git bytes: " + path)
    records.append({"path":path,"source_commit":BASE,"git_blob":blob,"sha256":sha(ROOT/path),"lines":lines,"observation":observation})
save("source-manifest.json", {"source_commit":BASE,"method":"static source inspection only; no producer or endpoint run","sources":records,
    "R5_data_path":"data/research/r5-public-reviews-20261007","R5_data_present_in_fixed_main":(ROOT/"data/research/r5-public-reviews-20261007").exists(),
    "R5_handoff_received":False,"actual_product_requests":0,"models":0,"OCR":0,"restart_calls":0})
rows = [
    ("C01", "생산자/소비 commit·팩 버전", "정확 head와 승인/후보 버전", "PM/PM 보조 DATA"),
    ("C02", "원 CSV/PDF bytes", "등록문서 ID별 source path·SHA", "PM 보조 DATA"),
    ("C03", "expected dataset/origins", "원문·ID·모델·판본·locator·text SHA", "PM 보조 DATA / 1·2번 원문 검수"),
    ("C04", "DB documents record", "저장 record의 전/후 export", "PM/PM 보조 DATA"),
    ("C05", "metadata GET", "동일 문서 GET/200 원 JSON 전/후", "PM/PM 보조 DATA"),
    ("C06", "original GET", "원 binary/CSV 응답 전/후 SHA", "PM/PM 보조 DATA"),
    ("C07", "개별 evidence GET", "모든 원 evidence ID별 원 JSON 전/후", "PM/PM 보조 DATA"),
    ("C08", "정상 scope GET", "selected model/version 원문 양성 대조", "PM/PM 보조 DATA"),
    ("C09", "다른 유효 제품 scope GET", "다른 제품의 근거만 반환하는 양성 대조", "PM/PM 보조 DATA"),
    ("C10", "미등록 모델 GET", "INVALID_MODEL_ID와 해당 profile HTTP status", "PM/PM 보조 DATA"),
    ("C11", "틀린 문서 판본 GET", "INVALID_DOCUMENT_VERSION; local400/public404 구분", "PM/PM 보조 DATA"),
    ("C12", "실제 재시작 수신증", "같은 DB/자료 범위와 전/후 응답", "PM"),
    ("C13", "운영 출처/계약 호환성/인수", "원 실행/배포 source 및 PM 검수 원 증거", "PM"),
]
table=[{"check_id":id_,"subject":subject,"required_input":required,"owner":owner,
        "expected_R5_value":None,"observed_before":None,"observed_after":None,
        "status":"미확인","reason":"고정 R5 등록/소비 인계 미수신","actual_capture_count":0} for id_,subject,required,owner in rows]
stream=io.StringIO(newline=""); writer=csv.DictWriter(stream,fieldnames=list(table[0]),lineterminator="\n"); writer.writeheader(); writer.writerows(table)
(OUT/"검수대조표.csv").write_bytes(stream.getvalue().encode())
save("input-intake.json", {"source_commit":BASE,"workspace_date_kst":"2026-10-07","handoff_received":False,"producer_commit":None,
    "R5_dataset_version":None,"original_R5_files_received":0,"DB_API_captures_received":0,"restart_receipt_received":False,
    "state":"UNCONFIRMED","checks":table,
    "historical_R4_operating_evidence":"https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/28#issuecomment-6028048853",
    "historical_R4_is_new_R5_validation":False})
save("verification.json", {"scope":"read-only preparation and synthetic validator correctness",
    "source_commit":BASE,"protected_original_files":len(baseline["files"]),"changed_original_files":changed,
    "static_source_Git_byte_matches":len(records),"synthetic_validator_cases":self_checks["total"],"synthetic_validator_passed":self_checks["passed"],
    "actual_R5_validation_status":pending["status"],"actual_R5_documents_checked":0,"actual_R5_capture_checks":0,
    "real_product_network_calls":0,"models":0,"OCR":0,"producer_calls":0,"service_restart_calls":0,
    "consumer_contract_compatibility_verified":False,"operating_origin_verified":False,"PM_approval":None,"issue13_done":False})
print(json.dumps({"protected_original_files":len(baseline["files"]),"source_Git_matches":len(records),"synthetic_cases":self_checks["total"],"actual_R5_status":"UNCONFIRMED"}))
