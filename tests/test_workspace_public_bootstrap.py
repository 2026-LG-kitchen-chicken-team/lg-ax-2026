"""Public sources require authenticated workspace access and the shared schema."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import secrets
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient
from jsonschema import ValidationError
from lgax_contracts import validate
from lgax_api.server import create_app
from lgax_api.workspace_auth import TokenRegistry
from lgax_api.workspace_bootstrap import workspace_bootstrap
from lgax_api.workspace_server import create_workspace_app
from lgax_core.document_workspace import WorkspaceDocumentStore
from lgax_core.store import DemoStore

ROOT = Path(__file__).resolve().parents[1]


class WorkspacePublicBootstrapTests(unittest.TestCase):
    def store(self):
        return WorkspaceDocumentStore(json.loads((ROOT / 'data/research/PM-DATA-intake-20261006/generated/dataset.json').read_bytes()))

    def test_public_no_review_reference_pack_has_shared_contract_and_same_digest(self):
        store = self.store()
        with TemporaryDirectory() as temporary:
            token = secrets.token_urlsafe(40)
            registry = TokenRegistry([{'principal_id': 'reader', 'role': 'viewer', 'token_sha256': sha256(token.encode()).hexdigest()}])
            app = create_workspace_app(Path(temporary) / 'workspace.sqlite', registry, evidence_store=store)
            with TestClient(app) as client:
                self.assertEqual(client.get('/api/workspace/bootstrap').status_code, 401)
                response = client.get('/api/workspace/bootstrap', headers={'Authorization': 'Bearer ' + token})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['cache-control'], 'no-store')
                result = response.json()
                validate('PublicBootstrapResponse', result)
                validate('WorkspaceBootstrapResponse', result)
                self.assertEqual(result['data']['manifest']['dataset_sha256'], app.state.workspace.dataset_sha256)
                self.assertEqual(result['data']['reviews'], [])
                self.assertEqual(result['data']['manifest']['review_count'], 0)
                self.assertEqual(result['data']['manifest']['source_kind'], 'public')
                self.assertEqual(result['data']['evidence'], store.bootstrap()['data']['evidence'])
                self.assertNotIn(token, json.dumps(result))
                with self.assertRaises(ValidationError):
                    validate('BootstrapResponse', result)
            with self.assertRaises(ValueError):
                create_app(store)

    def test_synthetic_contract_and_default_store_are_preserved(self):
        store = DemoStore()
        result = workspace_bootstrap(store)
        self.assertEqual(result, store.bootstrap())
        validate('BootstrapResponse', result)
        validate('WorkspaceBootstrapResponse', result)

    def test_public_relabel_or_unknown_entity_scope_is_rejected(self):
        result = workspace_bootstrap(self.store())
        bad = deepcopy(result)
        bad['data']['evidence'][0]['source_kind'] = 'synthetic'
        with self.assertRaises(ValidationError):
            validate('WorkspaceBootstrapResponse', bad)
        bad = deepcopy(result)
        bad['data']['manifest']['source_kind'] = 'synthetic'
        with self.assertRaises(ValidationError):
            validate('WorkspaceBootstrapResponse', bad)
