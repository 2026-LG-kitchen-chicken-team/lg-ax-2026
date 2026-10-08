"""Read a pinned input-only archive; emit metadata, never source text or answers.

Run in the documented zero-auth, network-none container. No product/model imports.
"""
import argparse
import hashlib
import json
import stat
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


ZIP_SHA = 'e73d3393ad43e0bb9cf5f19944cc6c23c3fa69c72a1a140d6d680037e89ffaa8'
METADATA_SHA = '7729630ce842c97cb17f6b67a68baf59c63c36bfee79822871e721413742647d'
MANIFEST_SHA = '99a3982820a3f13de66c854d9e03c77e59c9ecbf6f396930288a2e1d89c91bf7'
PUBLISHED_HEAD = 'd5d33c46a5f27d7ccd805713c784ec4c9f0ace55'
EXPECTED_ENTRIES = {
    'cases.json', 'supplement-index.json',
    'schemas/input.json', 'schemas/output.json',
    'materials/normal.json', 'materials/duplicate_feature.json',
    'materials/model_version_confusion.json', 'materials/conflicting_reviews.json',
    'materials/missing_evidence.json', 'materials/specification_change.json',
    'supplements/specification_change-before.json',
}
FORBIDDEN_KEYS = {
    'gold', 'gold_answer', 'gold_answers', 'expected_output', 'expected_outputs',
    'expected_constraints', 'answer', 'answers', 'answer_key', 'method_key',
    'method_keys', 'reviewer_only', 'rubric', 'scoring_key',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'), allow_nan=False).encode('utf-8'))


def prohibited_keys(value):
    found = set()
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = key.lower().replace('-', '_')
            if normalized in FORBIDDEN_KEYS:
                found.add(normalized)
            found.update(prohibited_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.update(prohibited_keys(child))
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    checks = []

    def check(name, condition):
        checks.append({'check': name, 'passed': bool(condition)})

    raw = args.archive.read_bytes()
    meta_raw = args.metadata.read_bytes()
    original_raw = args.original.read_bytes()
    check('frozen ZIP SHA256', sha(raw) == ZIP_SHA)
    check('original and outbox identical bytes', original_raw == raw)
    check('frozen handoff metadata SHA256', sha(meta_raw) == METADATA_SHA)
    if not all(c['passed'] for c in checks):
        raise SystemExit('Frozen input pin mismatch; no archive processing.')
    meta = json.loads(meta_raw)
    check('metadata published head is metadata provenance only',
          meta['published_metadata_head'] == PUBLISHED_HEAD
          and meta['producer_git_head_for_raw_input'] is None)
    check('metadata declares prepared, not sent or received',
          meta['transfer_status'] == 'prepared_not_sent'
          and not meta['recipient_receipt_received'])
    entries = []
    bindings = []
    with zipfile.ZipFile(args.archive) as archive:
        info = archive.infolist()
        names = [i.filename for i in info]
        check('exact 11 unique allowlisted entries',
              len(names) == 11 and set(names) == EXPECTED_ENTRIES)
        safe = all(not PurePosixPath(n).is_absolute()
                   and '..' not in PurePosixPath(n).parts and '\\' not in n for n in names)
        check('relative regular unencrypted entries', safe and all(
            not i.is_dir() and not i.flag_bits & 1
            and not stat.S_ISLNK(i.external_attr >> 16) for i in info))
        check('bounded input archive', sum(i.file_size for i in info) < 1048576)
        if not all(c['passed'] for c in checks):
            raise SystemExit('Archive shape mismatch; no entry processing.')
        objects = {}
        for item in info:
            content = archive.read(item)
            entries.append({'path': item.filename, 'bytes': len(content), 'sha256': sha(content)})
            objects[item.filename] = json.loads(content)
        by_name = {e['path']: e for e in entries}
        check('frozen cases manifest SHA256', by_name['cases.json']['sha256'] == MANIFEST_SHA)
        check('frozen input and output schema hashes', all(
            by_name[name]['sha256'] == expected for name, expected in meta['schema_sha256'].items()))
        # Schema describes output shape; it is not a generated answer or Gold.
        findings = {name: sorted(prohibited_keys(obj)) for name, obj in objects.items()
                    if not name.startswith('schemas/') and prohibited_keys(obj)}
        check('no prohibited answer keys in non-schema input objects', not findings)
        rows = meta['rows']
        check('six primary and one paired input, six groups',
              len(rows) == 7 and sum(r['role'] == 'primary' for r in rows) == 6
              and len({r['group_id'] for r in rows}) == 6)
        check('each material has one metadata binding',
              {r['input_path_in_archive'] for r in rows}
              == {n for n in names if n.startswith(('materials/', 'supplements/'))})
        for row in rows:
            name = row['input_path_in_archive']
            payload = objects[name]
            check(name + ': raw input hash', by_name[name]['sha256'] == row['input_sha256'])
            product = payload['product']
            check(name + ': product model/version/source kind', all(
                product[key] == row[key] for key in ('model_id', 'document_version', 'source_kind')))
            sources = {source['id']: source for source in payload['sources']}
            check(name + ': exact source membership',
                  len(sources) == len(payload['sources'])
                  and set(sources) == {s['id'] for s in row['sources']})
            for source_meta in row['sources']:
                source = sources[source_meta['id']]
                check(name + ': source metadata/text binding ' + source_meta['id'],
                      all(source[key] == source_meta[key] for key in
                          ('model_id', 'document_version', 'source_kind', 'locator'))
                      and sha(source['text'].encode('utf-8')) == source_meta['text_utf8_sha256'])
            bindings.append({
                'path': name, 'role': row['role'], 'case_id': row['case_id'],
                'group_id': row['group_id'], 'raw_file_sha256': by_name[name]['sha256'],
                'canonical_input_sha256': canonical(payload), 'source_count': len(sources),
                'model_id': row['model_id'], 'document_version': row['document_version'],
                'source_kind': row['source_kind'],
            })
    check('archive unchanged during audit', args.archive.read_bytes() == raw)
    check('metadata unchanged during audit', args.metadata.read_bytes() == meta_raw)
    report = {
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'sender bytes and metadata only; not a CORE receipt or model execution',
        'status': 'PASS' if all(c['passed'] for c in checks) else 'FAIL',
        'archive': {'filename': 'input-only.zip', 'sha256': sha(raw), 'bytes': len(raw),
                    'entry_count': len(entries), 'uncompressed_bytes': sum(e['bytes'] for e in entries)},
        'metadata': {'filename': 'handoff-metadata.json', 'sha256': sha(meta_raw), 'bytes': len(meta_raw)},
        'published_metadata_head': PUBLISHED_HEAD,
        'raw_input_producer_git_head': None,
        'producer_script_sha256_declared': meta['producer_script_sha256'],
        'producer_script_reexecuted': False,
        'entries': entries, 'input_bindings': bindings, 'checks': checks,
        'role_separation': {
            'only_input_archive_and_metadata_mounted': True,
            'reviewer_gold_demo_method_key_files_opened': False,
            'prohibited_non_schema_key_findings': findings,
            'limitation': 'File allowlist and metadata/key checks do not independently establish semantic Gold separation or evaluation independence.',
        },
        'raw_input_text_exported': False, 'new_product_model_calls': 0,
        'actual_CORE_receipt_verified': False, 'transfer_performed': False,
        'independent_evaluation_approved': False,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'checks': len(checks),
                      'failures': [c['check'] for c in checks if not c['passed']],
                      'archive_bytes': len(raw), 'entries': len(entries)}))
    if report['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
