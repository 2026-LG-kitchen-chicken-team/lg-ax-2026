"""Read-only projection of the fixed LG AX controller ledger.

Never imports controller code, calls its status/expiry methods, starts a Worker,
or reads credentials. The caller explicitly configures the one database path.
"""
from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

REPO = "2026-LG-kitchen-chicken-team/lg-ax-2026"
PROFILE = "lg-ax-2026"
ACCOUNTS = ("jeongiryang", "unknownamed", "ginaginaring", "choigilung")
STALE_SECONDS = 180
JOB_STATUSES = {"pending", "running", "stopping", "orphaned", "review_requested", "completed_review", "blocked", "failed", "accepted"}
FORMAL_STATUSES = {"pending", "ready", "doing", "blocked", "deferred", "individual_verified", "pm_review_requested", "pm_approved", "merged", "integration_verified", "done"}
IDLE_PHASES = {"starting", "idle", "profile_busy"}
ACTIVE_PHASES = {"preflight", "model", "validating", "publishing"}
EVENT_MESSAGES = {
    "registered": "승인된 작업이 대기열에 등록되었습니다.", "claimed": "Worker가 작업을 인수한 기록입니다.",
    "finished": "Worker가 결과를 보고한 기록입니다.", "reconciled": "PM이 작업 대기열을 조정한 기록입니다.",
    "orphaned": "소유권 확인이 필요한 작업 기록입니다.", "mode": "자동화 모드 변경 기록입니다.",
    "formal_snapshot": "PM 승인 스냅샷이 기록되었습니다.",
}
REASONS = {
    "running_confirmed": "유효한 작업 lease와 최근 Worker 자기보고가 일치합니다.",
    "worker_unconfirmed": "작업 기록은 실행 중이나 최근 Worker 실행 근거를 확인하지 못했습니다.",
    "lease_expired": "lease 또는 실행 기한이 지났습니다. 원본 상태는 변경하지 않았습니다.",
    "automation_off": "자동화가 OFF 또는 STOP입니다. 실제 프로세스 종료를 단정하지 않습니다.",
    "stopping": "중단 요청 상태입니다. 실제 종료 확인을 기다립니다.",
    "orphaned": "이전 실행의 소유권과 종료 상태를 확인해야 합니다.",
    "review_requested": "결과가 검수 요청 상태입니다. 정식 완료와 구분합니다.",
    "completed_review": "Worker 검토 결과가 보고되었습니다. PM 승인과 구분합니다.",
    "blocked": "대기열에 막힘이 기록되어 있습니다.", "failed": "대기열에 실패가 기록되어 있습니다.",
    "accepted": "대기열에서 인수되었습니다. phase2 정식 Done과 구분합니다.",
    "pending": "승인된 대기열의 착수 대기 상태입니다.",
}
ERRORS = {
    "not_configured": "하네스 DB 연결 설정을 기다리고 있습니다.",
    "unavailable": "하네스 상태를 읽을 수 없습니다. 운영자에게 연결 상태를 확인하세요.",
    "schema_error": "하네스 자료 계약이 맞지 않습니다. 운영자 확인이 필요합니다.",
    "invalid_profile": "허용된 하네스 연결 설정이 아닙니다.",
}


class HarnessReadError(RuntimeError):
    def __init__(self, code):
        self.code = code if code in ERRORS else "unavailable"
        super().__init__(ERRORS[self.code])


def epoch(value, *, nullable=True):
    if value is None and nullable:
        return None
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or value > 253402300799:
        raise HarnessReadError("schema_error")
    return float(value)


def stamp(value):
    return None if value is None else datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


def object_json(value):
    if not isinstance(value, str) or len(value) > 2_000_000:
        raise HarnessReadError("schema_error")
    try:
        result = json.loads(value, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, TypeError):
        raise HarnessReadError("schema_error") from None
    if not isinstance(result, dict):
        raise HarnessReadError("schema_error")
    return result


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,100}", value) or re.search(r"^(?:sk-|gh[pousr]_|github_pat_)", value, re.I):
        raise HarnessReadError("schema_error")
    return value


def safe_title(value):
    """Only the formal task title is eligible; suspicious titles are withheld."""
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        return "작업 이름 미제공"
    if re.search(r"[\x00-\x1f\x7f]|(?:[A-Za-z]:[\\/]|https?://|(?:^|\s)/|@)|(?:sk-|gh[pousr]_|github_pat_|Bearer\s)", value, re.I):
        return "작업 이름 비공개"
    return value.strip()


class HarnessReader:
    def __init__(self, database=None, *, profile=PROFILE, members=ACCOUNTS, clock=time.time):
        self.database = database
        self.members = tuple(members)
        self.clock = clock
        if profile != PROFILE or not self.members or len(set(self.members)) != len(self.members) or not set(self.members).issubset(ACCOUNTS):
            raise HarnessReadError("invalid_profile")

    @classmethod
    def from_env(cls, env=None):
        config = os.environ if env is None else env
        raw_members = config.get("AX_HARNESS_MEMBERS", "")
        members = tuple(m.strip() for m in raw_members.split(",") if m.strip()) if raw_members else ACCOUNTS
        return cls(config.get("AX_HARNESS_DB") or None, profile=config.get("AX_HARNESS_PROFILE", PROFILE), members=members)

    def snapshot(self):
        if not self.database:
            raise HarnessReadError("not_configured")
        try:
            selected = Path(self.database)
            if not selected.is_absolute() or not selected.is_file():
                raise HarnessReadError("unavailable")
            # mode=ro does not create a missing DB. Do not set immutable=1: the
            # live controller can use WAL, whose committed rows must be visible.
            uri = selected.resolve().as_uri() + "?mode=ro"
            with closing(sqlite3.connect(uri, uri=True, timeout=2, isolation_level=None)) as db:
                db.row_factory = sqlite3.Row
                db.execute("PRAGMA query_only=ON")
                db.execute("BEGIN")
                settings = {r["key"]: r["value"] for r in db.execute("SELECT key,value FROM settings WHERE key IN ('mode','formal_snapshot')")}
                members = list(db.execute("SELECT account,enabled FROM members"))
                jobs = list(db.execute("SELECT id,packet,status,created,attempt,lease_expires,run_deadline,CASE WHEN lease_hash IS NOT NULL AND length(lease_hash)>0 THEN 1 ELSE 0 END AS lease_present FROM jobs ORDER BY CASE WHEN status IN ('running','stopping','orphaned') THEN 0 ELSE 1 END,created DESC LIMIT 1001"))
                workers = list(db.execute("SELECT account,received_at,reported_at,metadata FROM worker_presence"))
                events = list(db.execute("SELECT id,at,actor,event,details FROM events ORDER BY id DESC LIMIT 201"))
                db.rollback()  # End the read snapshot, never commit any change.
            return self._project(settings, members, jobs, workers, events)
        except HarnessReadError:
            raise
        except sqlite3.Error:
            raise HarnessReadError("schema_error") from None
        except (OSError, TypeError, ValueError, KeyError, OverflowError):
            raise HarnessReadError("unavailable") from None

    def _project(self, settings, member_rows, job_rows, worker_rows, event_rows):
        now = epoch(self.clock(), nullable=False)
        mode = settings.get("mode")
        if mode not in ("on", "off", "stop") or "formal_snapshot" not in settings:
            raise HarnessReadError("schema_error")
        formal = object_json(settings["formal_snapshot"])
        approved = formal.get("approved_commit")
        if approved is not None and (not isinstance(approved, str) or not re.fullmatch(r"[0-9a-f]{40}", approved)):
            raise HarnessReadError("schema_error")
        tasks = formal.get("tasks")
        if not isinstance(tasks, dict) or len(tasks) > 1000:
            raise HarnessReadError("schema_error")
        task_map = {}
        for tid, task in tasks.items():
            if not isinstance(task, dict):
                raise HarnessReadError("schema_error")
            if task.get("owner") not in self.members:
                continue
            identifier(tid)
            if task.get("status") not in FORMAL_STATUSES:
                raise HarnessReadError("schema_error")
            task_map[tid] = {"id": tid, "owner": task["owner"], "title": safe_title(task.get("title")), "status": task["status"]}
        member_map = {m: False for m in self.members}
        for row in member_rows:
            if row["account"] in member_map:
                if row["enabled"] not in (0, 1):
                    raise HarnessReadError("schema_error")
                member_map[row["account"]] = bool(row["enabled"])
        updates = []
        jobs, job_map = [], {}
        for row in job_rows[:1000]:
            packet = object_json(row["packet"])
            tid, owner = packet.get("task_id"), packet.get("owner")
            kind = packet.get("kind", "implementation")
            if tid not in task_map or owner not in self.members:
                continue
            if kind not in ("implementation", "review") or (kind == "implementation" and owner != task_map[tid]["owner"]) or (kind == "review" and owner != "jeongiryang"):
                continue
            jid = identifier(row["id"])
            if packet.get("job_id") != jid or row["status"] not in JOB_STATUSES or type(row["attempt"]) is not int or not 0 <= row["attempt"] <= 2:
                raise HarnessReadError("schema_error")
            created, expires, deadline = epoch(row["created"], nullable=False), epoch(row["lease_expires"]), epoch(row["run_deadline"])
            updates.append(created)
            live = row["lease_present"] == 1 and expires is not None and deadline is not None and expires > now and deadline > now
            lease_state = "inactive" if row["status"] not in ("running", "stopping") else "unknown" if expires is None or deadline is None or not row["lease_present"] else "live" if live else "expired"
            job = {"id": jid, "owner": owner, "task_id": tid, "title": task_map[tid]["title"], "kind": kind,
                   "status": row["status"], "attempt": row["attempt"], "created_at": stamp(created),
                   "lease_expires_at": stamp(expires), "run_deadline": stamp(deadline), "lease_state": lease_state,
                   "activity_evidence": "unconfirmed", "is_running_confirmed": False, "view": "overview", "stage": None}
            jobs.append(job)
            job_map[jid] = job
        worker_map = {}
        for row in worker_rows:
            owner = row["account"]
            if owner not in self.members:
                continue
            metadata = object_json(row["metadata"])
            received, reported = epoch(row["received_at"], nullable=False), epoch(row["reported_at"], nullable=False)
            if metadata.get("engine") not in ("codex", "claude") or metadata.get("phase") not in IDLE_PHASES | ACTIVE_PHASES or metadata.get("source") != "fixed_worker":
                raise HarnessReadError("schema_error")
            jid = metadata.get("job_id")
            # A worker assigned outside the selected scope must not leak that
            # assignment or be presented as running a visible project's job.
            if jid is not None and (jid not in job_map or job_map[jid]["owner"] != owner):
                continue
            age = max(0, now - received)
            future = received > now + 5 or reported > now + 5
            updates.append(received)
            worker_map[owner] = {"owner": owner, "engine": metadata["engine"], "phase": metadata["phase"], "job_id": jid,
                                 "last_seen_at": stamp(received), "reported_at": stamp(reported), "age_seconds": round(age, 3),
                                 "presence": "online" if age < STALE_SECONDS and not future else "stale",
                                 "stale_after_seconds": STALE_SECONDS, "evidence_kind": "authenticated_worker_self_report"}
        for owner in self.members:
            worker_map.setdefault(owner, {"owner": owner, "engine": None, "phase": None, "job_id": None,
                "last_seen_at": None, "reported_at": None, "age_seconds": None, "presence": "never_seen",
                "stale_after_seconds": STALE_SECONDS, "evidence_kind": "authenticated_worker_self_report"})
        for job in jobs:
            worker = worker_map[job["owner"]]
            confirmed = (job["status"] == "running" and job["lease_state"] == "live" and mode == "on" and member_map[job["owner"]]
                         and worker["presence"] == "online" and worker["job_id"] == job["id"] and worker["phase"] in ACTIVE_PHASES)
            job["is_running_confirmed"] = bool(confirmed)
            if confirmed:
                job["activity_evidence"] = "recent_worker_and_live_lease"
            code = "running_confirmed" if confirmed else "stopping" if job["status"] == "stopping" else "lease_expired" if job["lease_state"] == "expired" else "automation_off" if job["status"] == "running" and (mode != "on" or not member_map[job["owner"]]) else "worker_unconfirmed" if job["status"] == "running" else job["status"]
            job.update(reason_code=code, reason=REASONS[code])
        events = []
        for row in reversed(event_rows[:200]):
            kind = row["event"]
            if kind not in EVENT_MESSAGES:
                continue
            details = object_json(row["details"])
            jid = details.get("job_id")
            if kind not in ("mode", "formal_snapshot") and jid not in job_map:
                continue
            if kind == "mode" and details.get("member") is not None and details.get("member") not in self.members:
                continue
            at = epoch(row["at"], nullable=False)
            if type(row["id"]) is not int or row["id"] < 1:
                raise HarnessReadError("schema_error")
            item = {"id": row["id"], "at": stamp(at), "type": kind, "message": EVENT_MESSAGES[kind]}
            if jid in job_map:
                item.update(job_id=jid, owner=job_map[jid]["owner"])
            outcome = details.get("outcome")
            if outcome in ("review_requested", "completed_review", "blocked", "failed"):
                item["outcome"] = outcome
            updates.append(at)
            events.append(item)
        notices = ["읽기 전용 조회입니다. 모드·Worker·작업·lease·하네스 기록을 변경하지 않습니다.",
                   "Worker 상태는 인증된 자기보고입니다. 모델 성공·제품 Skill 실행·정식 완료를 뜻하지 않습니다.",
                   "개발 작업은 전체 현황에 표시합니다. 제품기획 다섯 Skill로 임의 분류하지 않습니다."]
        if len(job_rows) > 1000 or len(event_rows) > 200:
            notices.append("표시 개수에 상한이 있어 일부 과거 기록은 생략되었습니다.")
        return {"schema_version": 1, "source": {"kind": "team_controller_sqlite_readonly", "repo": REPO,
                    "observed_at": stamp(now), "source_updated_at": stamp(max(updates)) if updates else None, "approved_commit": approved},
                "global_mode": mode, "members": [{"id": m, "enabled": member_map[m]} for m in self.members],
                "jobs": jobs, "workers": [worker_map[m] for m in self.members], "events": events,
                "formal_tasks": list(task_map.values()), "notices": notices}
