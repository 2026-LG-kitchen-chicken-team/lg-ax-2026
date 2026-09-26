"""Read-only workflow validation and readiness gates. Python standard library only."""
import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUBMISSION_CHECKS = {
    "team", "eligibility", "application", "proposal_hwp", "page_limit",
    "consents", "pledge", "file_open", "upload_requirements", "team_review",
}
STAGES = {"requirements", "harness", "topic_research", "topic_decision", "proposal",
          "submission", "implementation", "evaluation", "presentation"}


def evidence_error(root, evidence):
    if not isinstance(evidence, dict) or not evidence.get("path"):
        return "evidence path and sha256 required"
    path = (root / evidence["path"]).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        return "evidence file missing or outside repository"
    expected = evidence.get("sha256")
    if expected != hashlib.sha256(path.read_bytes()).hexdigest():
        return "evidence hash missing or changed; review again"
    return None


def validate(data, root=ROOT):
    errors = []
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    try:
        deadline = datetime.fromisoformat(data["deadline"])
        if deadline.utcoffset() is None:
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        errors.append("deadline must be an ISO timestamp with timezone")
    sources = data.get("sources", [])
    candidates = data.get("candidates", [])
    for label, records in [("sources", sources), ("candidates", candidates),
                           ("stages", data.get("stages", [])),
                           ("submission_checks", data.get("submission_checks", []))]:
        if not isinstance(records, list) or not records or not all(isinstance(r, dict) for r in records):
            errors.append(f"{label}: nonempty record list required")
            continue
        ids = [r.get("id") for r in records]
        if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
            errors.append(f"{label}: unique nonempty ids required")
    if errors:
        return errors
    source_ids = {s["id"] for s in sources}
    for source in sources:
        if not all(source.get(k) for k in ("title", "locator", "checked_at", "supports", "limitations")):
            errors.append(f"source {source['id']}: provenance fields missing")
    for candidate in candidates:
        cid = candidate["id"]
        if candidate.get("theme") not in ("A", "B"):
            errors.append(f"candidate {cid}: theme must be A/B")
        if not all(candidate.get(k) for k in ("name", "user", "problem", "mvp", "risks", "evidence")):
            errors.append(f"candidate {cid}: decision fields missing")
        if not set(candidate.get("evidence", [])) <= source_ids:
            errors.append(f"candidate {cid}: unknown source")
        if candidate.get("feasibility") not in ("unreviewed", "conditional", "reviewed"):
            errors.append(f"candidate {cid}: invalid feasibility")
        if candidate.get("feasibility") == "reviewed":
            problem = evidence_error(root, candidate.get("feasibility_evidence"))
            if problem:
                errors.append(f"candidate {cid}: {problem}")
    for group in ("stages", "submission_checks"):
        for record in data[group]:
            if record.get("status") not in ("pending", "in_progress", "done"):
                errors.append(f"{group}/{record['id']}: invalid status")
            if record.get("status") == "done":
                problem = evidence_error(root, record.get("evidence"))
                if problem:
                    errors.append(f"{group}/{record['id']}: {problem}")
    checks = {r["id"] for r in data["submission_checks"]}
    if checks != SUBMISSION_CHECKS:
        errors.append("submission_checks: required checklist ids changed or missing")
    if {r["id"] for r in data["stages"]} != STAGES:
        errors.append("stages: required workflow stages changed or missing")
    decision = data.get("decision", {})
    if decision.get("status") not in ("exploring", "proposed", "confirmed"):
        errors.append("decision status must be exploring/proposed/confirmed")
    if decision.get("candidate_id") is None and decision.get("status") == "exploring":
        pass
    elif decision.get("candidate_id") not in {c["id"] for c in candidates}:
        errors.append("decision candidate not found")
    if decision.get("status") == "confirmed" and not all(
        decision.get(k) for k in ("confirmed_by", "confirmed_at", "rationale")
    ):
        errors.append("confirmed decision requires user, timestamp and rationale")
    return errors


def gate(data, name, root=ROOT):
    errors = validate(data, root)
    if errors:
        return errors
    decision = data["decision"]
    if decision["status"] != "confirmed":
        errors.append("주제 선택 미확정: 추천안과 사용자 결정을 구분하세요.")
    candidate = next((c for c in data["candidates"] if c["id"] == decision["candidate_id"]), None)
    if candidate is None or candidate["feasibility"] != "reviewed":
        errors.append("선택 후보의 구현 검토 증빙이 필요합니다.")
    if name == "submission":
        errors.extend(f"접수 점검 미완료: {r['id']}" for r in data["submission_checks"] if r["status"] != "done")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["status", "validate", "gate"])
    parser.add_argument("stage", nargs="?", choices=["topic", "submission"])
    args = parser.parse_args()
    try:
        data = json.loads((ROOT / "harness/project.json").read_text(encoding="utf-8-sig"))
        if args.command == "status":
            print(f"마감: {data['deadline']}; 환경: {data['environment']}")
            print(f"주제: {data['decision']['candidate_id'] or '미정'} ({data['decision']['status']})")
            for record in data["stages"]:
                print(f"{record['id']}: {record['status']} - {record['next_action']}")
            print("상태 표시는 증빙 검증 결과가 아닙니다. validate/gate로 확인하세요.")
            return 0
        if args.command == "gate" and not args.stage:
            parser.error("gate requires topic or submission")
        errors = gate(data, args.stage) if args.command == "gate" else validate(data)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        print(f"INVALID: {exc}")
        return 1
    for error in errors:
        print(f"BLOCKED: {error}")
    if not errors:
        print("PASS: " + ("기록 구조·출처 연결·증빙 일치" if args.command == "validate" else f"{args.stage} 준비 점검"))
    return 1 if errors else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
