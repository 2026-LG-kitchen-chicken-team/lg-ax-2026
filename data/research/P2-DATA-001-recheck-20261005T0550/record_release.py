"""Read only sanitized operation receipts; never read personal auth files."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PRIVATE = ROOT / 'private/manual-preflight-20261005'
RESERVATION = 'manual-ginaginaring-data001-recheck-20261005T0550'


def main():
    releases = sorted(PRIVATE.glob('release-*-receipt.json'))
    statuses = sorted(PRIVATE.glob('status-*-receipt.json'))
    release = json.loads(releases[-1].read_text(encoding='utf-8'))
    status = json.loads(statuses[-1].read_text(encoding='utf-8'))
    release_result = json.loads(release['stdout'])
    current = json.loads(status['stdout'])
    compact = {k: current.get(k) for k in ['global_mode', 'members', 'reservations', 'viewer', 'observed_at']}
    passed = (release['exit_code'] == 0 and release_result.get('released') is True
              and status['exit_code'] == 0 and compact['global_mode'] == 'off'
              and not any(compact['members'].values())
              and not any(row['id'] == RESERVATION for row in compact['reservations']))
    record = {'reservation_id': RESERVATION, 'authenticated_account': 'ginaginaring',
              'release_receipt': releases[-1].name, 'release_result': release_result,
              'status_receipt': statuses[-1].name, 'current': compact, 'passed': passed,
              'tokens_or_config_copied': False}
    path = OUT / 'release-confirmation.json'
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
