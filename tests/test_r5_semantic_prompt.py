"""Actual local prompt-preparation regression; no generation or semantic grade."""
import hashlib
import json
import unittest
from copy import deepcopy
from pathlib import Path

from lgax_core.errors import DomainError
from lgax_core.model_client import ModelConfig, OllamaAdapter, StructuredModelClient
from lgax_core.prompt_context import model_context
from lgax_core.semantic_review import INSTRUCTIONS, schema_for_review, semantic_grounding_requirements, semantic_model_context
from lgax_core.source_boundary import SourceBoundary
import test_planning_agent as fixtures

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / 'evals/pm-prototype/20261007/r5-core/semantic-prompt-counterexample.json'
PIN = '85d30432f624e988b9ab0dd2b834723ac92887bb0f7845fd92377a6b12850a69'
MODEL = 'qwen3.5:122b-a10b-q4_K_M'
DIGEST = '8b9d11d807c57feb1e2ecb0d6cbf40334c37dcc3523bed5540af4f927f112a37'


class PreparedWithoutGeneration(Exception):
    pass


class PreparationCapture(OllamaAdapter):
    def generate(self, prompt, schema):
        self.prepared = (prompt, deepcopy(schema))
        raise PreparedWithoutGeneration


class RecordedSemanticPromptTests(unittest.TestCase):
    def setUp(self):
        self.raw = ARTIFACT.read_bytes()
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), PIN)
        self.case = json.loads(self.raw)

    def tearDown(self):
        self.assertEqual(ARTIFACT.read_bytes(), self.raw)

    def client(self):
        adapter = PreparationCapture(ModelConfig(
            'http://127.0.0.1:11434', MODEL, DIGEST, max_output_tokens=8192,
            context_tokens=16384, api_mode='generate'))
        self.addCleanup(adapter.close)
        return StructuredModelClient(adapter), adapter

    def test_actual_nine_need_nine_gap_three_candidate_request_passes_same_preparation_guard(self):
        context = self.case['request_context']
        self.assertEqual([len(context[key]) for key in ('needs', 'gaps', 'concepts')], [9, 9, 3])
        original = deepcopy(context)
        client, adapter = self.client()
        with self.assertRaises(DomainError) as caught:
            client.generate(self.case['previous_prompt'], self.case['schema'], MODEL)
        self.assertEqual(caught.exception.details, {'reason': 'prompt_too_large', 'maximum': 24000})
        self.assertFalse(hasattr(adapter, 'prepared'))
        projected = semantic_model_context(context)
        payload = self.case['payload']
        policy = SourceBoundary(payload, allowed_tools=('get_evidence', 'list_products')).messages()[0]['content']
        prompt = policy + '\n' + INSTRUCTIONS + json.dumps(projected, ensure_ascii=False, separators=(',', ':'))
        schema = schema_for_review(payload, self.case['current_output'], literal_choices=True)
        self.assertEqual(schema, self.case['schema'])
        with self.assertRaises(PreparedWithoutGeneration):
            client.generate(prompt, schema, MODEL)
        formatted, submitted_schema = adapter.prepared
        self.assertLessEqual(len(formatted), 24000)
        self.assertLessEqual(len(formatted.encode('utf-8')), 45000)
        self.assertEqual(submitted_schema, self.case['schema'])
        self.assertEqual(context, original)
        self.assertEqual(adapter.config.ollama_options()['seed'], 42)
        print(json.dumps({'semantic_prompt_preparation_only': True,
                          'actual_case_needs_gaps_concepts': [9, 9, 3],
                          'previous_unformatted_characters': len(self.case['previous_prompt']),
                          'new_formatted_characters': len(formatted),
                          'new_formatted_utf8_bytes': len(formatted.encode('utf-8')),
                          'character_limit': 24000, 'utf8_limit': 45000,
                          'schema_unchanged': True, 'model_generations': 0}, ensure_ascii=False))

    def test_every_original_link_field_and_review_fact_restores_exactly(self):
        context = self.case['request_context']
        expected = model_context(context)
        projected = semantic_model_context(context)
        for original, encoded in zip(expected['quality_context']['concept_lineage']['candidates'],
                                     projected['quality_context']['concept_lineage']['candidates'], strict=True):
            table = encoded['links']
            self.assertEqual(table['columns'][0], 'gap_id')
            self.assertEqual(len(table['columns']), 19)
            restored = [dict(zip(table['columns'], row, strict=True)) for row in table['values']]
            self.assertEqual(restored, original['links'])
            self.assertEqual({k: v for k, v in encoded.items() if k != 'links'},
                             {k: v for k, v in original.items() if k != 'links'})
        self.assertIn('gap_id identifies each row', projected['quality_context']['reference'])
        self.assertIn('zip(columns, values_row)', projected['quality_context']['reference'])
        for key in context:
            if key != 'quality_context':
                self.assertEqual(projected[key], expected[key])
        self.assertEqual(projected['sources'], self.case['payload']['sources'])
        self.assertEqual(projected['semantic_grounding_requirements'], semantic_grounding_requirements(
            self.case['payload'], self.case['current_output']))

    def test_pipeline_records_exact_submitted_projection_and_keeps_full_request_context(self):
        case = fixtures.PlanningAgentTests('test_three_stages_original_data_and_sources_are_preserved')
        case.setUp()
        self.addCleanup(case.doCleanups)
        agent, _transport = case.agent()
        result = agent.run(case.payload)
        call = next(row for row in result['model_calls'] if row['skill_id'] == 'semantic_review')
        submitted = json.loads(call['formatted_prompt'].split('DATA_JSON:\n', 1)[1])
        self.assertEqual(call['prompt_context'], submitted)
        self.assertEqual(call['prompt_context'], semantic_model_context(call['request_context']))
        self.assertIsInstance(call['request_context']['quality_context']['concept_lineage']['candidates'][0]['links'], list)
        self.assertIsInstance(call['prompt_context']['quality_context']['concept_lineage']['candidates'][0]['links'], dict)
        trace = next(row for row in result['trace'] if row['operation'] == 'semantic_review')
        self.assertEqual(trace['inputs'], call['request_context'])


if __name__ == '__main__':
    unittest.main()
