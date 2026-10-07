"""Offline original-ID mapping audit. Run only inside the fixed zero-auth container."""
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

SOURCE = Path('/source')
MANIFEST_SHA256 = '0ff3ff3e36a68d22d1303870c74e19891191ae7f4851d1197d80365dd6cb717a'


def reject_source(reason):
    print(json.dumps({'error': 'SOURCE_BINDING_MISMATCH', 'reason': reason,
                      'project_imports_started': False}), file=sys.stderr)
    raise SystemExit(2)


def verify_source():
    """Bind the source ref to frozen Git-derived bytes before project imports."""
    manifest_bytes = Path(__file__).with_name('source-manifest.json').read_bytes()
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    if manifest_sha != MANIFEST_SHA256:
        reject_source('source manifest digest')
    manifest = json.loads(manifest_bytes)
    expected = manifest['files']
    actual_paths = set()
    for package in ['packages/core/src/lgax_core', 'packages/contracts/src/lgax_contracts']:
        actual_paths.update(p.relative_to(SOURCE).as_posix() for p in (SOURCE / package).rglob('*.py'))
    actual_paths.add('packages/contracts/schemas/lgax.schema.json')
    if actual_paths != set(expected):
        reject_source('project source inventory')
    digests = {}
    for relative, pin in expected.items():
        path = SOURCE / relative
        if not path.is_file() or path.is_symlink() or path.resolve() != path.absolute():
            reject_source('missing or redirected source: ' + relative)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != pin['sha256']:
            reject_source('source bytes: ' + relative)
        digests[relative] = digest
    actual_digest = hashlib.sha256(json.dumps(digests, sort_keys=True,
                                             separators=(',', ':')).encode()).hexdigest()
    if actual_digest != manifest['source_digest_sha256']:
        reject_source('aggregate source digest')
    return {'source_ref': manifest['source_ref'], 'source_manifest_sha256': manifest_sha,
            'source_digest_sha256': actual_digest, 'verified_source_files': len(digests),
            'ref_kind': 'Git-derived source content pin; not a runtime Git HEAD query',
            'verified_before_project_import': True}


source_binding = verify_source()
sys.path[:0] = [str(SOURCE / 'packages/core/src'), str(SOURCE / 'packages/contracts/src')]
from lgax_core.concept_lineage import build_quality_context
from lgax_core.no_candidate_review import review_need_presence

artifact = Path('/source/evals/pm-prototype/20261007/r5-core/counterexamples.json')
raw = artifact.read_bytes()
assert hashlib.sha256(raw).hexdigest() == 'a1c25f1c405c2da887d52dd4b56639b6d7eddb7c9deb33a92a6d9bb29129e9cf'
cases = json.loads(raw)
results = {}
for name, case in cases.items():
    payload = deepcopy(case['original_input'])
    output = deepcopy(case['rejected_output'])
    if name == 'missing-manual':
        output = deepcopy(case['calls'][0]['request_context']['judgement'])
    before = deepcopy((payload, output))
    sources = {s['id']: s for s in payload['sources']}
    needs = {n['id']: n for n in output['needs']}
    gaps = {g['id']: g for g in output['gaps']}
    assessments = {r['gap_id']: r for r in output['gap_assessments']}
    context = build_quality_context(payload, output)
    rows = []
    for row in context['residual_matrix']['rows']:
        gap = gaps[row['gap_id']]
        need = needs[gap['need_id']]
        review_ids = [eid for eid in need['evidence_ids'] if eid in gap['evidence_ids']
                      and sources[eid]['source_type'] == 'review']
        manual_ids = [eid for eid in gap['evidence_ids'] if sources[eid]['source_type'] == 'manual']
        assert row['review_evidence_ids'] == review_ids
        assert row['manual_evidence_ids'] == manual_ids
        assert row['questions'] == gap['questions'] and row['remaining_pain'] == gap['remaining_pain']
        assert row['resolution'] == assessments[gap['id']]['resolution']
        assert row['support_basis'] == assessments[gap['id']]['support_basis']
        assert row['support_status'] == gap['support_status']
        for eid in gap['evidence_ids']:
            assert all(sources[eid][key] == payload['product'][key] for key in ['model_id', 'document_version'])
        rows.append({key: deepcopy(row[key]) for key in [
            'gap_id', 'need_id', 'review_evidence_ids', 'manual_evidence_ids', 'features',
            'support_basis', 'support_status', 'resolution', 'remaining_pain',
            'questions', 'requires_confirmation', 'candidate_eligible', 'valid']})
    presence = review_need_presence(payload, output)
    if name == 'missing-manual':
        row = next(r for r in presence if r['review_evidence_id'] == 'REVIEW-EVIDENCE-007')
        assert row['need_ids'] == ['NEED-006']
        assert not payload['features'] and not any(s['source_type'] == 'manual' for s in payload['sources'])
        assert output['status'] == 'held' and not output['concepts']
    assert (payload, output) == before
    results[name] = {'original_output_sha256': case['original_output_sha256'], 'rows': rows,
                     'review_need_presence': presence,
                     'violations': {key: value['violations'] for key, value in context.items()},
                     'semantic_accuracy_verified': False}
assert artifact.read_bytes() == raw
print(json.dumps({'source_binding': source_binding,
                  'kind': 'preserved_original_id_support_residual_question_mapping',
                  'cases': results, 'mapped_gap_rows': sum(len(r['rows']) for r in results.values()),
                  'inputs_and_outputs_unchanged': True, 'new_model_calls': 0,
                  'new_quality_pass': False, 'six_cases_regraded': False}, ensure_ascii=False))
