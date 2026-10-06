"""Synthetic offline ZIPs: no Git, subprocess, model, extraction or upload."""

from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import stat
import unittest
from unittest.mock import patch
import warnings
import zipfile

from evals.submission_replay import verify_replay
from scripts.package_submission import (
    GUIDE_PATH, MANIFEST_PATH, REQUIRED_FILES, Blob, digest, json_bytes,
    manifest_for, _zip_info,
)


class SubmissionReplayTests(unittest.TestCase):
    def setUp(self):
        self.commit = 'a' * 40
        root = Path(__file__).resolve().parents[1]
        self.files = {name: b'synthetic public fixture\n' for name in REQUIRED_FILES}
        for name in ('packages/contracts/schemas/lgax.schema.json', 'data/demo/dataset.json'):
            self.files[name] = (root / name).read_bytes()
        self.files['harness/phase2/requirements.json'] = json_bytes({'requirements': []})
        self.dataset = json.loads(self.files['data/demo/dataset.json'])
        self.models = [{'id': 'fixture-model', 'revision': 'fixture-revision-1', 'digest': None,
                        'runtime': 'fixture-runtime-1', 'settings': {'temperature': 0}}]
        self.files['models/replay.json'] = json_bytes(self.models)
        self.record = {
            'code_commit': self.commit, 'filming_commit': self.commit, 'demo_run_id': 'RUN-fixture',
            'run': {'id': 'RUN-fixture', 'project_id': 'PROJECT-fixture', 'dataset_version': '0.1.0',
                    'contract_version': '0.1.0', 'status': 'completed', 'stage': 'finished',
                    'revision_count': 0, 'max_revisions': 2, 'concepts': [], 'unresolved': [],
                    'evidence_ids': [self.dataset['evidence'][0]['id']], 'events': []},
            'dataset': {'path': 'data/demo/dataset.json',
                        'sha256': digest(self.files['data/demo/dataset.json']),
                        **{k: self.dataset['manifest'][k] for k in ('dataset_id', 'version', 'source_kind')}},
            'model_manifest': {'path': 'models/replay.json', 'sha256': digest(self.files['models/replay.json'])},
            'documents': [], 'models': deepcopy(self.models),
            'commands': [['uv', 'run', 'python', 'skills/evidence_lookup/scripts/run.py']],
        }
        # The synthetic fixture's original text is embedded in the dataset itself.
        seen = set()
        for item in self.dataset['evidence']:
            fields = {k: item[k] for k in ('source_id', 'model_id', 'document_version', 'source_kind')}
            key = tuple(fields.values())
            if key not in seen:
                self.record['documents'].append({**fields, 'path': 'data/demo/dataset.json',
                                                 'sha256': self.record['dataset']['sha256']})
                seen.add(key)

    def archive(self, *, files=None, mutate_manifest=None, extra=(), mode=None, override=None):
        files = self.files if files is None else files
        blobs = []
        for name, value in sorted(files.items()):
            oid = hashlib.sha1(b'blob ' + str(len(value)).encode() + b'\0' + value).hexdigest()
            blobs.append(Blob(name, '100644', oid, value))
        manifest = manifest_for(self.commit, 'b' * 40, blobs)
        if mutate_manifest:
            mutate_manifest(manifest)
        encoded = json_bytes(manifest)
        stream = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive:
                entries = list(files.items()) + [(MANIFEST_PATH, encoded), (GUIDE_PATH, b'draft')] + list(extra)
                for name, value in entries:
                    info = _zip_info(name)
                    if mode and name == mode[0]:
                        info.external_attr = mode[1] << 16
                    archive.writestr(info, (override or {}).get(name, value))
        return stream.getvalue(), digest(encoded)

    def verify(self, record=None, **archive_args):
        data, pin = self.archive(**archive_args)
        return verify_replay(data, self.record if record is None else record,
                             expected_commit=self.commit, expected_manifest_sha256=pin)

    def assert_issue(self, result, code, status='rejected'):
        self.assertFalse(result['ok'])
        self.assertEqual(result['status'], status)
        self.assertIn(code, [issue['code'] for issue in result['issues']])
        self.assertFalse(result['replay_executed'])
        self.assertFalse(result['submission_ready'])
        self.assertFalse(result['parent_complete'])

    def test_consistent_inputs_preserve_provenance_without_execution(self):
        before = deepcopy(self.record)
        with patch('subprocess.run', side_effect=AssertionError('must not execute')), \
                patch.object(zipfile.ZipFile, 'extractall', side_effect=AssertionError('must not extract')):
            result = self.verify()
        self.assertTrue(result['ok'])
        self.assertEqual(result['status'], 'consistent')
        self.assertEqual(result['dataset']['source_kind'], 'synthetic')
        self.assertEqual(result['documents'], before['documents'])
        self.assertEqual(result['models'], before['models'])
        self.assertEqual(result['commands'], before['commands'])
        self.assertFalse(result['commands_trusted'])
        self.assertFalse(result['submission_ready'])
        result['run']['evidence_ids'].clear()
        self.assertEqual(self.record, before)

    def test_missing_each_skill_is_explicit(self):
        for name in [name for name in self.files if name.endswith('/SKILL.md')]:
            with self.subTest(name=name):
                files = {key: value for key, value in self.files.items() if key != name}
                self.assert_issue(self.verify(files=files), 'MISSING_SKILL')

    def test_archived_document_version_is_preserved_but_not_current_run_evidence(self):
        products = {item['model_id']: item for item in self.dataset['products']}
        archived = next(item for item in self.dataset['evidence']
                        if item['document_version'] != products[item['model_id']]['document_version'])
        self.assertTrue(self.verify()['ok'])
        changed = deepcopy(self.record)
        changed['run']['evidence_ids'] = [archived['id']]
        self.assert_issue(self.verify(changed), 'PRODUCT_VERSION_MISMATCH')

    def test_missing_original_and_wrong_hash(self):
        for field, value, code in [('path', 'missing.txt', 'MISSING_SOURCE'),
                                   ('sha256', '0' * 64, 'ORIGINAL_HASH_MISMATCH')]:
            record = deepcopy(self.record)
            record['documents'][0][field] = value
            self.assert_issue(self.verify(record), code)

    def test_changed_commits_and_run_id(self):
        for field in ('code_commit', 'filming_commit', 'demo_run_id'):
            record = deepcopy(self.record)
            record[field] = 'c' * 40
            self.assert_issue(self.verify(record), 'DEMO_RUN_MISMATCH' if field == 'demo_run_id'
                              else 'FILMING_COMMIT_MISMATCH')

    def test_unpinned_manifest_and_commit_fail(self):
        data, pin = self.archive()
        self.assert_issue(verify_replay(data, self.record, expected_commit=self.commit,
                                       expected_manifest_sha256='0' * 64), 'MANIFEST_HASH_MISMATCH')
        self.assert_issue(verify_replay(data, self.record, expected_commit='c' * 40,
                                       expected_manifest_sha256=pin), 'CODE_COMMIT_MISMATCH')

    def test_manifest_source_hash_blob_mode_and_duplicate_fail(self):
        self.assert_issue(self.verify(override={'README.md': b'changed original'}), 'SOURCE_HASH_MISMATCH')
        for field, value, code in [('sha256', '0' * 64, 'SOURCE_HASH_MISMATCH'),
                                   ('git_blob', '0' * 40, 'SOURCE_BLOB_MISMATCH'),
                                   ('git_mode', '100755', 'SOURCE_MODE_MISMATCH')]:
            with self.subTest(field=field):
                self.assert_issue(self.verify(mutate_manifest=lambda m: m['files'][0].update({field: value})), code)
        self.assert_issue(self.verify(mutate_manifest=lambda m: m['files'].append(m['files'][0])),
                          'DUPLICATE_MANIFEST_ENTRY')

    def test_zip_slip_secret_paths_duplicate_and_portable_collision_fail(self):
        for name in ('../escape', '/escape', 'x/../escape', 'x\\escape', 'C:/escape',
                     'private/test.txt', '.env', 'credentials.json', 'x/.ssh/id_rsa'):
            with self.subTest(name=name):
                self.assert_issue(self.verify(extra=[(name, b'fixture')]), 'UNSAFE_ARCHIVE_CONTENT_OR_PATH')
        for name in ('README.md', 'readme.MD'):
            self.assert_issue(self.verify(extra=[(name, b'fixture')]), 'DUPLICATE_ENTRY')
        self.assert_issue(self.verify(extra=[('README.md/child', b'fixture')]), 'PATH_COLLISION')
        self.assert_issue(self.verify(extra=[('unlisted.txt', b'fixture')]), 'UNLISTED_SOURCE')

    def test_symlink_and_secret_content_fail(self):
        self.assert_issue(self.verify(mode=('README.md', stat.S_IFLNK | 0o777)), 'UNSAFE_ENTRY')
        files = dict(self.files)
        files['notes.txt'] = ('gh' + 'p_' + 'x' * 30).encode()
        self.assert_issue(self.verify(files=files), 'UNSAFE_ARCHIVE_CONTENT_OR_PATH')

    def test_incomplete_models_hold_and_changed_versions_reject(self):
        for field in ('id', 'runtime', 'settings', 'revision'):
            with self.subTest(field=field):
                record = deepcopy(self.record)
                record['models'][0][field] = None
                files = dict(self.files)
                files['models/replay.json'] = json_bytes(record['models'])
                record['model_manifest']['sha256'] = digest(files['models/replay.json'])
                self.assert_issue(self.verify(record, files=files), 'INCOMPLETE_MODEL_INFO', 'held')
        record = deepcopy(self.record)
        record['models'][0]['revision'] = 'different-revision'
        self.assert_issue(self.verify(record), 'MODEL_VERSION_MISMATCH')

    def test_missing_model_manifest_and_unpinned_metadata_hold(self):
        record = deepcopy(self.record)
        del record['model_manifest']
        self.assert_issue(self.verify(record), 'INCOMPLETE_MODEL_INFO', 'held')
        for field, value in [('revision', 'latest'), ('digest', 'not-a-digest'),
                             ('settings', {'temperature': None})]:
            record = deepcopy(self.record)
            record['models'][0][field] = value
            files = dict(self.files)
            files['models/replay.json'] = json_bytes(record['models'])
            record['model_manifest']['sha256'] = digest(files['models/replay.json'])
            self.assert_issue(self.verify(record, files=files), 'INCOMPLETE_MODEL_INFO', 'held')

    def test_digest_only_model_is_preserved(self):
        record = deepcopy(self.record)
        record['models'][0].update(revision=None, digest='sha256:' + 'd' * 64)
        files = dict(self.files)
        files['models/replay.json'] = json_bytes(record['models'])
        record['model_manifest']['sha256'] = digest(files['models/replay.json'])
        self.assertTrue(self.verify(record, files=files)['ok'])

    def test_run_failure_held_and_unimplemented_are_not_success(self):
        for state in ('held', 'failed', 'not_implemented', 'pending', 'running'):
            record = deepcopy(self.record)
            record['run']['status'] = state
            record['run']['unresolved'] = ['fixture incomplete']
            result = self.verify(record)
            self.assert_issue(result, 'RUN_NOT_COMPLETED', 'held')
            self.assertEqual(result['run_status'], state)
            self.assertEqual(result['run']['unresolved'], ['fixture incomplete'])

    def test_contract_limits_and_unknown_evidence_fail(self):
        record = deepcopy(self.record)
        record['run']['revision_count'] = 3
        self.assert_issue(self.verify(record), 'CONTRACT_MISMATCH')
        record = deepcopy(self.record)
        record['run']['events'] = [{'stage': 'review', 'summary': 'fixture', 'tool': None,
                                    'evidence_ids': ['unknown']}]
        self.assert_issue(self.verify(record), 'UNKNOWN_EVIDENCE')

    def test_changed_dataset_version_and_document_kind_fail(self):
        for target, field, value, code in [('dataset', 'version', '2.0', 'DATASET_MISMATCH'),
                                         ('run', 'dataset_version', '2.0', 'DATASET_MISMATCH')]:
            record = deepcopy(self.record)
            record[target][field] = value
            self.assert_issue(self.verify(record), code)
        record = deepcopy(self.record)
        record['documents'][0]['source_kind'] = 'public'
        self.assert_issue(self.verify(record), 'DOCUMENT_PROVENANCE_MISMATCH')

    def test_changed_product_document_version_and_duplicate_document_fail(self):
        dataset = deepcopy(self.dataset)
        dataset['evidence'][0]['document_version'] = 'different-version'
        files = dict(self.files)
        files['data/demo/dataset.json'] = json_bytes(dataset)
        record = deepcopy(self.record)
        record['dataset']['sha256'] = digest(files['data/demo/dataset.json'])
        for document in record['documents']:
            document['sha256'] = record['dataset']['sha256']
        self.assert_issue(self.verify(record, files=files), 'PRODUCT_VERSION_MISMATCH')
        record = deepcopy(self.record)
        record['documents'].append(deepcopy(record['documents'][0]))
        self.assert_issue(self.verify(record), 'DUPLICATE_DOCUMENT')

    def test_duplicate_json_keys_and_nonfinite_metadata_fail(self):
        files = dict(self.files)
        files['models/replay.json'] = b'{"id":"one","id":"two"}'
        record = deepcopy(self.record)
        record['model_manifest']['sha256'] = digest(files['models/replay.json'])
        self.assert_issue(self.verify(record, files=files), 'DUPLICATE_JSON_KEY')
        record = deepcopy(self.record)
        record['models'][0]['settings']['temperature'] = float('nan')
        self.assert_issue(self.verify(record), 'MALFORMED_INPUT')

    def test_record_secret_is_not_echoed(self):
        record = deepcopy(self.record)
        record['commands'] = [['fixture', 'gh' + 'p_' + 'x' * 30]]
        result = self.verify(record)
        self.assert_issue(result, 'UNSAFE_ARCHIVE_CONTENT_OR_PATH')
        self.assertEqual(result['commands'], [])

    def test_schema_tampering_is_not_loaded_as_authority(self):
        files = dict(self.files)
        files['packages/contracts/schemas/lgax.schema.json'] = b'{}'
        self.assert_issue(self.verify(files=files), 'CONTRACT_MISMATCH')

    def test_commands_are_only_data_and_malformed_commands_fail(self):
        record = deepcopy(self.record)
        record['commands'] = [['arbitrary-program', '$(untrusted)', '; another-command']]
        with patch('subprocess.run', side_effect=AssertionError('must not execute')):
            result = self.verify(record)
        self.assertEqual(result['commands'], record['commands'])
        self.assertFalse(result['commands_trusted'])
        record['commands'] = 'execute this'
        self.assert_issue(self.verify(record), 'INVALID_COMMAND_DATA')

    def test_malformed_inputs_and_limits_fail_closed(self):
        data, pin = self.archive()
        for value in (None, [], {'run': None}):
            result = verify_replay(data, value, expected_commit=self.commit, expected_manifest_sha256=pin)
            self.assertFalse(result['ok'])
        self.assert_issue(verify_replay(b'not zip', self.record, expected_commit=self.commit,
                                       expected_manifest_sha256=pin), 'MALFORMED_INPUT')
        with patch('evals.submission_replay.MAX_FILES', 1):
            self.assert_issue(self.verify(), 'ARCHIVE_LIMIT')
        with patch('evals.submission_replay.MAX_FILE_BYTES', 1):
            self.assert_issue(self.verify(), 'RECORD_LIMIT')
            # The record limit is checked before ZIP members. Exercise the
            # archive bound directly without weakening production ordering.
            from evals.submission_replay import _archive, ReplayError
            with self.assertRaises(ReplayError) as raised:
                _archive(data)
            self.assertEqual(raised.exception.code, 'ARCHIVE_LIMIT')


if __name__ == '__main__':
    unittest.main()
