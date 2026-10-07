"""Bind new normal-UI date/topic observations to immutable R5 metadata."""
from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import Counter
from datetime import date, datetime
from pathlib import Path

ROOT = Path.cwd()
UNIT = 'evals/data456-r5-followup/20261007-01a10c5c-de40f92a'
PACK = ROOT / 'data/research/r5-public-reviews-20261007'


def load(path: Path) -> object:
    return json.loads(path.read_bytes())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    observations = load(ROOT / UNIT / 'public-ui-date-topic-observations.json')
    products = load(PACK / 'fixed18/products.json')
    records = load(PACK / 'fixed18/records.json')
    sidecar = load(PACK / 'balanced-pilot-v2/records.json')
    registry = {product['model_id']: product['lge_model_id'] for product in products}
    lookup = {str(row['original_review_id']): ('fixed18', index, row) for index, row in enumerate(records)}
    for index, row in enumerate(sidecar):
        lookup.setdefault(str(row['original_review_id']), ('balanced-pilot-v2', index, row))
    checks = []

    def check(name: str, passed: bool) -> None:
        checks.append({'name': name, 'passed': bool(passed)})
        if not passed:
            raise AssertionError(name)

    check('immutable fixed18 raw SHA', sha(PACK / 'fixed18/records.json')
          == '98830d3078d5c14443ee672a4fd6d5ae7fbafe6c77ea15ab6b14828ad2d5ad6f')
    check('immutable sidecar raw SHA', sha(PACK / 'balanced-pilot-v2/records.json')
          == 'd8ac06a75f53eac2fc2db469d78fa967bbc20883048aa44190217fd19d26fb7d')
    check('exact 238 unique original records retained', len(lookup) == 238)
    check('metadata observations only', observations['privacy'] == 'author/household/contact/body/media not exported')
    check('no inferred publication date', observations['same_observed_result_on_every_page'] == {
        'publication_nodes': 0, 'ld_json_nodes': 0, 'visible_review_publication_label_present': False,
        'purchase_label': '구매 일자', 'published_at_inferred': False})
    check('15 additional pages', len(observations['observations']) == 15)
    canonical = json.dumps(observations['observations'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    check('browser observation byte-for-byte transcription', hashlib.sha256(canonical).hexdigest()
          == '8379d8400b1f5a20498def0396dfa8ad061c4c7684467c2e4013c89e21d3c013')
    bindings = []
    topics = {}
    observed_ids = []
    for page in observations['observations']:
        check('official model/page mapping', registry[page['model']] == page['page'])
        check('bounded visible page rows', 0 < len(page['rows']) <= 10)
        datetime.fromisoformat(page['observed_at_utc'])
        url = observations['source_url_template'].replace('{page}', page['page'])
        for topic in page['vendor_topic_candidates']:
            topics.setdefault(topic, []).append({'model': page['model'], 'source_url': url,
                                                'observed_at_utc': page['observed_at_utc']})
        for rank, (review_id, row_page, date_text) in enumerate(page['rows'], 1):
            observed_ids.append(review_id)
            parsed = date.fromisoformat(date_text.replace('.', '-')).isoformat()
            item = {'original_review_id': review_id, 'model_page': page['model'],
                    'source_url': url, 'UI_rank': rank, 'review_row_page': row_page,
                    'purchase_date_observed': parsed, 'purchase_date_label': '구매 일자',
                    'published_at_confirmed': None, 'raw_body_rechecked': False,
                    'row_page_differs_from_display_page': row_page != page['page']}
            if review_id in lookup:
                pack, index, record = lookup[review_id]
                item.update(fixed_pack=pack, fixed_record_pointer=f'/{index}',
                            original_text_sha256=record.get('original_text_sha256', record.get('original_visible_text_sha256')),
                            fixed_purchase_date=record['purchase_date'], fixed_split=record['split'],
                            fixed_source_locator=record['source_locator'], fixed_published_at=record['published_at'],
                            purchase_date_matches_fixed=record['purchase_date'] == parsed)
                check('fixed publication date remains null', record['published_at'] is None)
            else:
                item['fixed_pack'] = None
                item['new_ID_not_added_to_fixed_pack'] = True
            bindings.append(item)
    check('149 direct date observations', len(bindings) == 149)
    check('seven candidate vendor topic names', len(topics) == 7)
    structured = load(ROOT / UNIT / 'pdp-structured-date-observations.json')
    canonical_pdp = json.dumps(structured['observations'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    check('PDP observation transcription from browser', hashlib.sha256(canonical_pdp).hexdigest()
          == structured['browser_observation_canonical_sha256'])
    normalized_records = {}
    for pack, index, row in lookup.values():
        text = ' '.join(unicodedata.normalize('NFKC', row['text']).split())
        digest = hashlib.sha256(text.encode()).hexdigest()
        normalized_records.setdefault(digest, []).append((pack, index, row))
    structured_bindings = []
    for page in structured['observations']:
        for observed in page['reviews']:
            matches = normalized_records.get(observed['normalized_body_sha256'], [])
            scoped = [item for item in matches if item[2].get('displayed_model_id') == page['model']]
            check('structured date binds to exact normalized original body and page', len(scoped) == 1)
            pack, index, original = scoped[0]
            same_date = observed['datePublished'] == original['purchase_date']
            check('JSON-LD date equals UI purchase date', same_date)
            structured_bindings.append({**observed, 'displayed_model': page['model'],
                'source_url': page['source_url'], 'original_review_id': original['original_review_id'],
                'fixed_pack': pack, 'fixed_record_pointer': f'/{index}',
                'date_equals_displayed_purchase_date': same_date,
                'verified_posting_date': None,
                'original_raw_UTF8_hash_matches': observed['raw_body_sha256'] == original.get('original_text_sha256', original.get('original_visible_text_sha256'))})
    check('nine ambiguous structured dates preserved', len(structured_bindings) == 9)
    report = {
        'status': 'PASS', 'check_count': len(checks), 'checks': checks,
        'observations_sha256': sha(ROOT / UNIT / 'public-ui-date-topic-observations.json'),
        'live_model_pages': 15, 'live_date_observations': len(bindings), 'live_unique_review_IDs': len(set(observed_ids)),
        'fixed_ID_matches': sum(item['fixed_pack'] is not None for item in bindings),
        'new_UI_IDs_not_imported': sum(item['fixed_pack'] is None for item in bindings),
        'fixed_date_agreement': dict(Counter(item.get('purchase_date_matches_fixed') for item in bindings if item['fixed_pack'])),
        'review_row_page_mismatches': sum(item['row_page_differs_from_display_page'] for item in bindings),
        'purchase_dates_are_not_publication_dates': True,
        'new_verified_publication_dates': 0, 'monthly_denominator_after_new_evidence': 0,
        'topic_names': topics, 'topic_label_source_kind': 'vendor_AI_summary_heading',
        'individual_review_topic_labels': None, 'PM_topic_approval': None, 'topic_numerators': None,
        'market_or_monthly_ratios': None, 'bindings': bindings,
        'structured_date_bindings': structured_bindings,
        'PDP_datePublished_semantics': 'ambiguous; nine values equal purchase dates; publication meaning not independently confirmed',
        'independent_Gold_or_product_model_input_approval': False,
        'new_product_model_calls': 0, 'new_OCR_calls': 0,
    }
    Path('/artifacts/observations.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print(json.dumps({key: report[key] for key in ('status', 'check_count', 'live_date_observations',
                      'fixed_ID_matches', 'new_UI_IDs_not_imported', 'review_row_page_mismatches')}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
