"""Role-only mutations of actual sources test taxonomy, never customer/model quality."""
import json
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import ValidationError
from lgax_contracts.research import validate_research_bundle
from lgax_core.public_planning import is_customer_source

PACK = Path(__file__).resolve().parents[1] / 'data/research/r8-public-research-20261007/bundles/dishwasher.development.research-bundle.json'
class ActualSourceRoleTests(unittest.TestCase):
    def test_official_answer_is_not_a_customer_question(self):
        bundle = json.loads(PACK.read_text('utf-8'))
        official = deepcopy(next(source for source in bundle['sources'] if source['source_type'] == 'manual'))
        self.assertFalse(is_customer_source(official))
        # Metadata mutations only: no invented review text or saved corpus.
        official['source_type'] = 'qa'
        official['source_role'] = 'official_answer'
        self.assertFalse(is_customer_source(official))
        official['source_role'] = 'customer_question'
        self.assertTrue(is_customer_source(official))
    def test_official_documents_cannot_be_tagged_as_customer_experience(self):
        bundle = json.loads(PACK.read_text('utf-8'))
        validate_research_bundle(bundle)
        next(source for source in bundle['sources'] if source['source_type'] == 'manual')['source_role'] = 'customer_experience'
        with self.assertRaises(ValidationError):
            validate_research_bundle(bundle)
if __name__ == '__main__':
    unittest.main()
