"""Run only inside the fixed zero-auth validator; normal HTML captured separately."""
import csv
import hashlib
import io
import json
from pathlib import Path

from lgax_core.public_review_collection import group_and_split, parse_public_review_html, save_landing_db
from lgax_core.review_import import import_review_csv

VERSION = 'lg-public-reviews.20261007.r5-pilot1'
CAPTURE = Path('/workspace/captures')
OUT = Path('/artifacts/r5-data')


def write_json(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def make_csv(rows, source_id):
    out = io.StringIO(newline='')
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(('id', 'model_id', 'text', 'source_kind', 'document_version', 'source_id', 'row', 'evidence_id'))
    for row in rows:
        physical = out.getvalue().count('\n') + 1
        writer.writerow((row['review_id'], row['displayed_model_id'], row['text'], 'public',
                         row['document_version'], source_id, physical, 'LGE-R5-EV-' + row['original_review_id']))
    return out.getvalue().encode('utf-8')


def main():
    OUT.mkdir()
    original = json.loads(Path('data/research/PM-DATA-intake-20261006/generated/dataset.json').read_bytes())
    receipt = json.loads((CAPTURE / 'receipt.json').read_bytes())
    assert receipt['status'] == 'captured' and not receipt['authentication_used'] and not receipt['cookies_used']
    ids = {'T876MEE1H1': 'MD10758826', 'DUE6BGL2E': 'MD10492836', 'MW23FDI': 'MD10738847'}
    products = [{**p, 'lge_model_id': ids[p['model_id']], 'manual_version': p['document_version']} for p in original['products']]
    records = []
    for product in products:
        source = next(s for s in receipt['requests'] if s['model_id'] == product['model_id'])
        records.extend(parse_public_review_html((CAPTURE / (product['model_id'] + '.html')).read_bytes(),
                                                product=product, source=source, limit=10))
    records, summary = group_and_split(records)
    manifest = {'version': VERSION, 'source_kind': 'public', 'collection': summary,
                'selection': 'First 10 normal public recommendation-order review rows per pilot model',
                'collection_time': receipt['requests'][0]['captured_at'], 'sources': receipt['requests'],
                'actual_purchased_model_verified_count': 0, 'publication_date_known_count': 0,
                'model_calls': 0, 'synthetic_reviews': 0,
                'limitations': ['Official page association is not independently verified purchased SKU.',
                                'Visible purchase date is not posting date; published_at remains null.',
                                'Current manual version is a reference, not verified purchase-time revision.',
                                'Recommendation-order nonrandom bounded sample; positive reviews retained.',
                                'No automatic complaint labels or market-demand estimates.']}
    write_json('records.json', records)
    write_json('products.json', products)
    write_json('manifest.json', manifest)
    for split in summary['split_counts']:
        write_json(split + '.records.json', [r for r in records if r['split'] == split])
    save_landing_db(OUT / 'public-reviews.sqlite3', records=records, products=products, manifest=manifest)
    combined = {**original, 'dataset_version': VERSION + '-development', 'reviews': []}
    origins = []
    csv_sources = []
    for product in original['products']:
        rows = [r for r in records if r['displayed_model_id'] == product['model_id'] and r['split'] == 'development']
        if not rows:
            continue
        source_id = 'LGE-R5-' + product['model_id'] + '-pilot1'
        raw = make_csv(rows, source_id)
        approval = {'document_id': source_id, 'model_id': product['model_id'],
                    'document_version': product['document_version'], 'source_kind': 'public',
                    'sha256': hashlib.sha256(raw).hexdigest()}
        imported = import_review_csv(raw, products=[product], sources=[approval], dataset_version=VERSION)
        combined['reviews'].extend(imported.dataset['reviews'])
        combined['evidence'].extend(imported.dataset['evidence'])
        origins.extend(imported.origins)
        (OUT / (product['model_id'] + '.development.csv')).write_bytes(raw)
        csv_sources.append(approval)
    write_json('development.dataset.json', combined)
    write_json('development.origins.json', origins)
    write_json('development.csv-sources.json', csv_sources)
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file()}
    write_json('files.json', hashes)
    print(json.dumps({'version': VERSION, 'summary': summary, 'development_reviews': len(combined['reviews']),
                      'manual_evidence': len(original['evidence']), 'features': len(original['features']),
                      'models': ids, 'model_calls': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
