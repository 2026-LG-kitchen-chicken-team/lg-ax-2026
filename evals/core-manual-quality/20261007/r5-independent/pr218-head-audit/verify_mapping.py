"""Offline original-ID mapping audit. Run only inside the fixed zero-auth container."""
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

sys.path[:0] = ['/source/packages/core/src', '/source/packages/contracts/src']
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
print(json.dumps({'head': '0d920df7d1afd09490e91cd40bf9c6cb9dfaf75d',
                  'kind': 'preserved_original_id_support_residual_question_mapping',
                  'cases': results, 'mapped_gap_rows': sum(len(r['rows']) for r in results.values()),
                  'inputs_and_outputs_unchanged': True, 'new_model_calls': 0,
                  'new_quality_pass': False, 'six_cases_regraded': False}, ensure_ascii=False))
