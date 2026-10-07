"""Replay selected real counterexamples; authored repairs are fixtures, not LLM passes."""
import hashlib
import json
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator

import test_planning_agent as fixtures
from lgax_core.concept_lineage import concept_grounding_requirements, trace_concept_lineage
from lgax_core.errors import DomainError
from lgax_core.judgement_contract import input_digest, review_judgement
from lgax_core.no_candidate_review import no_candidate_review_schema, review_need_presence, review_no_candidate
from lgax_core.planning_agent import generation_schema
from lgax_core.revision_guard import revision_schema
from lgax_core.semantic_review import review_semantics, schema_for_review

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / 'evals/pm-prototype/20261007/r5-core/counterexamples.json'
PIN = 'a1c25f1c405c2da887d52dd4b56639b6d7eddb7c9deb33a92a6d9bb29129e9cf'


class RecordedR5GroundingTests(unittest.TestCase):
    def setUp(self):
        self.raw = ARTIFACT.read_bytes()
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), PIN)
        self.cases = json.loads(self.raw)

    def tearDown(self):
        self.assertEqual(ARTIFACT.read_bytes(), self.raw)

    def test_both_original_changed_drafts_identify_exact_manual_omission(self):
        case = self.cases['changed']
        for call in case['calls']:
            with self.subTest(revision=call['request_context']['revision_count']):
                payload = deepcopy(case['original_input'])
                output = deepcopy(case['rejected_output'])
                output['concepts'] = deepcopy(call['data']['result']['concepts'])
                output['concept_assessments'] = deepcopy(call['data']['concept_assessments'])
                requirements = concept_grounding_requirements(payload, output)
                schema = generation_schema('concept_draft', grounding_requirements=requirements)
                Draft202012Validator.check_schema(schema)
                self.assertTrue(list(Draft202012Validator(schema).iter_errors(call['data'])))
                rejected = [v for v in trace_concept_lineage(payload, output)['violations']
                            if v['code'] == 'CONCEPT_GROUNDING_MISSING']
                self.assertEqual({v['concept_id'] for v in rejected}, {'CONCEPT-002', 'CONCEPT-003'})
                self.assertTrue(all(link['missing_evidence_ids'] == ['MANUAL-001']
                                    for v in rejected for link in v['missing_links']))
                decision = review_judgement(payload, output)
                detailed = [v for v in decision['violations'] if v['code'] == 'CONCEPT_GROUNDING_MISSING']
                self.assertEqual(detailed, rejected)
                self.assertNotEqual(decision['action'], 'accept')

    def test_candidate_schema_requires_only_its_selected_gap_evidence(self):
        payload = fixtures.read('normal.input.json')
        output = fixtures.read('normal.fixture-output.json')
        other = deepcopy(output['gaps'][0])
        other.update(id='GAP-UNSELECTED', evidence_ids=['UNSELECTED-REVIEW', 'UNSELECTED-MANUAL'])
        # An explicit requirements table probes conditional scope without changing
        # source data or pretending the unselected Gap is canonically valid.
        requirements = concept_grounding_requirements(payload, output)
        requirements.append({'gap_id': other['id'], 'required_evidence_ids': other['evidence_ids']})
        schema = generation_schema('concept_draft', grounding_requirements=requirements)
        value = fixtures.stages_for(output)['concept_draft']
        self.assertFalse(list(Draft202012Validator(schema).iter_errors(value)))
        value['result']['concepts'][0]['gap_ids'].append(other['id'])
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(value)))

    def test_original_normal_semantic_review_stays_rejected_with_precise_gap(self):
        case = self.cases['normal']
        call = next(c for c in case['calls'] if c['skill_id'] == 'semantic_review')
        payload = deepcopy(case['original_input'])
        payload['revision_count'] = call['request_context']['revision_count']
        output = case['rejected_output']
        self.assertEqual(input_digest(payload), call['data']['input_sha256'])
        self.assertEqual(input_digest(output), call['data']['output_sha256'])
        schema = schema_for_review(payload, output, literal_choices=True)
        Draft202012Validator.check_schema(schema)
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(call['data'])))
        with self.assertRaises(DomainError) as caught:
            review_semantics(payload, output, call['data'])
        self.assertEqual(caught.exception.details['reason'], 'difference_requires_review_and_manual')
        self.assertEqual(caught.exception.details['gap_id'], 'GAP-007')
        self.assertEqual(caught.exception.details['required_review_evidence_ids'], ['REVIEW-EVIDENCE-008'])

    def test_difference_violation_is_not_forced_to_satisfied_by_quote_schema(self):
        payload = fixtures.read('normal.input.json')
        output = fixtures.read('normal.fixture-output.json')
        context = {**payload, **output, 'input_sha256': input_digest(payload), 'output_sha256': input_digest(output)}
        report = fixtures.semantic_for(context)
        row = next(r for r in report['quality_assessments'] if r['criterion'] == 'difference_from_current_features')
        row.update(verdict='violation', source_quotes=[], reason='Fixture: difference is not established')
        schema = schema_for_review(payload, output, literal_choices=True)
        self.assertFalse(list(Draft202012Validator(schema).iter_errors(report)))
        self.assertEqual(review_semantics(payload, output, report)['action'], 'revise')

    def test_original_normal_hold_without_question_fails_generation_shape(self):
        call = next(c for c in self.cases['normal']['calls'] if c['skill_id'] == 'review_revision')
        value = call['data']
        self.assertEqual(value['status'], 'held')
        self.assertEqual(value['questions'], [])
        schema = revision_schema(2)
        Draft202012Validator.check_schema(schema)
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(value)))

    def test_held_question_shape_does_not_supply_or_accept_a_candidate(self):
        value = deepcopy(next(c for c in self.cases['normal']['calls'] if c['skill_id'] == 'review_revision')['data'])
        value['questions'] = ['Authored fixture question; actual semantic necessity is not verified']
        value['hold_reasons'] = ['Authored fixture missing source; actual semantic necessity is not verified']
        self.assertFalse(list(Draft202012Validator(revision_schema(2)).iter_errors(value)))
        self.assertEqual(value['status'], 'held')
        self.assertEqual(value['result']['concepts'], [])

    def missing_case(self):
        call = self.cases['missing-manual']['calls'][0]
        payload = deepcopy(self.cases['missing-manual']['original_input'])
        payload['revision_count'] = call['request_context']['judgement']['revision_count']
        return payload, call['request_context']['judgement'], call['data']

    def structured_copy(self, report):
        value = deepcopy(report)
        for row in value['assessments']:
            row['missing_need_review_ids'] = []
        value['question_basis'] = [{'question': question, 'kind': 'source_information', 'review_evidence_ids': []}
                                   for question in value['questions']]
        return value

    def test_original_legacy_reviewer_cannot_bypass_new_declared_claim_shape(self):
        payload, output, report = self.missing_case()
        self.assertEqual(input_digest(payload), report['input_sha256'])
        self.assertEqual(input_digest(output), report['output_sha256'])
        schema = no_candidate_review_schema(payload, output)
        Draft202012Validator.check_schema(schema)
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(report)))
        with self.assertRaises(DomainError):
            review_no_candidate(payload, output, report)

    def test_same_original_false_need_claim_is_rejected_against_need006(self):
        payload, output, report = self.missing_case()
        value = self.structured_copy(report)
        value['assessments'][0]['missing_need_review_ids'] = ['REVIEW-EVIDENCE-007']
        value['question_basis'][0].update(kind='missing_need', review_evidence_ids=['REVIEW-EVIDENCE-007'])
        self.assertEqual(value['questions'], report['questions'])
        presence = {r['review_evidence_id']: r['need_ids'] for r in review_need_presence(payload, output)}
        self.assertEqual(presence['REVIEW-EVIDENCE-007'], ['NEED-006'])
        with self.assertRaises(DomainError) as caught:
            review_no_candidate(payload, output, value)
        self.assertEqual(caught.exception.details['reason'], 'reviewer_reports_existing_need')
        self.assertEqual(caught.exception.details['contradictions'], [
            {'review_evidence_id': 'REVIEW-EVIDENCE-007', 'existing_need_ids': ['NEED-006']}])

    def test_authored_consistent_missing_manual_review_retains_real_hold(self):
        payload, output, original = self.missing_case()
        report = self.structured_copy(original)
        report['questions'] = [original['questions'][1]]
        report['question_basis'] = [report['question_basis'][1]]
        for row in report['assessments']:
            row.update(verdict='consistent', reason='Authored fixture: existing Need is present; manual information is absent')
        decision = review_no_candidate(payload, output, report)
        self.assertEqual(decision['action'], 'hold')
        self.assertEqual(decision['next_revision_count'], payload['revision_count'])
        self.assertEqual(output['concepts'], [])
        self.assertEqual(payload['features'], [])
        self.assertFalse(any(s['source_type'] == 'manual' for s in payload['sources']))

    def test_each_question_must_have_one_basis_and_output_omission_is_not_source(self):
        payload, output, original = self.missing_case()
        report = self.structured_copy(original)
        report['question_basis'] = report['question_basis'][1:]
        with self.assertRaises(DomainError) as caught:
            review_no_candidate(payload, output, report)
        self.assertEqual(caught.exception.details['reason'], 'question_basis_coverage')
        report = self.structured_copy(original)
        report['question_basis'][0].update(kind='missing_need', review_evidence_ids=[])
        with self.assertRaises(DomainError) as caught:
            review_no_candidate(payload, output, report)
        self.assertEqual(caught.exception.details['reason'], 'output_omission_is_not_missing_source')


class R5PipelineFeedbackTests(unittest.TestCase):
    def fixture(self, alter):
        case = fixtures.PlanningAgentTests('test_three_stages_original_data_and_sources_are_preserved')
        case.setUp()
        self.addCleanup(case.doCleanups)
        agent, transport = case.agent(alter)
        return case, agent, transport

    def test_native_concept_schema_rejection_preserves_raw_and_exact_retry_edges(self):
        rejected = []

        def alter(skill, context, value, _count):
            if skill == 'concept_draft' and context['revision_count'] == 0:
                value['result']['concepts'][0]['evidence_ids'] = [
                    eid for eid in value['result']['concepts'][0]['evidence_ids'] if eid != 'DEV-01-MANUAL']
                rejected.append(deepcopy(value))
            return value

        case, agent, transport = self.fixture(alter)
        result = agent.run(case.payload)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['input']['revision_count'], 1)
        call = next(c for c in result['model_calls'] if c['skill_id'] == 'concept_draft')
        self.assertEqual(json.loads(call['raw_response']), rejected[0])
        self.assertEqual(call['error']['details']['reason'], 'schema_mismatch')
        post = next(p for p in transport.posts if p['skill'] == 'concept_draft' and p['context']['revision_count'] == 1)
        missing = post['context']['feedback'][0]['details']['grounding_violations'][0]['missing_links'][0]
        self.assertEqual(missing['missing_evidence_ids'], ['DEV-01-MANUAL'])
        self.assertTrue(post['context']['candidate_grounding_requirements'])

    def test_native_semantic_schema_rejection_keeps_same_per_gap_retry_details(self):
        rejected = []

        def alter(skill, context, value, _count):
            if skill == 'semantic_review' and context['revision_count'] == 0:
                row = next(r for r in value['quality_assessments'] if r['criterion'] == 'difference_from_current_features')
                row['source_quotes'] = [q for q in row['source_quotes'] if q['evidence_id'] != 'DEV-01-REVIEW']
                rejected.append(deepcopy(value))
            return value

        case, agent, transport = self.fixture(alter)
        result = agent.run(case.payload)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['input']['revision_count'], 1)
        call = next(c for c in result['model_calls'] if c['skill_id'] == 'semantic_review')
        self.assertEqual(json.loads(call['raw_response']), rejected[0])
        self.assertEqual(call['error']['details']['reason'], 'schema_mismatch')
        post = next(p for p in transport.posts if p['skill'] == 'review_revision')
        details = json.loads(post['context']['previous']['violations'][0])['details']
        self.assertEqual(details['reason'], 'difference_requires_review_and_manual')
        self.assertEqual(details['required_review_evidence_ids'], ['DEV-01-REVIEW'])

    def test_false_need_claim_cannot_hold_or_bypass_shared_two_retry_limit(self):
        def alter(skill, context, value, _count):
            if skill == 'product_compare':
                value['result']['gaps'][0]['remaining_pain'] = ''
                value['gap_assessments'][0]['resolution'] = 'resolved'
            if skill == 'no_candidate_review':
                value['assessments'][0].update(verdict='violation', missing_need_review_ids=['DEV-01-REVIEW'])
            return value

        case, agent, transport = self.fixture(alter)
        result = agent.run(case.payload)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['input']['revision_count'], 2)
        self.assertEqual(result['decision']['action'], 'unresolved')
        self.assertEqual(sum(p['skill'] == 'no_candidate_review' for p in transport.posts), 3)
        self.assertTrue(result['correction_budget']['closed'])
        self.assertTrue(all(p['context']['review_need_presence'] for p in transport.posts if p['skill'] == 'no_candidate_review'))
        self.assertEqual(result['errors'][-1]['details']['reason'], 'reviewer_reports_existing_need')

