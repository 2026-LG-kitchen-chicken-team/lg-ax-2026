"""Record exact exit codes; validate provenance without calling any model."""
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


def main():
    result_path = OUT / 'final-checks.json'
    if result_path.exists():
        raise FileExistsError(result_path)
    relative = OUT.relative_to(ROOT).as_posix()
    commands = [
        [sys.executable, '-m', 'ruff', 'check', relative + '/audit_pdf.py', relative + '/model_check.py',
         relative + '/finalize_evidence.py', relative + '/check_evidence.py'],
        [sys.executable, '-X', 'utf8', 'scripts/sync_agent_rules.py', '--check'],
        [sys.executable, '-X', 'utf8', 'scripts/check_contracts.py'],
        [sys.executable, '-X', 'utf8', 'scripts/phase2.py', 'validate'],
        ['git', 'diff', '--check'],
    ]
    results = []
    for command in commands:
        process = subprocess.run(command, cwd=ROOT, capture_output=True, encoding='utf-8', timeout=90, check=False)
        results.append({'command': command, 'exit_code': process.returncode,
                        'stdout': process.stdout, 'stderr': process.stderr})
    audit = json.loads((OUT / 'pdf-run3/audit.json').read_text(encoding='utf-8'))
    model = json.loads((OUT / 'model-run1/model-result.json').read_text(encoding='utf-8'))
    executed = OUT / 'model-run1/executed_model_check.py.txt'
    source_hash = next(value for key, value in model['source_sha256'].items() if key.endswith('model_check.py'))
    provenance = {
        'audit_54_checks_pass': len(audit['checks']) == 54 and audit['passed'],
        'executed_model_script_matches_recorded_sha256': sha256(executed.read_bytes()).hexdigest() == source_hash,
        'final_audit_script_matches_recorded_sha256': sha256((OUT / 'audit_pdf.py').read_bytes()).hexdigest() == audit['runner_sha256'],
        'model_call_count_one': model['actual_model_calls'] == 1,
        'semantic_failure_preserved': model['passed'] is False and model['status'] == 'one_case_semantic_fail',
        'own_proxy_stopped': model['owned_proxy_stopped'] is True,
        'original_plan_hash_unchanged': sha256((ROOT / 'data/document_plans/lg-three-models-20261005.json').read_bytes()).hexdigest() == audit['input_versions']['data/document_plans/lg-three-models-20261005.json'],
    }
    result = {'observed_at': datetime.now(timezone(timedelta(hours=9))).isoformat(),
              'base_commit': model['source_commit'], 'results': results, 'provenance': provenance,
              'production_code_changed': False, 'new_model_calls': 0,
              'passed': all(row['exit_code'] == 0 for row in results) and all(provenance.values())}
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': result['passed'], 'exit_codes': [row['exit_code'] for row in results],
                      'provenance': provenance}, ensure_ascii=False))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
