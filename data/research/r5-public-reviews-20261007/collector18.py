"""Offline bounded public-page landing; execute only in zero-auth guest."""
import hashlib
import json
from collections import Counter
from pathlib import Path

from lgax_core.public_review_collection import group_and_split, parse_public_review_html, save_landing_db, verify_public_product_page

VERSION = 'lg-public-reviews.20261007.r5-fixed18.v1'
HERE = Path('data/research/r5-public-reviews-20261007')
CAPTURE = Path('/workspace/captures18')
PILOT_CAPTURE = Path('/workspace/captures')
OUT = Path('/artifacts/r5-data18')


def write_json(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    OUT.mkdir()
    registry = json.loads((HERE / 'models18.json').read_bytes())
    assert len(registry) == 18 and Counter(p['product_group'] for p in registry) == {
        'fridge': 6, 'microwave': 6, 'dishwasher': 6}
    receipt = json.loads((CAPTURE / 'receipt.json').read_bytes())
    pilot_receipt = json.loads((PILOT_CAPTURE / 'receipt.json').read_bytes())
    for captured in (receipt, pilot_receipt):
        assert captured['status'] == 'captured' and not captured['authentication_used'] and not captured['cookies_used']
    original = json.loads(Path('data/research/PM-DATA-intake-20261006/generated/dataset.json').read_bytes())
    manuals = {p['model_id']: p for p in original['products']}
    products, records, page_counts = [], [], {}
    for registered in registry:
        sku = registered['model_id']
        pdp = next(s for s in receipt['requests'] if s['model_id'] == sku and s['kind'] == 'pdp')
        raw_pdp = (CAPTURE / (sku + '.pdp.html')).read_bytes()
        assert hashlib.sha256(raw_pdp).hexdigest() == pdp['sha256'] and len(raw_pdp) <= 8 * 1024 * 1024
        identity = verify_public_product_page(raw_pdp, product=registered, source=pdp)
        manual = manuals.get(sku)
        product = {**registered, 'source_kind': 'public',
                   'manual_version': manual['document_version'] if manual else None,
                   'manual_verification': 'existing_verified_public_manual' if manual else 'not_yet_verified',
                   'document_version': manual['document_version'] if manual else 'LG-PDP-' + registered['lge_model_id'] + '-sha256-' + pdp['sha256'][:16],
                   'document_version_basis': 'existing_manual_revision' if manual else 'official_pdp_snapshot_not_manual',
                   'pdp_source': pdp, 'displayed_product_identity': identity}
        products.append(product)
        pilot_source = next((s for s in pilot_receipt['requests'] if s['model_id'] == sku), None)
        if pilot_source:
            source = pilot_source
            raw = (PILOT_CAPTURE / (sku + '.html')).read_bytes()
        else:
            source = next(s for s in receipt['requests'] if s['model_id'] == sku and s['kind'] == 'reviews')
            raw = (CAPTURE / (sku + '.reviews.html')).read_bytes()
        rows = parse_public_review_html(raw, product=product, source=source, limit=10)
        assert len(rows) <= 10
        page_counts[sku] = len(rows)
        records.extend(rows)
    records, summary = group_and_split(records)
    known_dates = [r['purchase_date'] for r in records if r['purchase_date']]
    manifest = {
        'version': VERSION, 'source_kind': 'public', 'collection': summary,
        'selection': '6 registered official models per category; first at most 10 recommendation-order rows per page',
        'model_count': len(products), 'model_page_row_counts': page_counts,
        'max_rows_per_model': 100, 'version_rows_per_model': 10,
        'collection_time': receipt['requests'][0]['captured_at'],
        'sources': pilot_receipt['requests'] + receipt['requests'],
        'actual_purchased_model_verified_count': sum(r['actual_purchased_model_id'] is not None for r in records),
        'publication_date_known_count': sum(r['published_at'] is not None for r in records),
        'visible_purchase_date_range': [min(known_dates), max(known_dates)] if known_dates else None,
        'posting_date_range': None,
        'verified_manual_model_count': len(manuals),
        'exact_sku_execution_status': 'held',
        'exact_sku_execution_hold_reason': 'Purchased SKU is not independently verified by page association.',
        'model_calls': 0, 'synthetic_reviews': 0,
        'limitations': [
            'Official page association is not independently verified purchased SKU; all exact-model inputs held.',
            'Visible purchase date is not posting date; no publication-year, month or season inference.',
            'Only the existing 3 public manuals have verified revisions; 15 PDP snapshots are not manuals.',
            'Current manual reference is not verified purchase-time manual revision.',
            'Recommendation-order bounded nonrandom sample; missing dates and fewer rows are not filled.',
            'Related page pools are globally deduplicated before fixed group split; positive reviews retained.',
            'No automatic complaint labels, customer-population estimates or market-demand conclusions.',
            'Pilot splits were never used for training, independent model evaluation or model input.'
        ],
    }
    write_json('products.json', products)
    write_json('records.json', records)
    write_json('manifest.json', manifest)
    for split in summary['split_counts']:
        write_json(split + '.records.json', [r for r in records if r['split'] == split])
    save_landing_db(OUT / 'public-reviews.sqlite3', records=records, products=products, manifest=manifest)
    # Keep the existing exact manual contract usable, but do not invent executable reviews.
    development = {**original, 'dataset_version': VERSION + '-development-held', 'reviews': []}
    write_json('development.dataset.json', development)
    write_json('execution-holds.json', [{'model_id': p['model_id'], 'eligible_reviews': 0,
                                       'reasons': ['purchased_sku_not_independently_verified']
                                       + ([] if p['manual_version'] else ['manual_revision_not_verified'])}
                                      for p in products])
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file()}
    write_json('files.json', hashes)
    print(json.dumps({'version': VERSION, 'collection': summary, 'models': len(products),
                      'page_rows': page_counts, 'verified_manuals': len(manuals),
                      'exact_sku_input_reviews': 0, 'model_calls': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
