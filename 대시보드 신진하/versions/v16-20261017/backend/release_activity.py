"""Allowlisted activity facts from ONE observer-selected native Codex turn.

No model calls, commands, prompts, messages or reasoning are returned. Public
progress messages only select fixed labels; they never certify a Skill call.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import stat

SKILLS = ('evidence-retrieval', 'web-evidence-collection', 'needs-structuring',
          'feature-comparison', 'concept-writing', 'review-and-revise')
STAGES = dict(zip(SKILLS, ('retrieve', 'retrieve', 'structure', 'compare', 'concept', 'validate')))
_CACHE = {}


def _file(root, parts):
    if not root.is_absolute() or not root.is_dir():
        return None
    path = root
    for part in ('', *parts):
        if part:
            path = path / part
        if path.is_symlink() or (path.exists() and getattr(path.lstat(), 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)):
            return None
    return path if path.is_file() and path.resolve().is_relative_to(root.resolve()) else None


def _text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return '\n'.join(x.get('text', '') for x in value if isinstance(x, dict) and isinstance(x.get('text'), str))
    return ''


def _report(text):
    lower = text.lower()
    if any(x in text for x in ('SQLite', 'sqlite', '파일 읽기/쓰기', '파일·SQLite')):
        return 'check_storage', None
    if any(x in text for x in ('설치 점검', '실행 준비', '설치 지침', '6개 Skill', '준비 상태')):
        return 'check_setup', None
    for words, code, stage in ((('콘셉트',), 'write_concepts', 'concept'), (('기능 대조', '기존 기능과'), 'compare_features', 'compare'),
                                (('니즈 구조화', '불편을 구조화'), 'structure_needs', 'structure'), (('검토·수정', '검토 및 수정'), 'review_results', 'validate'),
                                (('자료 조사', '웹 조사', '후기를 조사', '공식 자료를 조사'), 'research_sources', 'retrieve')):
        if any(x in text for x in words) and any(x in text for x in ('하겠습니다', '진행', '시작', '중입니다')):
            return code, stage
    return None, None


def _decode_output(value):
    if not isinstance(value, str) or len(value) > 2 * 1024 * 1024:
        return {}
    try:
        data = json.loads(value)
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


def project_activity(rows, workspace, session, prompt):
    """Pure projection, shared by the runtime and fixture tests."""
    meta = next((r.get('payload', {}) for r in rows[:5] if r.get('type') == 'session_meta'), {})
    if meta.get('id') != session or os.path.normcase(os.path.abspath(meta.get('cwd', ''))) != os.path.normcase(os.path.abspath(workspace)) or meta.get('parent_thread_id'):
        return None
    starts = [i for i, r in enumerate(rows) if r.get('type') == 'event_msg' and r.get('payload', {}).get('type') == 'task_started']
    if not starts or rows[starts[-1]].get('payload', {}).get('turn_id') != prompt:
        return None
    current = rows[starts[-1]:]
    out = {'kind': 'codex_native_activity', 'session_id': session, 'prompt_id': prompt,
           'state': 'working', 'intent': 'general', 'task_code': 'main_work', 'reported_stage': None,
           'last_event_at': current[-1].get('timestamp'), 'checks': {}, 'installed_skills': [], 'skill_reads': [],
           'command_count': 0, 'web_count': 0, 'actions': []}
    read = {}
    def action(key, ts, code, state='completed', stage=None):
        out['actions'].append({'id': str(key)[:180], 'time': ts, 'code': code, 'status': state, 'stage': stage})
    for i, row in enumerate(current):
        payload = row.get('payload', {})
        if not isinstance(payload, dict):
            continue
        ts = row.get('timestamp')
        if row.get('type') == 'response_item' and payload.get('type') == 'message' and payload.get('role') == 'assistant' and payload.get('phase') == 'commentary':
            # Read only public commentary; never inspect reasoning/analysis.
            if payload.get('channel') == 'analysis':
                continue
            code, stage = _report(_text(payload.get('content')))
            if code:
                out.update(task_code=code, reported_stage=stage)
                if stage:
                    out['intent'] = 'planning'
                elif code in ('check_setup', 'check_storage') and out['intent']!='planning':
                    out['intent'] = 'readiness'
                action('report-' + str(i), ts, code, 'reported', stage)
        if row.get('type') == 'event_msg' and payload.get('type') == 'item_completed':
            item = payload.get('item', {})
            if not isinstance(item, dict):
                continue
            key = item.get('id', 'item-' + str(i))
            if item.get('type') == 'CommandExecution':
                out['command_count'] += 1
                command = item.get('command', '')
                command = ' '.join(x for x in command if isinstance(x, str)) if isinstance(command, list) else command
                command = command if isinstance(command, str) else ''
                ok = item.get('status') not in ('failed', 'cancelled') and item.get('exit_code') == 0
                raw = item.get('aggregated_output') or item.get('stdout') or ''
                data = _decode_output(raw)
                code, stage = 'local_command', None
                if ok and 'SKILL.md' in command and re.search(r'(?i)\b(get-content|cat|type|head|sed)\b', command) and isinstance(raw, str):
                    # Output frontmatter supports Join-Path/foreach reads without
                    # evaluating PowerShell or mistaking installation for use.
                    names = set(re.findall(r'^name:\s*[\"\']?([a-z0-9-]+)[\"\']?\s*$', raw, re.M)) & set(SKILLS)
                    for skill in names:
                        read[skill] = {'id': skill, 'time': ts, 'basis': 'read_command_output'}
                    if names:
                        code = 'read_skill_instructions'
                if 'installed_skills' in data and isinstance(data.get('errors'), list) and 'common_tool_exit_code' in data and ('product-doctor' in command or 'product_doctor' in command):
                    out['checks']['installation'] = bool(ok and not data['errors'] and data['common_tool_exit_code'] == 0)
                    installed = data['installed_skills']
                    names = installed.keys() if isinstance(installed, dict) else installed if isinstance(installed, list) else []
                    out['installed_skills'] = sorted({x if isinstance(x, str) else x.get('name', '') for x in names if isinstance(x, (str, dict))} & set(SKILLS))
                    code = 'check_setup'
                    if out['intent']!='planning':out['intent']='readiness'
                for native, check in (('file_read_write', 'file'), ('sqlite_disk_commit_read', 'sqlite')):
                    if isinstance(data.get(native), bool):
                        out['checks'][check] = bool(ok and data[native])
                        code = 'check_storage'
                        if out['intent']!='planning':out['intent']='readiness'
                for skill in SKILLS:
                    if re.search(r'skills[\\/]+' + re.escape(skill) + r'[\\/]+scripts[\\/]+run\.py', command):
                        stage = STAGES[skill]
                        out['intent']='planning'
                        code = {'retrieve': 'research_sources', 'structure': 'structure_needs', 'compare': 'compare_features', 'concept': 'write_concepts', 'validate': 'review_results'}[stage]
                        break
                action(key, ts, code, 'completed' if ok else 'failed', stage)
            elif item.get('type') == 'Extension' and item.get('kind') == 'web.search':
                out['web_count'] += 1
                action(key, ts, 'web_lookup')
        if row.get('type') == 'event_msg' and payload.get('type') in ('task_complete', 'turn_aborted'):
            if payload.get('turn_id') not in (None, prompt):
                continue
            out['state'] = 'cancelled' if payload['type'] == 'turn_aborted' else 'finished'
            out['reported_stage'] = None
            action('turn-' + str(i), ts, 'readiness_finished' if out['intent'] == 'readiness' else 'turn_finished', out['state'])
    out['skill_reads'] = sorted(read.values(), key=lambda r: r['id'])
    out['actions'] = out['actions'][-12:]
    return out


def native_activity(workspace, sessions_root, session, prompt):
    if not sessions_root or not re.fullmatch(r'[a-f0-9-]{36}', session or '') or not re.fullmatch(r'[a-f0-9-]{36}', prompt or ''):
        return None
    try:
        root = Path(sessions_root)
        state_path = _file(Path(workspace), ('runtime-data', 'agent-office', 'codex-follow.json'))
        if not state_path or state_path.stat().st_size > 4 * 1024 * 1024:
            return None
        info = json.loads(state_path.read_text(encoding='utf-8')).get('sessions', {}).get(session, {})
        names = list(info.get('threads', {}))
        pattern = re.compile(r'rollout-(\d{4})-(\d{2})-(\d{2})T[0-9-]+-' + re.escape(session) + r'\.jsonl')
        for name in names:
            match = pattern.fullmatch(name)
            if not match:
                continue
            path = _file(root, (*match.groups(), name))
            if not path or path.stat().st_size > 32 * 1024 * 1024:
                return None
            stamp = path.stat()
            key = (str(path), str(workspace), session, prompt, stamp.st_mtime_ns, stamp.st_size)
            if key in _CACHE:
                return _CACHE[key]
            rows = []
            with path.open('rb') as stream:
                for line in stream:
                    if len(line) > 1024 * 1024 or not line.endswith(b'\n'):
                        continue
                    try:
                        row = json.loads(line)
                        if isinstance(row, dict):
                            rows.append(row)
                    except ValueError:
                        continue
            result = project_activity(rows, workspace, session, prompt)
            if len(_CACHE) >= 8:
                _CACHE.pop(next(iter(_CACHE)))
            _CACHE[key] = result
            return result
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        return None
    return None
