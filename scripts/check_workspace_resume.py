"""Verify immutable records after an actual workspace service restart (read-only)."""

import argparse
import json
from pathlib import Path

from lgax_mcp.workspace_client import WorkspaceClient


def check(url, credential_file, live_proof):
    proof = json.loads(live_proof.read_text('utf-8'))
    credential = json.loads(credential_file.read_text('utf-8'))
    client = WorkspaceClient(url, credential['token'])
    expected = {call['result']['data']['run']['id']: call['result']['data'] for call in proof['calls']
                if call['result'].get('ok') and 'run' in call['result'].get('data', {})}
    for run_id, snapshot in expected.items():
        assert client.get_run(run_id)['data'] == snapshot
    runs = client.list_runs(proof['project_id'])['data']['runs']
    assert {snapshot['run']['id'] for snapshot in runs} == set(expected)
    return {'status': 'pass', 'execution_kind': 'live_service', 'project_id': proof['project_id'],
            'retained_run_ids': sorted(expected), 'retained_input_and_unconfirmed_and_source_hash': True,
            'analysis_implemented': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:18869')
    parser.add_argument('--credential-file', type=Path, required=True)
    parser.add_argument('--live-proof', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = check(args.url, args.credential_file, args.live_proof)
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print(json.dumps(result))
