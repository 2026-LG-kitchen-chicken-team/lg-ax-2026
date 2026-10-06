"""Validate R2 inputs/provenance without model calls or output answers."""
import hashlib
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator
from lgax_core.feature_scope import select_feature_scope
from lgax_core.judgement_contract import schema_for
from lgax_core.store import DemoStore


def main():
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    provenance = json.loads((base / 'input-provenance.json').read_bytes())
    assert len(provenance['cases']) == 3 and provenance['max_batch_generations'] == 24
    assert provenance['independent_evaluation_answers_used'] is False
    rows = []
    for entry in provenance['cases']:
        input_raw = (base / entry['input']).read_bytes()
        dataset_raw = (base / entry['dataset']).read_bytes()
        assert hashlib.sha256(input_raw).hexdigest() == entry['input_sha256']
        assert hashlib.sha256(dataset_raw).hexdigest() == entry['dataset_sha256']
        payload, dataset = json.loads(input_raw), json.loads(dataset_raw)
        Draft202012Validator(schema_for('input')).validate(payload)
        DemoStore(dataset)
        selected = select_feature_scope(payload['request'],
            {payload['product']['model_id']: payload['product']['document_version']}, dataset)
        scoped = selected['inputs'][0]
        assert scoped['product'] == payload['product']
        for key in ('sources', 'features'):
            assert {v['id']: v for v in scoped[key]} == {v['id']: v for v in payload[key]}
        if entry['case_id'] == 'fridge-missing-manual':
            assert payload['features'] == []
            assert payload['sources'] and all(s['source_type'] == 'review' for s in payload['sources'])
            assert all(v['id'] != 'MANUAL-001' for v in dataset['evidence'])
            assert all(v['id'] != 'FEATURE-001' for v in dataset['features'])
        rows.append({'case_id': entry['case_id'], 'valid': True, 'input_sha256': entry['input_sha256'],
                     'dataset_sha256': entry['dataset_sha256']})
    print(json.dumps({'valid_inputs': rows, 'model_calls': 0, 'quality_verdict': 'not evaluated'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
