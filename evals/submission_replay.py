"""Offline submission input comparison, never extraction, execution or approval.

verify_replay accepts ZIP bytes, an independently retained manifest SHA256 and
commit, and a filming record. The record contains code_commit, filming_commit,
demo_run_id, a shared-contract Run, dataset (path/sha256/dataset_id/version/
source_kind), documents (path/sha256/source_id/model_id/document_version/
source_kind), model_manifest (path/sha256 of a JSON model list), models
(id/revision/digest/runtime/settings), and commands (argv
lists). Documents cover every evidence source in the dataset. Model revision
or digest must be pinned; unknown metadata is held, never filled in.

Commands are untrusted display data, including when status is consistent.
This checks consistency against caller-supplied pins, not Git authenticity,
actual filming, model execution, semantic quality or final submission readiness.
The existing packager's Git-backed verify remains a separate trusted step.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import io
import json
import re
import stat
import zipfile

from jsonschema import ValidationError
from lgax_contracts import load_schema, validate
from scripts.package_submission import (
    GUIDE_PATH, MANIFEST_PATH, MAX_FILES, MAX_FILE_BYTES, MAX_TOTAL_BYTES,
    REQUIRED_FILES, SKILLS, PackageError, _check_content, _deny_source_path,
    _safe_name, digest,
)


class ReplayError(ValueError):
    def __init__(self, code: str, location: str):
        self.code, self.location = code, location
        super().__init__(code)


def _require(condition, code, location):
    if not condition:
        raise ReplayError(code, location)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _hex(value, lengths=(64,)):
    return isinstance(value, str) and len(value) in lengths and re.fullmatch('[0-9a-f]+', value) is not None


def _pinned_revision(value):
    return (_text(value) and value.strip().casefold() not in
            ('main', 'master', 'latest', 'unknown', 'unmeasured', 'null', 'none', 'pending')
            and not value.startswith('<'))


def _model_complete(model):
    if not isinstance(model, dict):
        return False
    revision, model_digest = model.get('revision'), model.get('digest')
    valid_digest = isinstance(model_digest, str) and _hex(model_digest.removeprefix('sha256:'))
    settings = model.get('settings')
    return (_text(model.get('id')) and _text(model.get('runtime'))
            and (revision is None or _pinned_revision(revision))
            and (model_digest is None or valid_digest)
            and (_pinned_revision(revision) or valid_digest)
            and isinstance(settings, dict) and any(value is not None for value in settings.values()))


def _json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, 'DUPLICATE_JSON_KEY', 'json')
            result[key] = value
        return result

    def constant(_):
        raise ReplayError('INVALID_JSON', 'json')

    return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)


def _archive(data):
    _require(isinstance(data, bytes) and len(data) <= MAX_TOTAL_BYTES + 16 * 1024 * 1024,
             'ARCHIVE_LIMIT', 'archive')
    contents, modes, names = {}, {}, set()
    total = 0
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        _require(len(archive.infolist()) <= MAX_FILES + 2, 'ARCHIVE_LIMIT', 'archive')
        for info in archive.infolist():
            name = info.filename
            _require(info.orig_filename == name, 'UNSAFE_ENTRY', 'archive')
            portable = _safe_name(name)
            _require(portable not in names, 'DUPLICATE_ENTRY', 'archive')
            names.add(portable)
            total += info.file_size
            mode = info.external_attr >> 16
            _require(not info.is_dir() and not info.flag_bits & 1
                     and stat.S_IFMT(mode) == stat.S_IFREG
                     and info.compress_type == zipfile.ZIP_STORED,
                     'UNSAFE_ENTRY', 'archive')
            _require(info.file_size <= MAX_FILE_BYTES and total <= MAX_TOTAL_BYTES,
                     'ARCHIVE_LIMIT', 'archive')
            if name not in (MANIFEST_PATH, GUIDE_PATH):
                _deny_source_path(name)
            contents[name] = archive.read(info)
            _check_content(name, contents[name])
            modes[name] = mode
    # A file cannot also be a directory when reproduced on disk.
    for name in names:
        _require(not any('/'.join(name.split('/')[:i]) in names
                         for i in range(1, len(name.split('/')))), 'PATH_COLLISION', 'archive')
    return contents, modes


def _source(contents, modes, commit, manifest_sha256):
    _require(MANIFEST_PATH in contents and GUIDE_PATH in contents, 'MISSING_MANIFEST', 'archive')
    _require(digest(contents[MANIFEST_PATH]) == manifest_sha256, 'MANIFEST_HASH_MISMATCH', MANIFEST_PATH)
    manifest = _json(contents[MANIFEST_PATH])
    _require(isinstance(manifest, dict) and type(manifest.get('schema_version')) is int
             and manifest['schema_version'] == 1 and manifest.get('source_snapshot') == 'all_tracked_git_blobs'
             and manifest.get('compression') == 'ZIP_STORED', 'INVALID_MANIFEST', MANIFEST_PATH)
    _require(manifest.get('source_commit') == commit, 'CODE_COMMIT_MISMATCH', MANIFEST_PATH)
    _require(_hex(manifest.get('source_tree'), (len(commit),)), 'INVALID_MANIFEST', 'source_tree')
    rows = manifest.get('files')
    _require(isinstance(rows, list) and bool(rows), 'INVALID_MANIFEST', 'files')
    listed = set()
    for row in rows:
        _require(isinstance(row, dict) and _text(row.get('path')), 'INVALID_MANIFEST', 'files')
        name = row['path']
        _deny_source_path(name)
        _require(name not in listed, 'DUPLICATE_MANIFEST_ENTRY', 'files')
        listed.add(name)
        _require(name in contents, 'MISSING_SOURCE', name)
        value = contents[name]
        _require(type(row.get('size')) is int and row['size'] == len(value)
                 and row.get('sha256') == digest(value), 'SOURCE_HASH_MISMATCH', name)
        _require(row.get('git_mode') in ('100644', '100755')
                 and modes[name] == int(row['git_mode'], 8), 'SOURCE_MODE_MISMATCH', name)
        blob = b'blob ' + str(len(value)).encode('ascii') + b'\0' + value
        oid = hashlib.sha1(blob).hexdigest() if len(commit) == 40 else digest(blob)
        _require(row.get('git_blob') == oid, 'SOURCE_BLOB_MISMATCH', name)
    _require(set(contents) == listed | {MANIFEST_PATH, GUIDE_PATH}, 'UNLISTED_SOURCE', 'archive')
    for skill in SKILLS:
        path = f'skills/{skill}/SKILL.md'
        _require(path in listed and bool(contents[path].strip()), 'MISSING_SKILL', path)
    for path in REQUIRED_FILES:
        _require(path in listed, 'MISSING_SOURCE', path)
    schema = _json(contents['packages/contracts/schemas/lgax.schema.json'])
    _require(schema == load_schema(), 'CONTRACT_MISMATCH', 'schema')
    return manifest


def _bound_file(contents, item, location):
    _require(isinstance(item, dict) and _text(item.get('path')), 'INVALID_RECORD', location)
    path = item['path']
    _deny_source_path(path)
    _require(path in contents, 'MISSING_SOURCE', location)
    _require(item.get('sha256') == digest(contents[path]), 'ORIGINAL_HASH_MISMATCH', location)
    return contents[path]


def verify_replay(archive_bytes: bytes, replay: dict, *, expected_commit: str,
                  expected_manifest_sha256: str) -> dict:
    """Return consistent/held/rejected and diagnostics; no command is executed.

    Pins must originate outside the supplied ZIP. Missing model metadata and
    non-completed Run states are held. Invalid bytes/identities are rejected.
    Neither consistent nor ok grants parent completion or upload permission.
    """
    result = {'ok': False, 'status': 'rejected', 'issues': [], 'commands': [],
              'commands_trusted': False, 'replay_executed': False,
              'submission_ready': False, 'parent_complete': False}
    try:
        _require(_hex(expected_commit, (40, 64)) and _hex(expected_manifest_sha256),
                 'INVALID_PIN', 'expected')
        _require(isinstance(replay, dict), 'INVALID_RECORD', 'replay')
        # Strict JSON copy rejects NaN/non-JSON values, and prevents caller mutation.
        record_bytes = json.dumps(replay, allow_nan=False).encode('utf-8')
        _require(len(record_bytes) <= MAX_FILE_BYTES, 'RECORD_LIMIT', 'replay')
        _check_content('replay.json', record_bytes)
        replay = _json(record_bytes)
        contents, modes = _archive(archive_bytes)
        _source(contents, modes, expected_commit, expected_manifest_sha256)
        for field in ('code_commit', 'filming_commit'):
            _require(replay.get(field) == expected_commit, 'FILMING_COMMIT_MISMATCH', field)
        run = replay.get('run')
        validate('Run', run)
        _require(replay.get('demo_run_id') == run['id'], 'DEMO_RUN_MISMATCH', 'demo_run_id')
        dataset_ref = replay.get('dataset')
        dataset = _json(_bound_file(contents, dataset_ref, 'dataset'))
        validate('DemoDataset', dataset)
        for field in ('dataset_id', 'version', 'source_kind'):
            _require(dataset_ref.get(field) == dataset['manifest'][field], 'DATASET_MISMATCH', field)
        _require(run['dataset_version'] == dataset_ref['version'], 'DATASET_MISMATCH', 'run.dataset_version')
        products = {p['model_id']: p for p in dataset['products']}
        evidence = {e['id']: e for e in dataset['evidence']}
        _require(len(products) == len(dataset['products']) and len(evidence) == len(dataset['evidence']),
                 'DUPLICATE_DATA_ID', 'dataset')
        used = set(run['evidence_ids'])
        for event in run['events']:
            used.update(event['evidence_ids'])
        for concept in run['concepts']:
            used.update(concept['evidence_ids'])
        _require(used <= evidence.keys(), 'UNKNOWN_EVIDENCE', 'run')
        documents = replay.get('documents')
        _require(isinstance(documents, list), 'INVALID_RECORD', 'documents')
        sources = {}
        fields = ('source_id', 'model_id', 'document_version', 'source_kind')
        for document in documents:
            _bound_file(contents, document, 'documents')
            _require(all(_text(document.get(k)) for k in fields), 'INVALID_RECORD', 'documents')
            key = tuple(document[k] for k in fields)
            _require(key not in sources, 'DUPLICATE_DOCUMENT', 'documents')
            sources[key] = document
        expected_sources = set()
        for item in dataset['evidence']:
            product = products.get(item['model_id'])
            _require(product is not None and all(product[k] == item[k]
                     for k in ('document_version', 'source_kind')), 'PRODUCT_VERSION_MISMATCH', 'evidence')
            expected_sources.add(tuple(item[k] for k in fields))
        _require(set(sources) == expected_sources, 'DOCUMENT_PROVENANCE_MISMATCH', 'documents')
        commands = replay.get('commands')
        _require(isinstance(commands, list) and bool(commands) and all(
            isinstance(argv, list) and bool(argv) and all(_text(arg) and '\0' not in arg for arg in argv)
            for argv in commands), 'INVALID_COMMAND_DATA', 'commands')
        models = replay.get('models')
        held = []
        if replay.get('model_manifest') is None:
            held.append({'code': 'INCOMPLETE_MODEL_INFO', 'location': 'model_manifest'})
        else:
            recorded_models = _json(_bound_file(contents, replay['model_manifest'], 'model_manifest'))
            _require(models == recorded_models, 'MODEL_VERSION_MISMATCH', 'models')
        if not isinstance(models, list) or not models:
            held.append({'code': 'INCOMPLETE_MODEL_INFO', 'location': 'models'})
        else:
            ids = set()
            for model in models:
                if not _model_complete(model):
                    held.append({'code': 'INCOMPLETE_MODEL_INFO', 'location': 'models'})
                else:
                    _require(model['id'] not in ids, 'DUPLICATE_MODEL', 'models')
                    ids.add(model['id'])
        if run['status'] != 'completed':
            held.append({'code': 'RUN_NOT_COMPLETED', 'location': 'run.status'})
        result.update(ok=not held, status='held' if held else 'consistent', issues=held,
                      source_commit=expected_commit, archive_sha256=digest(archive_bytes),
                      manifest_sha256=expected_manifest_sha256, demo_run_id=run['id'],
                      run_status=run['status'], run=deepcopy(run), dataset=deepcopy(dataset_ref),
                      products=deepcopy(dataset['products']), documents=deepcopy(documents),
                      models=deepcopy(models), commands=deepcopy(commands))
    except ReplayError as error:
        result['issues'] = [{'code': error.code, 'location': error.location}]
    except PackageError:
        # Do not echo credential-bearing archive paths or content in errors.
        result['issues'] = [{'code': 'UNSAFE_ARCHIVE_CONTENT_OR_PATH', 'location': 'archive'}]
    except ValidationError:
        result['issues'] = [{'code': 'CONTRACT_MISMATCH', 'location': 'run_or_dataset'}]
    except (ValueError, TypeError, KeyError, UnicodeError, zipfile.BadZipFile,
            RuntimeError, NotImplementedError, RecursionError):
        result['issues'] = [{'code': 'MALFORMED_INPUT', 'location': 'input'}]
    return result
