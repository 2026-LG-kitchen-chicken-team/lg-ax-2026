"""Selection/version and public coverage boundaries, using frozen real source originals."""

import json
import tempfile
import unittest
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from fastapi.testclient import TestClient
from lgax_api.research_planning import ResearchWorkspace
from lgax_api.research_projection import project_source_statistics
from lgax_api.workspace_auth import TokenRegistry
from lgax_api.workspace_server import create_workspace_app
from lgax_core.public_planning import is_customer_source, summary_reference_coverage
from test_research_workspace import PACK, ContractOnlyPlanner


class SelectedSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.bundle = json.loads(PACK.read_text('utf-8'))
        self.planner = ContractOnlyPlanner()
        registry = TokenRegistry([{'principal_id': 'selection-wire-test', 'role': 'editor',
                                  'token_sha256': sha256(b'test-selection-boundary-credential-20261008').hexdigest()}])
        self.workspace = ResearchWorkspace(root / 'research.sqlite3', [PACK], self.planner)
        self.client = TestClient(create_workspace_app(root / 'workspace.sqlite3', registry,
                                                     research_workspace=self.workspace), base_url='http://127.0.0.1')
        self.addCleanup(self.client.close)
        self.headers = {'Authorization': 'Bearer test-selection-boundary-credential-20261008', 'Origin': 'http://127.0.0.1:5175'}
        self.payload = {'bundle_id': self.bundle['bundle_id'], 'goal': 'TEST ONLY: 원문 선택 전송 경계', 'constraints': []}
        self.ids = [source['source_id'] for source in self.bundle['sources'][:2]]

    def post(self, **changes):
        return self.client.post('/api/research/planning-runs', headers=self.headers, json={**self.payload, **changes})

    def test_selected_input_exact_and_revision_inherits_scope(self):
        original = deepcopy(self.workspace.get_bundle(self.bundle['bundle_id']))
        first = self.post(selected_source_ids=list(reversed(self.ids)),
                          bundle_sha256=self.workspace.digests[self.bundle['bundle_id']])
        self.assertEqual(first.status_code, 201)
        result = first.json()
        self.assertEqual([row['source_id'] for row in result['source_facts']], self.ids)
        self.assertEqual(result['runtime']['user_selected_source_ids'], self.ids)
        self.assertEqual(result['runtime']['input_scope'], 'user_selected_sources')
        self.assertEqual(self.workspace.get_bundle(self.bundle['bundle_id']), original)
        revised = self.post(previous_run_id=result['run_id'], constraints=['TEST ONLY: 바뀐 조건'])
        self.assertEqual(revised.status_code, 201)
        self.assertEqual(revised.json()['source_facts'], result['source_facts'])
        self.assertEqual(revised.json()['runtime']['input_scope'], 'user_selected_sources')
        restored = self.client.get('/api/research/planning-runs/' + result['run_id'], headers=self.headers)
        self.assertEqual(restored.json(), result)

    def test_invalid_scope_is_rejected_before_any_model_or_attempt(self):
        for selection in ([], [self.ids[0], self.ids[0]], ['foreign-source'], None, [True]):
            with self.subTest(selection=selection):
                self.assertEqual(self.post(selected_source_ids=selection).status_code, 400)
        self.assertEqual(self.post(selected_source_ids=self.ids, bundle_sha256='0' * 64).status_code, 409)
        self.assertEqual(self.planner.calls, [])
        with self.workspace.connect() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM research_attempts').fetchone()[0], 0)

    def test_existing_run_cannot_change_its_selected_sources(self):
        first = self.post(selected_source_ids=self.ids).json()
        result = self.post(previous_run_id=first['run_id'], selected_source_ids=[self.ids[0]])
        self.assertEqual(result.status_code, 409)
        self.assertEqual(len(self.planner.calls), 1)

    def coverage_brief(self):
        brief = self.planner.run(self.bundle, self.payload['goal'], [])
        customers, groups = set(), set()
        for source in self.bundle['sources']:
            group = source.get('duplicate_group') or source['source_id']
            if is_customer_source(source) and group not in groups:
                customers.add(source['source_id'])
                groups.add(group)
        denominator = set(sorted(customers)[:2])
        brief['runtime']['processed_source_ids'] = sorted(denominator)
        brief['runtime']['summary_reference_coverage'] = summary_reference_coverage(brief['summaries'], customers, denominator)
        return brief

    def test_valid_summary_coverage_and_missing_are_distinct(self):
        brief = self.coverage_brief()
        projected = project_source_statistics(brief, self.bundle)
        self.assertEqual(projected['summary_reference_coverage_state'], 'provided')
        self.assertEqual(projected['summary_reference_coverage'], brief['runtime']['summary_reference_coverage'])
        del brief['runtime']['summary_reference_coverage']
        self.assertEqual(project_source_statistics(brief, self.bundle)['summary_reference_coverage_state'], 'unavailable')

    def test_invalid_counts_or_noncustomer_denominator_never_reach_public_response(self):
        for field, value in [('input_customer_source_count', True), ('coverage_ratio', -5e-10),
                             ('covered_customer_source_count', 999), ('classification_approved', True)]:
            with self.subTest(field=field):
                brief = self.coverage_brief()
                brief['runtime']['summary_reference_coverage'][field] = value
                projected = project_source_statistics(brief, self.bundle)
                self.assertEqual(projected['summary_reference_coverage_state'], 'invalid')
                self.assertNotIn('summary_reference_coverage', projected)
        brief = self.coverage_brief()
        official = next(source['source_id'] for source in self.bundle['sources'] if not is_customer_source(source))
        brief['runtime']['summary_reference_coverage']['denominator_source_ids'] = [official]
        self.assertNotIn('summary_reference_coverage', project_source_statistics(brief, self.bundle))


if __name__ == '__main__':
    unittest.main()
