"""Read-only R5 original-response audit. Stdlib only; never imports product code."""
import argparse
import hashlib
import json
from pathlib import Path

SOURCE = '814fe2fbcd3b752ff6400d8a08671dce7bdd2d80'
PINS = {
    'fridge-normal': ('5625c0ff13d7e4282cbe7e6eb3ea0aa43d848cec8bf3d47c45845cf32d670f3d', 1309041, 'failed', 6, 42626),
    'fridge-changed': ('95833e754b034d7f0ec6749c549fb3f2f80ca3fa240d5bc1c98d80b49c8046e5', 831174, 'failed', 5, 27769),
    'fridge-missing-manual': ('d4a7af4f3a881256e0af779174518c1e3e0176ed86a0b9e923bcf6f833ebb688', 607986, 'held', 4, 21192),
}

def pick(rows, field, value):
    matches = [row for row in rows if row[field] == value]
    assert len(matches) == 1, (field, value, len(matches))
    return matches[0]

def audit(directory):
    documents = {}
    checks = []
    for case, (sha, size, status, count, tokens) in PINS.items():
        raw = (directory / f'{case}.output.json').read_bytes()
        assert hashlib.sha256(raw).hexdigest() == sha and len(raw) == size
        d = json.loads(raw)
        assert d['execution_kind'] == 'live_model' and d['status'] == status
        assert len(d['model_calls']) == count
        actual_tokens = 0
        for i, call in enumerate(d['model_calls']):
            assert call['execution_kind'] == 'live_model'
            assert call['model_id'] == 'qwen3.5:122b-a10b-q4_K_M'
            assert call['model_digest'] == '8b9d11d807c57feb1e2ecb0d6cbf40334c37dcc3523bed5540af4f927f112a37'
            assert json.loads(call['raw_response']) == call['generated']['data'], (case, i)
            actual_tokens += call['metadata']['prompt_eval_count'] + call['metadata']['eval_count']
        assert actual_tokens == tokens, (case, actual_tokens, tokens)
        assert d['correction_budget']['max_revisions'] == 2 and d['correction_budget']['closed']
        documents[case] = d
        checks.append({'case': case, 'sha256': sha, 'bytes': size, 'status': status,
                       'original_calls': count, 'original_tokens': actual_tokens,
                       'raw_generated_equal_calls': count,
                       'original_input_revision': d['original_input']['revision_count'],
                       'final_input_revision': d['input']['revision_count'],
                       'correction_budget': d['correction_budget']})

    normal = documents['fridge-normal']
    semantic = normal['model_calls'][4]
    assert semantic['skill_id'] == 'semantic_review'
    judgement = semantic['request_context']
    need = pick(judgement['needs'], 'id', 'NEED-007')
    gap = pick(judgement['gaps'], 'id', 'GAP-007')
    concept = pick(judgement['concepts'], 'id', 'CONCEPT-001')
    assert 'REVIEW-EVIDENCE-008' in need['evidence_ids']
    assert gap['need_id'] == need['id'] and 'GAP-007' in concept['gap_ids']
    assert {'REVIEW-EVIDENCE-008', 'MANUAL-001'} <= set(gap['evidence_ids'])
    assert {'REVIEW-EVIDENCE-008', 'MANUAL-001'} <= set(concept['evidence_ids'])
    rows = [r for r in semantic['generated']['data']['quality_assessments'] if r['concept_id'] == 'CONCEPT-001']
    difference = pick(rows, 'criterion', 'difference_from_current_features')
    mechanism = pick(rows, 'criterion', 'mechanism')
    difference_ids = [q['evidence_id'] for q in difference['source_quotes']]
    assert 'REVIEW-EVIDENCE-008' not in difference_ids and 'MANUAL-001' in difference_ids
    assert 'REVIEW-EVIDENCE-008' in [q['evidence_id'] for q in mechanism['source_quotes']]
    error = pick(normal['trace'], 'operation', 'semantic_review_error')['outputs']['error']
    assert error['details']['reason'] == 'difference_requires_review_and_manual'
    assert error['details']['gap_id'] == 'GAP-007'
    revision = normal['model_calls'][5]
    assert revision['skill_id'] == 'review_revision' and revision['revision_count'] == 2
    answer = revision['generated']['data']
    assert answer['status'] == 'held' and answer['questions'] == [] and answer['hold_reasons'] == []
    decision = pick(normal['trace'], 'operation', 'review_revision')['outputs']['error']['details']['decision']
    assert any(v['code'] == 'HOLD_WITHOUT_QUESTIONS' for v in decision['violations'])
    normal_facts = {'provided_need': need, 'provided_gap': gap, 'provided_concept': concept,
                    'difference_review': difference, 'mechanism_review': mechanism,
                    'semantic_error': error, 'revision_previous_violations': revision['request_context']['previous']['violations'],
                    'revision_previous_declarations': revision['request_context']['previous_declarations'],
                    'revision_response_status': answer['status'], 'revision_response_questions': answer['questions'],
                    'revision_response_hold_reasons': answer['hold_reasons'], 'revision_guard_decision': decision,
                    'interpretation': 'Candidate already cites RE008. The difference criterion omits that quote; the mechanism criterion has it. Questionless held revision was rejected, not accepted.'}

    changed = documents['fridge-changed']
    attempts = []
    for index in [3, 4]:
        call = changed['model_calls'][index]
        assert call['skill_id'] == 'concept_draft'
        context = call['request_context']['skill_input']
        assert isinstance(context, dict)
        generated = call['generated']['data']['result']['concepts']
        selected = [pick(generated, 'id', cid) for cid in ['CONCEPT-002', 'CONCEPT-003']]
        for c in selected:
            assert 'MANUAL-001' not in c['evidence_ids']
            for gid in c['gap_ids']:
                assert 'MANUAL-001' in pick(context['gaps'], 'id', gid)['evidence_ids']
        attempts.append({'call_index': index, 'revision_count': call['revision_count'],
                         'concepts': selected, 'feedback': call['request_context']['feedback'],
                         'provided_gaps': [g for g in context['gaps'] if g['id'] in ['GAP-002','GAP-009','GAP-005']]})
    assert attempts[1]['feedback'] == [{'code': 'CONCEPT_GROUNDING_MISSING', 'stage': 'concepts'}]
    changed_facts = {'attempts': attempts, 'semantic_review_calls': len(changed['semantic_reviews']),
                     'interpretation': 'Both draft attempts omit MANUAL001 for CONCEPT002/003; retry feedback names only code/stage, not missing IDs. No semantic review was reached.'}

    missing = documents['fridge-missing-manual']
    review = missing['no_candidate_reviews'][0]
    call = missing['model_calls'][3]
    assert call['skill_id'] == 'no_candidate_review'
    actual = pick(call['request_context']['judgement']['needs'], 'id', 'NEED-006')
    assert 'REVIEW-EVIDENCE-007' in actual['evidence_ids']
    assert actual == pick(review['reviewed_output']['needs'], 'id', 'NEED-006')
    assert actual == pick(missing['output']['needs'], 'id', 'NEED-006')
    assert missing['input']['features'] == []
    assessment = pick(review['report']['assessments'], 'criterion', 'review_polarity')
    assert assessment['verdict'] == 'violation'
    assert 'REVIEW-EVIDENCE-007' in [q['evidence_id'] for q in assessment['source_quotes']]
    assert any('REVIEW-EVIDENCE-007' in q and '누락' in q for q in review['report']['questions'])
    missing_facts = {'provided_need': actual, 'false_missing_need_assessment': assessment,
                     'review_questions': review['report']['questions'], 'review_decision': review['decision'],
                     'final_questions': missing['output']['questions'], 'final_hold_reasons': missing['output']['hold_reasons'],
                     'feature_count': 0,
                     'interpretation': 'RE007 is already linked to NEED006 in exact model input, reviewed output and final output. Missing-feature hold is appropriate; missing-Need assertion and associated question are false.'}
    return {'audit_id': 'CORE-R5-RAW-AUDIT-01a10729-01', 'original_handoff_commit': SOURCE,
            'original_model_source': 'de09b64ca72d5ae918cc0a95f244b0e0562761b0',
            'data_kind': 'synthetic', 'artifact_checks': checks,
            'new_model_calls': 0, 'original_total_calls': 15, 'original_total_tokens': 91587,
            'facts': {'normal': normal_facts, 'changed': changed_facts, 'missing_manual': missing_facts},
            'new_pm_fix_head': None, 'new_head_verdict': 'pending exact head handoff',
            'quality_pass': False, 'original_six_regraded': False, 'pm_approval': False}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--originals', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit(args.originals)
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode()
    if args.output:
        args.output.write_bytes(raw)
    else:
        print(raw.decode(), end='')
