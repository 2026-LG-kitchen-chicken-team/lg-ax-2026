"""Fixed actual-source consumer audit; no planner, model, network or new source collection."""
import contextlib
import hashlib
import importlib.util
import io
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

from lgax_contracts.research import validate_research_bundle
from lgax_core.guides import (
    build_official_guide,
    build_official_reference_guide,
    render_guide_html,
    render_guide_markdown,
)

ROOT = Path(__file__).resolve().parent
OUT = Path('/out')
BASE = ROOT / 'data/research/r8-public-research-20261007/d1-d2-01a10600'

def read(path):
    return json.loads(path.read_text('utf-8'))

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

def rejected(action, kind=ValueError):
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        try:
            action()
        except kind:
            return
    raise AssertionError('Required rejection was not observed')

old = module('before_guides', ROOT / 'baseline/before_guides.py')
cli = module('guide_cli', ROOT / 'scripts/export_research_guide.py')
delivery = read(ROOT / 'evals/data-d1-d2/20261007-01a10600/current-delivery.json')
members = read(BASE / 'd1-membership.json')
assert len(members) == 238 and len({m['original_review_id'] for m in members}) == 238
assert Counter(m['split'] for m in members) == {'development': 141, 'independent_evaluation': 36, 'demonstration': 49, 'quarantine': 12}
development = {m['original_review_id']: m for m in members if m['split'] == 'development'}
assert sha((BASE / 'd2-source-pack.json').read_bytes()) == delivery['source_pack_sha256']
assert sha((ROOT / 'packages/contracts/schemas/research-planning.schema.json').read_bytes()) == delivery['canonical_input_checks']['schema_sha256']

groups = {}
all_review_ids = set()
all_review_count = 0
all_sources = 0
all_official = 0
bundles = {}
for group, model, total, reviews, references, manual_count in [
    ('fridge', 'T876MEE1H1', 58, 48, 10, 8),
    ('dishwasher', 'DUE6BGL2E', 73, 48, 24, 7),
    ('microwave', 'MW23FDI', 53, 45, 8, 6),
]:
    path = BASE / f'agent-input/{group}/research-bundle.json'
    bundle = read(path)
    validate_research_bundle(bundle)
    before = deepcopy(bundle)
    assert sha(path.read_bytes()) == delivery['canonical_input_checks']['groups'][group]['sha256']
    assert len(bundle['sources']) == total
    baseline = read(ROOT / f'baseline/{group}.json')
    baseline_reviews = {s['source_id']: s for s in baseline['sources'] if s['source_type'] == 'review'}
    actual_reviews = {s['source_id']: s for s in bundle['sources'] if s['source_type'] == 'review'}
    assert len(actual_reviews) == reviews and actual_reviews == baseline_reviews
    for source in actual_reviews.values():
        oid = source['metadata']['original_review_id']
        member = development[oid]
        assert oid not in all_review_ids
        all_review_ids.add(oid)
        assert source['purchased_model'] is None and source['published_at'] is None
        assert source['metadata']['split'] == 'development'
        assert source['metadata']['original_input_hold_reasons'] == member['input_hold_reasons']
        assert source['metadata']['strict_exact_model_eligible_for_model_input'] is False
        assert sha(source['text'].encode()) == member['text_sha256']
    ids = [s['source_id'] for s in bundle['sources'] if s['source_role'] in {'official_document', 'official_answer'}]
    reference = build_official_reference_guide(bundle, ids)
    assert len(ids) == references and reference['sources'] == [s for s in bundle['sources'] if s['source_id'] in ids]
    assert reference['exact_sku_applicability_confirmed'] is False
    html = render_guide_html(reference)
    markdown = render_guide_markdown(reference)
    args = ['--bundle', str(path), '--output-prefix', str(OUT / 'references' / group)]
    for sid in ids:
        args += ['--source-id', sid]
    with contextlib.redirect_stdout(io.StringIO()):
        assert cli.main(args) == 0
    for suffix, expected in [('.json', json.dumps(reference, ensure_ascii=False, indent=2, allow_nan=False)+'\n'), ('.html', html), ('.md', markdown)]:
        assert (OUT / 'references' / (group+suffix)).read_bytes() == expected.encode('utf-8'), (group, suffix)
    rejected(lambda args=args: cli.main(args), SystemExit)
    rejected(lambda args=args, model=model: cli.main(args + ['--page-model', model]), SystemExit)
    rejected(lambda path=path, ids=ids: cli.main(['--bundle', str(path), '--source-id', ids[0], '--output-prefix', str(path.with_suffix('')), '--overwrite']), SystemExit)
    old_guide = old.build_official_guide(bundle, model)
    new_guide = build_official_guide(bundle, model)
    assert new_guide == old_guide and len(new_guide['sources']) == manual_count
    assert render_guide_html(new_guide) == old.render_guide_html(old_guide)
    assert render_guide_markdown(new_guide) == old.render_guide_markdown(old_guide)
    assert bundle == before
    groups[group] = {'bundle_id': bundle['bundle_id'], 'bundle_sha256': sha(path.read_bytes()), 'sources': total, 'review_objects_equal_to_fixed_R8': reviews, 'official_reference_count': references, 'source_ids': ids, 'page_model_manual_count_unchanged': manual_count, 'old_official_three_formats_equal': True, 'cli_direct_function_three_formats_equal': True, 'input_and_overwrite_guards': 'PASS'}
    bundles[group] = bundle
    all_sources += total
    all_review_count += reviews
    all_official += references
assert all_review_ids == set(development)
assert (all_sources, all_review_count, all_official) == (184, 141, 42)

dw = bundles['dishwasher']
question = next(s for s in dw['sources'] if s['source_id'] == 'D2-DW-QA-470877-Q')
answer = next(s for s in dw['sources'] if s['source_id'] == 'D2-DW-QA-470877-A')
rejected(lambda: build_official_reference_guide(dw, [question['source_id']]))
rejected(lambda: cli.main(['--bundle', str(BASE/'agent-input/dishwasher/research-bundle.json'), '--source-id', question['source_id'], '--output-prefix', '/out/question-must-not-export']))
assert not list(OUT.glob('question-must-not-export.*'))
assert question['source_role'] == 'customer_question' and answer['source_role'] == 'official_answer'
dwhtml = (OUT/'references/dishwasher.html').read_text('utf-8')
dwmd = (OUT/'references/dishwasher.md').read_text('utf-8')
for output in [dwhtml, dwmd]:
    assert '작성 역할: 공식 답변' in output
    assert '페이지 모델 미확인' in output and '연속 페이지' in output and '원문 숫자·단위 주의' in output
    assert '선택 발췌 바깥의 원문 대조' in output
    assert '600' in output and '590' in output and '567' in output
assert question['source_id'] not in dwhtml and question['source_id'] not in dwmd

original = {a['audit_evidence_id']: a for a in read(ROOT/'baseline/audit252.json')}
index = read(BASE/'d2-care-evidence-index.json')
assert len(index) == len(original) == 14
canonical = {s['source_id']: s for s in dw['sources']}
mapped = []
for entry in index:
    audit = original[entry['audit_evidence_id']]
    for key in audit:
        if key != 'native_exact_excerpt':
            assert entry[key] == audit[key], (entry['audit_evidence_id'], key)
    source = canonical[entry['canonical_source_id']]
    assert entry['canonical_excerpt_ref']['source_id'] == source['source_id']
    assert source['text'] == audit['native_exact_excerpt']
    assert sha(source['text'].encode()) == audit['native_excerpt_sha256'] == source['metadata']['text_sha256']
    assert source['metadata']['original_source_id'] == audit['source_id']
    assert source['metadata']['pdf_sha256'] == audit['pdf_sha256']
    assert source['document_version'] == audit['document_version']
    for key in ['page', 'printed_page', 'start_char', 'end_char']:
        assert source['locator'][key] == audit[key]
    assert source['page_model'] is None and source['purchased_model'] is None and source['published_at'] is None
    assert source['facts'] == [] and source['metadata']['ocr_used'] is False
    assert source['metadata']['numeric_facts_extracted_automatically'] is False
    mapped.append({'canonical_source_id': source['source_id'], 'audit_evidence_id': audit['audit_evidence_id'], 'original_source_id': audit['source_id'], 'document_version': audit['document_version'], 'page': audit['page'], 'start_char': audit['start_char'], 'end_char': audit['end_char'], 'native_excerpt_sha256': audit['native_excerpt_sha256'], 'pdf_sha256': audit['pdf_sha256'], 'page_model': None, 'original_audit_role': audit['source_role'], 'canonical_source_role': source['source_role'], 'continuation_pages': source['metadata']['continuation_pages'], 'applicability': source['metadata']['applicability'], 'native_unit_caution': source['metadata']['native_unit_caution']})
assert '50 7' in canonical['D2-DUE-CARE-DW-STORAGE-P43']['text']
assert not {'D2-DW-QA-470877-Q'} & set(groups['dishwasher']['source_ids'])
receipt = {'record_id': 'CORE-X1-D2-CONSUMER-01a10729-01', 'DATA_head': '94b560de72f91795cfd50aada9e17d6773383ae1', 'CORE_before_head': 'd1ce2f9dfb60e8179daadf1c566f097228aba594', 'P0_contract_head': 'ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f', 'total_sources': 184, 'actual_review_objects_preserved': 141, 'official_reference_sources': 42, 'canonical_care_sources': 14, 'groups': groups, 'care_mapping': mapped, 'qa_question_answer_separated': True, 'scope_and_native_units_preserved': True, 'model_calls': 0, 'new_sources_collected': 0, 'ocr_calls': 0, 'independent_quality_evaluation_repeated': False, 'runtime_registered': False, 'exact_sku_applicability_confirmed': False, 'actual_customer_cause_recovery_confirmed': False, 'actual_concept_generated': False, 'PM_acceptance': False, 'parent_done': False}
(OUT/'consumer-audit.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'PASS','bundles':3,'sources':184,'reviews_preserved':141,'official_references':42,'care_native_ranges':14,'model_calls':0}))
