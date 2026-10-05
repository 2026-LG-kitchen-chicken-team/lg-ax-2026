"""Read-only recheck against pinned PR74; every execution requires a new directory."""
import argparse
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

from pypdf import PdfReader
import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[3]
PR_HEAD = '5af64e93b1ca413317a91893e530901fc7f5874e'
PLAN_PATH = 'data/document_plans/lg-three-models-20261005.json'
DATA_PATH = 'data/document_datasets/lg-three-models-20261005.json'
GIT = ['git', '-c', 'safe.directory=' + ROOT.as_posix()]

def digest(raw):
    return sha256(raw).hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-directory', type=Path, required=True)
    args = parser.parse_args()
    run = args.run_directory.resolve()
    run.relative_to(ROOT / 'data/research/P2-DATA-001-recheck-20261005T0550')
    run.mkdir()  # Fail instead of overwriting a previous result.
    private = ROOT / 'private/manual-preflight-20261005' / run.name
    private.mkdir(parents=True, exist_ok=False)
    raw_plan = (ROOT / PLAN_PATH).read_bytes()
    plan = json.loads(raw_plan)
    dataset = json.loads((ROOT / DATA_PATH).read_bytes())
    checks, docs, citations, features = [], [], [], []
    def check(name, passed):
        checks.append({'name': name, 'passed': bool(passed)})
    for relative in [PLAN_PATH, DATA_PATH]:
        pinned = subprocess.run(GIT + ['show', PR_HEAD + ':' + relative], cwd=ROOT, capture_output=True, check=True).stdout
        check(relative + ':same_as_PR74', pinned == (ROOT / relative).read_bytes())
    evidence_by_id = {e['id']: e for e in dataset['evidence']}
    for doc in plan['documents']:
        model = doc['product']['model_id']
        req = urllib.request.Request(doc['url'], headers={'User-Agent': 'LGAX-manual-source-verification/1.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read(12 * 1024 * 1024 + 1)
            status, resolved_url = response.status, response.url
        check(model + ':official_download_hash', digest(raw) == doc['sha256'])
        if digest(raw) != doc['sha256'] or len(raw) > 12 * 1024 * 1024:
            raise ValueError('Official PDF changed or exceeded the bounded size')
        pdf_path = private / (model + '.pdf')
        pdf_path.write_bytes(raw)
        reader = PdfReader(pdf_path)
        pages = [p.extract_text() or '' for p in reader.pages]
        write(private / (model + '.pages.json'), pages)
        all_text = '\n'.join(pages)
        version_parts = doc['document_version'].split(' ')
        check(model + ':version_parts_present', all(p in pages[0] for p in version_parts))
        exact_pages = [i + 1 for i, text in enumerate(pages) if model in text]
        docs.append({'model_id': model, 'document_id': doc['document_id'], 'document_version': doc['document_version'],
                     'url': doc['url'], 'download_http_status': status, 'resolved_url': resolved_url,
                     'sha256': digest(raw), 'page_count': len(pages), 'exact_model_text_pages': exact_pages,
                     'association_basis': doc['applicability']['basis'],
                     'association_independently_proved_by_pdf': bool(exact_pages),
                     'model_link_is_inherited_from_approved_reference_pack': not bool(exact_pages),
                     'all_optional_features_applied_to_sku': False})
        render_pages = {1}
        for selection in doc['selections']:
            eid, number, excerpt = selection['evidence_id'], selection['page'], selection['excerpt']
            page = pages[number - 1]
            start = page.find(excerpt)
            exact = start >= 0 and page.count(excerpt) == 1
            check(eid + ':unique_pdf_slice', exact)
            ev = evidence_by_id[eid]
            check(eid + ':model_version_kind', ev['model_id'] == model and ev['document_version'] == doc['document_version']
                  and ev['source_kind'] == 'public')
            check(eid + ':dataset_text', ev['text'] == excerpt)
            citations.append({'evidence_id': eid, 'document_id': doc['document_id'], 'model_id': model,
                              'document_version': doc['document_version'], 'source_kind': 'public',
                              'page': number, 'section': selection['section'], 'start_char': start,
                              'end_char': start + len(excerpt), 'text_sha256': digest(excerpt.encode()),
                              'pdf_sha256': digest(raw), 'exact_original_slice_verified': exact,
                              'feature_ids': selection['feature_ids'], 'proves_customer_demand': False})
            render_pages.add(number)
        for feature in doc['features']:
            unresolved = feature['id'].endswith('folding-shelf')
            if unresolved:
                scope = 'optional_shared_manual_exact_sku_and_quantity_unconfirmed'
            elif model == 'DUE6BGL2E':
                scope = 'matching_DUE6_family_manual_via_approved_product_association'
            elif model == 'T876MEE1H1':
                scope = 'shared_fridge_manual_general_procedure_via_approved_product_association'
            else:
                scope = 'exact_model_listed_in_manual_named_operation'
            features.append({'feature_id': feature['id'], 'model_id': model,
                             'document_version': doc['document_version'], 'description': feature['description'],
                             'conditions': feature['conditions'], 'evidence_ids': feature['evidence_ids'],
                             'applicability_scope': scope, 'exact_sku_feature_verified_by_these_pdf_citations':
                             bool(exact_pages) and not unresolved,
                             'customer_demand_proved': False,
                             'personal_preset_support_or_absence_proved': False})
        pdf = pdfium.PdfDocument(str(pdf_path))
        for number in sorted(render_pages):
            page = pdf[number - 1]
            bitmap = page.render(scale=1.5)
            bitmap.to_pil().save(private / f'{model}-page{number}.png')
            bitmap.close(); page.close()
        pdf.close()
    check('three_documents_fifteen_citations_nine_features', len(docs) == 3 and len(citations) == 15 and len(features) == 9)
    report = {'checked_at': datetime.now(timezone(timedelta(hours=9))).isoformat(),
              'source_commit': subprocess.run(GIT + ['rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
              'PR74_head': PR_HEAD, 'argv': sys.argv, 'python': sys.version, 'runner_sha256': digest(Path(__file__).read_bytes()),
              'input_versions': {PLAN_PATH: digest(raw_plan), DATA_PATH: digest((ROOT / DATA_PATH).read_bytes())},
              'dataset_version': plan['dataset_version'], 'documents': docs, 'citations': citations, 'features': features,
              'checks': checks, 'passed': all(c['passed'] for c in checks), 'customer_reviews': 0,
              'limitations': ['PDF text presence is separate from exact SKU applicability',
                              'The inherited product-to-manual association was not newly independently established',
                              'Folding shelf exact SKU/quantity remain unconfirmed',
                              'Manual instructions do not establish customer demand, frequency, or benefits',
                              'No PM semantic acceptance, formal dependency release, merge, or Agent completion']}
    write(run / 'audit.json', report)
    print(json.dumps({'passed': report['passed'], 'checks': len(checks), 'documents': len(docs),
                      'citations': len(citations), 'features': len(features), 'model_text_pages':
                      {d['model_id']: d['exact_model_text_pages'] for d in docs}, 'output': str(run / 'audit.json')}, ensure_ascii=False))
    return 0 if report['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
