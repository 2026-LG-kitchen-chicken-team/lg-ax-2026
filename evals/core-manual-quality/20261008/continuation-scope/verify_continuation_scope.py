"""Replay the fixed existing reference export without interpreting continuation steps."""
import argparse
import hashlib
import html
import json
import pathlib
import zipfile
from copy import deepcopy

from lgax_core.guides import build_official_reference_guide, render_guide_html, render_guide_markdown

ROOT = pathlib.Path(__file__).resolve().parents[4]
BASE = ROOT / 'evals/core-manual-quality/20261008/d2-reference-consumer'
INPUT = ROOT / 'data/research/r8-public-research-20261007/d1-d2-01a10600/agent-input/dishwasher/research-bundle.json'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=pathlib.Path, required=True)
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    input_raw = INPUT.read_bytes()
    assert sha(input_raw) == 'e922c51dd7f1f805953fd8e4df4ea1a75479ad8da0e2ba500b541acd720e84d0'
    bundle = json.loads(input_raw)
    unchanged = deepcopy(bundle)
    old_raw = (BASE / 'references/dishwasher.json').read_bytes()
    assert sha(old_raw) == 'bfca53d9ab18632882ec38f3b76b16118c85b025096b19c5fae8c800d463992d'
    before = json.loads(old_raw)
    guide = build_official_reference_guide(bundle, [s['source_id'] for s in before['sources']])
    assert guide['sources'] == before['sources'] and len(guide['sources']) == 24
    expected = deepcopy(before)
    expected['notice'] = guide['notice']
    assert guide == expected
    care = [s for s in guide['sources'] if s['source_id'].startswith('D2-DUE-CARE-')]
    assert len(care) == 14
    by_id = {s['source_id']: s for s in care}
    warnings = [
        ('D2-DUE-CARE-DW-INTERNAL-CLEAN-P39', [40]),
        ('D2-DUE-CARE-DW-TUB-CITRIC-P41', [42]),
        ('D2-DUE-CARE-DW-TUB-VINEGAR-P42', [41, 43]),
        ('D2-DUE-CARE-DW-NOZZLE-P42', [41, 43]),
        ('D2-DUE-CARE-DW-STORAGE-P43', [42]),
    ]
    entries = []
    for sid, pages in warnings:
        source = by_id[sid]
        assert source['metadata']['continuation_pages'] == pages
        assert source['page_model'] is None and source['facts'] == []
        entries.append({'source_id': sid, 'document_version': source['document_version'],
                        'locator': source['locator'], 'text_sha256': sha(source['text'].encode('utf-8')),
                        'continuation_pages_preserved': pages, 'step_relationship_confirmed': False})
    rendered = {'.html': render_guide_html(guide), '.md': render_guide_markdown(guide),
                '.json': json.dumps(guide, ensure_ascii=False, indent=2, allow_nan=False) + '\n'}
    with zipfile.ZipFile(BASE / 'official-references.zip') as archive:
        names = archive.namelist()
        for suffix in ['.html', '.md']:
            name = next(n for n in names if n.endswith('dishwasher' + suffix))
            old = archive.read(name).decode('utf-8')
            notice_before = html.escape(before['notice'], quote=True)
            notice_after = html.escape(guide['notice'], quote=True)
            expected_output = old.replace(notice_before, notice_after).replace(
                '연속 페이지:', '자료에 표시된 참조 쪽 · 같은 절/단계 미확인:')
            assert rendered[suffix] == expected_output, suffix + ' changes exceed notice/label scope'
            assert rendered[suffix].count('자료에 표시된 참조 쪽 · 같은 절/단계 미확인:') == 9
            assert '연속 페이지:' not in rendered[suffix]
            assert '다른 절이 포함될 수 있어' in rendered[suffix]
    assert bundle == unchanged and INPUT.read_bytes() == input_raw
    pins = []
    for suffix, text in rendered.items():
        target = output / ('dishwasher-reference' + suffix)
        assert not target.exists()
        raw = text.encode('utf-8')
        target.write_bytes(raw)
        pins.append({'path': target.name, 'sha256': sha(raw), 'bytes': len(raw)})
    result = {'record_id': 'CORE-X1-CONTINUATION-SCOPE-01a10729-01', 'status': 'PASS',
              'input_bundle_id': bundle['bundle_id'], 'input_sha256': sha(input_raw),
              'DATA_head': '94b560de72f91795cfd50aada9e17d6773383ae1',
              'DATA_warning_head': '9516caa27f05330830aa91d725d4bd8902bf4d9e',
              'CORE_before_head': '3e2214920162f8725ce4f29c554ca932086e26c9',
              'baseline_output_sha256': sha(old_raw), 'sources': 24, 'care_sources': 14,
              'warning_sources': entries, 'reference_labels': 9, 'source_objects_unchanged': True,
              'display_only_delta_matches': True, 'outputs': pins,
              'metadata_step_relationship_confirmed': False, 'metadata_values_corrected': False,
              'new_model_calls': 0, 'model_version': None, 'model_digest': None, 'usage': None,
              'actual_planning_run': False, 'new_OCR_calls': 0, 'exact_sku_confirmed': False,
              'customer_cause_recovery_confirmed': False, 'PM_acceptance': False}
    target = output / 'consumer-receipt.json'
    assert not target.exists()
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'PASS', 'sources_preserved': 24, 'care_sources': 14, 'warnings_scoped': 5,
                      'reference_labels': 9, 'new_model_calls': 0}))


if __name__ == '__main__':
    main()
