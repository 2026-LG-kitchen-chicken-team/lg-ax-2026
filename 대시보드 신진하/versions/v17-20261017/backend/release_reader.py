"""Read only an installed product's observer artifacts; never execute JavaScript or native AI.

The selected product folder is explicit. No runtime DB, raw session log, home
directory, credential file, or global latest session is opened by this reader.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from .harness_reader import HarnessReadError

# The installed product decides the version: its own install record (product-install.json) and, for a judge ZIP,
# runtime-data/judge-setup.json. No release, asset or install fingerprint is pinned here.
INSTALL_FORMATS = {"codex-product-install-v1": "codex", "portable-product-install-v1": None}
RELEASE_PATTERN = re.compile(r"product-v\d+\.\d+\.\d+(?:-[a-z0-9.-]+)?")
# office.py install refreshes the observer itself; its files may differ from the product's install record.
OBSERVER_FILES = re.compile(r"web/prototypes/agent-office/[^/]+")
CONTINUATIONS = ("handback_delivered", "notification")
SKILLS = {"evidence-retrieval", "web-evidence-collection", "needs-structuring", "feature-comparison", "concept-writing", "review-and-revise"}
ROLES = {"main", "product_official_researcher", "product_review_researcher", "product_evidence_reviewer", "other_subagent", "unknown_subagent", "unknown_skill"}
NODES = ROLES | SKILLS
KINDS = {"lifecycle", "tool", "delegate", "handback", "handback_delivered", "notification", "skill_load", "skill_op", "file", "shell", "web", "request", "subagent", "turn_end", "turn_cancelled", "session"}
PHASES = {"point", "start", "end", "fail"}
BASES = {"observed", "instruction_loaded", "command_based_mapping"}
TS_BASES = {"hook_received", "codex_log", "reader_received"}
AREAS = {"exports", "web_evidence", "catalogs", "deliverables", "conversation", "runtime", "docs", "skills", "agents", "harness", "outside"}
PROGRAMS = {"ls", "dir", "cat", "type", "head", "tail", "find", "grep", "rg", "wc", "pwd", "cd", "echo", "mkdir", "cp", "mv", "rm", "python", "python3", "py", "uv", "git", "sed", "awk", "jq", "curl", "wget", "sort", "uniq", "node", "npm", "npx", "get-childitem", "get-content", "set-location", "test-path", "select-string", "new-item", "remove-item", "copy-item", "move-item", "invoke-webrequest", "out-file", "set-content", "get-item", "write-output", "measure-object", "product-doctor.py", "other"}
MAX_BYTES = 16 * 1024 * 1024
MAX_EVENTS = 1500
ERRORS = {
    "not_configured": "제품 하네스 폴더 연결 설정을 기다리고 있습니다.",
    "not_installed": "선택한 폴더의 제품 설치 기록을 확인할 수 없습니다.",
    "release_mismatch": "선택한 폴더의 파일이 그 폴더의 제품 설치 기록과 일치하지 않습니다.",
    "unsafe_path": "제품 관측 파일의 안전한 경계를 확인할 수 없습니다.",
    "schema_error": "제품 관측 파일의 형식이 맞지 않습니다.",
    "unavailable": "제품 관측 파일을 읽을 수 없습니다.",
}


class ReleaseReadError(HarnessReadError):
    def __init__(self, code):
        self.code = code if code in ERRORS else "unavailable"
        RuntimeError.__init__(self, ERRORS[self.code])


def no_duplicates(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("duplicate")
        result[name] = value
    return result


def decoder():
    return json.JSONDecoder(object_pairs_hook=no_duplicates, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))


def parse_object(raw):
    try:
        result = decoder().decode(raw)
    except (ValueError, TypeError, RecursionError):
        raise ReleaseReadError("schema_error") from None
    if not isinstance(result, dict):
        raise ReleaseReadError("schema_error")
    return result


def id_token(value, limit=200):
    if not isinstance(value, str) or not 1 <= len(value) <= limit or not re.fullmatch(r"[A-Za-z0-9_.:-]+", value):
        return None
    if re.match(r"(?:sk[-_]|gh[pousr]_|github_pat_|Bearer|eyJ)", value, re.I):
        return None
    return value


def code_token(value):
    return value if isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,59}", value) and id_token(value) else None


def timestamp(value):
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (ValueError, OverflowError):
        return None


def seconds(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def number(value, maximum=1_000_000_000):
    return value if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= maximum else None


def binding(value):
    if not isinstance(value, dict):
        return None
    keys = ("session_id", "turn_id", "request_key")
    values = {k: id_token(value.get(k)) for k in keys}
    return values if all(values.values()) else None


def safe_detail(raw):
    if not isinstance(raw, dict):
        return {}
    result = {}
    for name in ("interrupted", "background", "accepted", "other_skill_operation"):
        if type(raw.get(name)) is bool:
            result[name] = raw[name]
    for name in ("duration_ms", "result_version", "revision_count"):
        value = number(raw.get(name))
        if value is not None and (name == "duration_ms" or type(value) is int):
            result[name] = value
    if type(raw.get("exit_code")) is int and -255 <= raw["exit_code"] <= 65535:
        result["exit_code"] = raw["exit_code"]
    for name in ("reason", "error", "turn_status", "response_status"):
        value = code_token(raw.get(name))
        if value:
            result[name] = value
    for name in ("launched_agent_id", "from_agent_id"):
        value = id_token(raw.get(name))
        if value:
            result[name] = value
    host = raw.get("host")
    if isinstance(host, str) and 1 <= len(host) <= 253 and re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", host):
        result["host"] = host.lower()
    if raw.get("area") in AREAS:
        result["area"] = raw["area"]
    if raw.get("skill") in SKILLS:
        result["skill"] = raw["skill"]
    if isinstance(raw.get("programs"), list):
        result["programs"] = list(dict.fromkeys(p for p in raw["programs"] if isinstance(p, str) and p in PROGRAMS))[:6]
    joined = binding(raw.get("business_binding"))
    if joined:
        result["business_binding"] = joined
    return result


def event_projection(raw, engine):
    if not isinstance(raw, dict) or type(raw.get("v")) is not int or raw.get("v") != 1 or raw.get("src") != engine or raw.get("kind") not in KINDS or raw.get("phase") not in PHASES or raw.get("basis") not in BASES:
        raise ReleaseReadError("schema_error")
    event_id, ts, session = id_token(raw.get("id")), timestamp(raw.get("ts")), id_token(raw.get("session"))
    if not event_id or not ts or not session or raw.get("ts_basis") not in TS_BASES:
        raise ReleaseReadError("schema_error")
    actor, node = raw.get("actor"), raw.get("node")
    if actor not in ROLES or node not in NODES:
        raise ReleaseReadError("schema_error")
    ops = []
    if isinstance(raw.get("ops"), list):
        for item in raw["ops"][:8]:
            if isinstance(item, dict) and item.get("skill") in SKILLS and id_token(item.get("op"), 60):
                ops.append({"skill": item["skill"], "op": item["op"]})
    return {"v": 1, "id": event_id, "ts": ts, "ts_basis": raw["ts_basis"], "src": engine,
            "hook": id_token(raw.get("hook"), 60), "session": session, "prompt_id": id_token(raw.get("prompt_id")),
            "agent_id": id_token(raw.get("agent_id")), "actor": actor, "tool": id_token(raw.get("tool"), 100),
            "call": id_token(raw.get("call")), "kind": raw["kind"], "node": node, "op": id_token(raw.get("op"), 60),
            "ops": ops, "phase": raw["phase"], "basis": raw["basis"], "detail": safe_detail(raw.get("detail"))}


def selected_native(events):
    """Select context from request/session-start, never a late old tool result.

    Returns (session, prompts, floor). Claude Code delivers a background role's result (and task notices) as a new
    prompt id; those prompts continue the selected request instead of starting another one."""
    main = [(index, e) for index, e in enumerate(events) if e["actor"] == "main" and not e.get("agent_id")]
    anchors = [(index, e) for index, e in main if e["kind"] == "request" or (e["kind"] == "session" and e["phase"] == "start")]
    if not main or not anchors:
        return None, set(), len(events)
    index, anchor = anchors[-1]
    session = anchor["session"]
    starts = [i for i, e in main if e["session"] == session and e["kind"] == "session" and e["phase"] == "start"]
    floor = starts[-1] if starts else 0
    requests = [(i, e) for i, e in main if i >= floor and e["session"] == session and e["kind"] == "request"]
    if requests:
        index, request = requests[-1]
        prompts, children = {request["prompt_id"]}, set()
        # A late old child must not introduce a continuation into this request. Unknown parentage stays unbound.
        for current in events[index:]:
            if current["session"] != session:
                continue
            detail = current.get("detail") or {}
            is_main = current["actor"] == "main" and not current.get("agent_id")
            if is_main and current["kind"] in CONTINUATIONS and current["prompt_id"] and detail.get("from_agent_id") in children:
                prompts.add(current["prompt_id"])
            if (not current["prompt_id"] or current["prompt_id"] not in prompts) and current.get("agent_id") not in children:
                continue
            if current["kind"] == "delegate" and detail.get("launched_agent_id"):
                children.add(detail["launched_agent_id"])
            if current["kind"] == "subagent" and current["phase"] == "start" and current.get("agent_id"):
                children.add(current["agent_id"])
        return session, prompts, index
    # A resumed session with no new request is not the old turn's completion.
    prompt = None if starts else anchor["prompt_id"]
    return session, {prompt}, floor if starts else index


def safe_db(raw, events):
    if not isinstance(raw, dict) or raw.get("available") is not True:
        return {"available": False, "binding_status": "unavailable", "binding": None, "read_at": timestamp(raw.get("read_at")) if isinstance(raw, dict) else None}
    read_at = timestamp(raw.get("read_at"))
    expected = binding(raw.get("binding"))
    selected_session, current_prompts, floor = selected_native(events)
    selected = [e for e in events[floor:] if e["actor"] == "main" and e["session"] == selected_session]
    matched = expected and any(e["detail"].get("business_binding") == expected and e["prompt_id"] in current_prompts for e in selected)
    if not matched:
        return {"available": True, "binding_status": "unmatched", "binding": None, "read_at": read_at}
    output = {"available": True, "binding_status": "matched", "binding": expected, "read_at": read_at,
              "workflow": None, "workflow_events": [], "request": None, "turn": None, "results": number(raw.get("results")),
              "candidates": [], "evidence_delivered": number(raw.get("evidence_delivered")), "evidence_reviews": number(raw.get("evidence_reviews")),
              "cancelled": raw.get("cancelled") is True, "latest_export": None}
    workflow = raw.get("workflow")
    if isinstance(workflow, dict):
        output["workflow"] = {"research_id": id_token(workflow.get("research_id")), "started_at": timestamp(workflow.get("started_at")),
                              "budget_seconds": number(workflow.get("budget_seconds")), "research_stopped_at": timestamp(workflow.get("research_stopped_at")), "finished_at": timestamp(workflow.get("finished_at"))}
    for event in (raw.get("workflow_events") or [])[-80:]:
        if not isinstance(event, dict) or event.get("kind") not in ("research_plan", "source_scan", "research_stop", "analysis_scope", "finish"):
            continue
        item = {"kind": event["kind"], "observed_at": timestamp(event.get("observed_at"))}
        for name in ("status", "source_type", "code", "layout_review"):
            if code_token(event.get(name)):
                item[name] = event[name]
        for name in ("reviews", "sources"):
            if number(event.get(name)) is not None:
                item[name] = event[name]
        host = safe_detail({"host": event.get("host")}).get("host")
        if host:
            item["host"] = host
        output["workflow_events"].append(item)
    request = raw.get("request")
    if isinstance(request, dict) and request.get("turn_id") == expected["turn_id"] and request.get("request_key") == expected["request_key"]:
        output["request"] = {"turn_id": expected["turn_id"], "request_key": expected["request_key"], "status": code_token(request.get("status"))}
    turn = raw.get("turn")
    if isinstance(turn, dict) and turn.get("turn_id") == expected["turn_id"]:
        output["turn"] = {"turn_id": expected["turn_id"], "status": code_token(turn.get("status")), "revision_count": number(turn.get("revision_count")),
                          "result_version": number(turn.get("result_version")), "valid": turn.get("valid") is True, "created_at": timestamp(turn.get("created_at"))}
    for candidate in (raw.get("candidates") or [])[-3:]:
        if not isinstance(candidate, dict):
            continue
        item = {"result_version": number(candidate.get("result_version")), "created_at": timestamp(candidate.get("created_at")),
                "status": code_token(candidate.get("status")), "counts": {}}
        counts = candidate.get("counts")
        if isinstance(counts, dict):
            item["counts"] = {n: number(counts.get(n)) for n in ("pains", "existing_features", "remaining_pains", "concepts", "evidence_refs")}
        for name in ("contract_valid", "structural_valid", "acceptance_ready"):
            if type(candidate.get(name)) is bool:
                item[name] = candidate[name]
        if code_token(candidate.get("semantic_status")):
            item["semantic_status"] = candidate["semantic_status"]
        output["candidates"].append(item)
    # Export file names/absolute paths and document content are intentionally not
    # forwarded. A separate result view must verify exact web_binding+file hash.
    latest = raw.get("latest_export")
    if isinstance(latest, dict):  # observe.py records the export file's modified_at
        output["latest_export"] = {"available": True, "created_at": timestamp(latest.get("created_at") or latest.get("modified_at"))}
    return output


class ReleaseReader:
    def __init__(self, workspace=None, *, clock=time.time, native_sessions_root=None):
        self.workspace = Path(workspace) if workspace else None
        self.clock = clock
        self.native_sessions_root = native_sessions_root

    @classmethod
    def from_env(cls, env=None):
        config = os.environ if env is None else env
        return cls(config.get("AX_RELEASE_WORKSPACE"), native_sessions_root=config.get('AX_RELEASE_NATIVE_SESSIONS'))

    def _path(self, relative, *, optional=False):
        root = self.workspace
        if root is None or not root.is_absolute() or not root.is_dir():
            raise ReleaseReadError("not_installed")
        selected = PurePosixPath(relative)
        if not isinstance(relative, str) or selected.is_absolute() or ".." in selected.parts or "\\" in relative or ":" in relative or selected.as_posix() != relative:
            raise ReleaseReadError("unsafe_path")
        path = root
        for part in selected.parts:
            path = path / part
            if path.is_symlink() or (path.exists() and getattr(path.lstat(), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
                raise ReleaseReadError("unsafe_path")
        if not path.resolve().is_relative_to(root.resolve()):
            raise ReleaseReadError("unsafe_path")
        if not path.exists():
            if optional:
                return None
            raise ReleaseReadError("not_installed")
        if not path.is_file() or path.stat().st_size > MAX_BYTES:
            raise ReleaseReadError("unsafe_path")
        return path

    def _read(self, relative, *, optional=False):
        path = self._path(relative, optional=optional)
        if path is None:
            return None
        with path.open("rb") as handle:
            raw = handle.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ReleaseReadError("unsafe_path")
        return raw

    def _verify(self):
        """The folder's own install record: its format names the engine and every product file must still match it."""
        raw = self._read("product-install.json")
        fingerprint = hashlib.sha256(raw).hexdigest()
        record = parse_object(raw.decode("utf-8"))
        if record.get("format") not in INSTALL_FORMATS:
            raise ReleaseReadError("release_mismatch")
        engine = INSTALL_FORMATS[record["format"]] or record.get("engine")
        if engine not in ("codex", "claude"):
            raise ReleaseReadError("release_mismatch")
        entries = record.get("files")
        if not isinstance(entries, list) or not entries or len(entries) > 400 or set(record.get("skills", [])) != SKILLS:
            raise ReleaseReadError("release_mismatch")
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) or entry["path"] in seen or not re.fullmatch(r"[a-f0-9]{64}", entry.get("sha256", "")):
                raise ReleaseReadError("release_mismatch")
            seen.add(entry["path"])
            if OBSERVER_FILES.fullmatch(entry["path"]):
                continue
            data = self._read(entry["path"])
            if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise ReleaseReadError("release_mismatch")
        return engine, fingerprint

    def _release(self):
        """The judge ZIP's setup mark names the product release; other installs leave it unknown (None)."""
        raw = self._read("runtime-data/judge-setup.json", optional=True)
        if raw is None:
            return None
        try:
            release = parse_object(raw.decode("utf-8")).get("release")
        except (ReleaseReadError, UnicodeError):
            return None
        return release if isinstance(release, str) and RELEASE_PATTERN.fullmatch(release) else None

    def snapshot(self):
        if self.workspace is None:
            raise ReleaseReadError("not_configured")
        try:
            engine, fingerprint = self._verify()
            live_raw = self._read("runtime-data/agent-office/live.js", optional=True)
            lines_raw = self._read("runtime-data/agent-office/events.jsonl", optional=True)
            db_raw = self._read("runtime-data/agent-office/snapshot.json", optional=True)
            live, db, raw_events, updates = {}, None, [], []
            if live_raw is not None:
                live_text = live_raw.decode("utf-8")
                match = re.match(r"\A(?:/\* agent-office observe\.py writes this file; do not edit\. \*/\r?\n)?window\.LGAX_OFFICE_LIVE = ", live_text)
                if not match:
                    raise ReleaseReadError("schema_error")
                try:
                    live, end = decoder().raw_decode(live_text, match.end())
                except (ValueError, RecursionError):
                    raise ReleaseReadError("schema_error") from None
                if live_text[end:].strip() != ";" or not isinstance(live, dict) or live.get("kind") != "lgax-agent-office-live" or type(live.get("version")) is not int or live.get("version") != 1 or not isinstance(live.get("events"), list):
                    raise ReleaseReadError("schema_error")
                raw_events.extend(live["events"][-MAX_EVENTS:])
                db = live.get("db")
                if timestamp(live.get("written_at")):
                    updates.append(timestamp(live["written_at"]))
            if lines_raw is not None:
                for line in lines_raw.splitlines(keepends=True):
                    # An append in progress is not a complete event. Never parse
                    # or expose the unfinished last JSONL record.
                    if not line.endswith(b"\n"):
                        continue
                    if line.strip():
                        raw_events.append(parse_object(line.decode("utf-8")))
                raw_events = raw_events[-MAX_EVENTS * 2:]
            if db_raw is not None:
                separate = parse_object(db_raw.decode("utf-8"))
                separate_at = timestamp(separate.get("read_at"))
                live_at = timestamp(db.get("read_at")) if isinstance(db, dict) else None
                if not isinstance(db, dict) or (seconds(separate_at) if separate_at else -1) >= (seconds(live_at) if live_at else -1):
                    db = separate
            by_id = {}
            for raw in raw_events:
                event = event_projection(raw, engine)
                if event["id"] in by_id and by_id[event["id"]] != event:
                    raise ReleaseReadError("schema_error")
                by_id[event["id"]] = event
            events = sorted(by_id.values(), key=lambda e: seconds(e["ts"]))[-MAX_EVENTS:]
            summary = safe_db(db, events)
            updates.extend(e["ts"] for e in events)
            if timestamp(summary.get("read_at")):
                updates.append(summary["read_at"])
            now = datetime.fromtimestamp(self.clock(), timezone.utc).isoformat().replace("+00:00", "Z")
            status = "waiting_for_session" if not events else "recorded"
            selected, prompts, floor = selected_native(events)
            opened, closed, turn_open = set(), set(), False
            current = [e for e in events[floor:] if e["session"] == selected and e["prompt_id"] in prompts]
            for event in current:
                if event["kind"] in ("request", *CONTINUATIONS) and event["actor"] == "main":
                    turn_open = True
                if event["call"]:
                    # Async hooks may record a call's end just before its start; that start is already closed.
                    if event["phase"] == "start" and event["call"] not in closed:
                        opened.add(event["call"])
                    elif event["phase"] in ("end", "fail"):
                        opened.discard(event["call"])
                        closed.add(event["call"])
                if event["kind"] == "subagent":
                    aid = "agent:" + (event["agent_id"] or event["actor"])
                    opened.add(aid) if event["phase"] == "start" else opened.discard(aid)
                if event["kind"] in ("turn_end", "turn_cancelled") and event["actor"] == "main":
                    turn_open = False
                    if event["kind"] == "turn_cancelled":
                        opened.clear()
                if event["kind"] == "session" and event["phase"] == "end" and event["actor"] == "main":
                    opened.clear()
                    turn_open = False
            if current and (opened or turn_open) and -5 <= self.clock() - seconds(current[-1]["ts"]) <= 120:
                status = "observing"
            from .release_activity import native_activity
            request = events[floor] if floor < len(events) and events[floor]["kind"] == "request" else None
            prompt = request["prompt_id"] if request else next(iter(prompts), None)
            activity = native_activity(self.workspace, self.native_sessions_root, selected, prompt) if engine == 'codex' else None
            return {"schema_version": 1, "activity": activity, "source": {"kind": "lgax_release_observer", "release": self._release(), "engine": engine,
                        "observed_at": now, "source_updated_at": max(updates, key=seconds) if updates else None,
                        "observer_status": status, "asset_sha256": None, "product_install_sha256": fingerprint}, "events": events, "db": summary,
                    "notices": ["설치된 제품 폴더의 관측 파일만 읽습니다. 모델·업무·훅·원본 DB를 실행하거나 변경하지 않습니다.",
                                "관측 중 표시는 최근 열린 사건의 기록이며 프로세스 생존·모델 성공의 독립 확인이 아닙니다.",
                                "Skill 지침 읽기와 명령 기반 작업 추정을 실제 의미 판단·완료와 구분합니다."]}
        except ReleaseReadError:
            raise
        except (OSError, UnicodeError, ValueError, TypeError, KeyError, RecursionError, OverflowError):
            raise ReleaseReadError("schema_error") from None
