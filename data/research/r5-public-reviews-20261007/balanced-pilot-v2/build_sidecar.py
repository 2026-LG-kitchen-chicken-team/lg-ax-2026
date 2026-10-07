"""Offline research-only DOM sidecar. Run in the approved zero-auth guest only."""
import csv
import hashlib
import io
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

CAPTURE = Path('/workspace/captures')
OLD = Path('/workspace/v1')
OUT = Path('/artifacts/balanced-pilot-v2')
VERSION = 'lg-public-reviews.20261007.r5-balanced-pilot.v2-research-held'
SPLIT_VERSION = 'r5-public-new-group-split.20261007.v2'
PINS = {
    'records.json': '98830d3078d5c14443ee672a4fd6d5ae7fbafe6c77ea15ab6b14828ad2d5ad6f',
    'products.json': '5575df7a988d919eedc16a050914d192e30fc8eff1e0ad7b5a97c6328adb9d8b',
    'manifest.json': '3a35518787c1959d29dd11f6a651194f7b7a6be971e392a470cff3da240c895d',
}
PILOTS = {'T876MEE1H1': 'MD10758826', 'MW23FDI': 'MD10738847', 'DUE6BGL2E': 'MD10492836'}
CAPTURE_PIN = '028f27ec0862b910828799e279af4c8306ad2a1f4302cdd1d93ba59d15a2cf9e'
HASH_PIN = '95efe72f2c31d95827f9f35207a38402c64c39f6e8329f2721c60456124c3bba'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path, digest):
    raw = path.read_bytes()
    assert len(raw) < 2 * 1024 * 1024 and sha(raw) == digest
    return json.loads(raw)


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def normalize(text):
    return ' '.join(unicodedata.normalize('NFKC', text).split())


def redact(text):
    redactions = []
    # Public output excludes contacts even when the contact is a vendor number.
    for pattern, label in [(r'(?<!\d)(?:0\d{1,2}-\d{3,4}-\d{4}|1\d{3}-\d{4})(?!\d)', 'contact_number'),
                           (r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', 'email')]:
        if re.search(pattern, text):
            text = re.sub(pattern, '[연락처 생략]', text)
            redactions.append(label)
    vendor_match = re.search(r'LG 협력업체 ([^()<>\n]+)\(', text)
    if vendor_match:
        vendor = vendor_match.group(1).strip()
        assert vendor and len(vendor) <= 80
        text = text.replace(vendor, '[업체명 생략]')
        redactions.append('vendor_name')
    return text, sorted(set(redactions))


def intersections(rows, field):
    labels = ['development', 'independent_evaluation', 'demonstration']
    sets = {s: {r[field] for r in rows if r['split'] == s} for s in labels}
    return {a + '__' + b: sorted(sets[a] & sets[b]) for i, a in enumerate(labels) for b in labels[i + 1:]}


def main():
    OUT.mkdir(exist_ok=False)
    (OUT / 'snapshots').mkdir()
    old = load(OLD / 'records.json', PINS['records.json'])
    products = load(OLD / 'products.json', PINS['products.json'])
    old_manifest = load(OLD / 'manifest.json', PINS['manifest.json'])
    assert len(old) == 179 and old_manifest['version'] == 'lg-public-reviews.20261007.r5-fixed18.v1'
    original = {r['original_review_id']: r for r in old}
    assert len(original) == 179
    product_by_id = {p['model_id']: p for p in products}
    receipt = load(CAPTURE / 'capture-receipt.json', CAPTURE_PIN)
    hash_raw = (CAPTURE / 'browser-observed-hashes.tsv').read_bytes()
    assert sha(hash_raw) == HASH_PIN
    observed_hashes = {r['id']: r for r in csv.DictReader(io.StringIO(hash_raw.decode('utf-8')), delimiter='\t')}
    assert len(observed_hashes) == 60
    rows = []
    capture_proofs = []
    for name, digest in receipt['capture_files'].items():
        assert name in {'fridge-recent.json', 'fridge-low.json', 'mw-recent.json', 'mw-low.json', 'due-recent.json', 'due-low.json'}
        capture = load(CAPTURE / name, digest)
        sku = capture['displayed_sku']
        assert sku in PILOTS and capture['displayed_md'] == PILOTS[sku]
        assert capture['sort'] in {'recent', 'scoreAsc'} and len(capture['rows']) == 10
        assert capture['source_url'] == f'https://www.lge.co.kr/mkt/review/{PILOTS[sku]}/pdpReviewListPopup'
        safe_capture = {k: v for k, v in capture.items() if k != 'rows'}
        safe_capture['capture_kind'] = 'visible_DOM_observation_not_server_HTML_download'
        safe_capture['rows'] = []
        for raw in capture['rows']:
            ident = raw['id']
            assert ident.isdigit() and raw['md'].startswith('MD') and 1 <= raw['rank'] <= 10
            assert sha(raw['body'].encode()) == observed_hashes[ident]['body_sha256']
            assert sha(raw['fragment'].encode()) == observed_hashes[ident]['fragment_sha256']
            assert raw['fragment'].startswith('<p class="message">') and raw['fragment'].endswith('</p>')
            assert not re.search(r'<(?:script|img|iframe|video|a)\b', raw['fragment'], re.I)
            text, redactions = redact(raw['body'])
            fragment, fragment_redactions = redact(raw['fragment'])
            assert redactions == fragment_redactions
            purchase = re.search(r'\d{4}\.\d{2}\.\d{2}', raw['purchase']).group().replace('.', '-')
            rating = raw['rating'] if isinstance(raw['rating'], int) else int(re.search(r'중 (\d)점', raw['rating']).group(1))
            assert 1 <= rating <= 5
            flags = ['contact_or_vendor_redacted'] if redactions else []
            if raw['md'] != PILOTS[sku]:
                flags.append('review_row_MD_differs_from_displayed_page_MD')
            legacy = original.get(ident)
            lineage = None
            if legacy:
                equiv = normalize(raw['body']) == normalize(legacy['text'])
                lineage = {k: legacy[k] for k in ['review_id', 'source_url', 'source_sha256', 'text_sha256', 'original_text_sha256', 'dedup_group_id', 'split', 'split_version']}
                lineage['v1_records_path'] = 'data/research/r5-public-reviews-20261007/fixed18/records.json'
                lineage['v1_records_sha256'] = PINS['records.json']
                lineage['v1_row_index_zero_based'] = old.index(legacy)
                lineage['body_equivalence'] = 'whitespace_normalized_equal' if equiv else 'changed_body_hold'
                if not equiv:
                    flags.append('same_ID_body_changed_from_v1')
            row = {
                'original_review_id': ident, 'displayed_model_id': sku, 'displayed_page_MD': PILOTS[sku],
                'review_row_MD': raw['md'], 'actual_purchased_model_id': None,
                'sku_binding': 'official_product_review_page_only', 'text': text,
                'original_visible_text_sha256': observed_hashes[ident]['body_sha256'], 'text_sha256': sha(text.encode()),
                'original_message_DOM_fragment_sha256': observed_hashes[ident]['fragment_sha256'],
                'public_message_DOM_fragment_sha256': sha(fragment.encode()), 'redactions': redactions,
                'rating': rating, 'purchase_date': purchase, 'published_at': None,
                'date_basis': 'visible_purchase_date_is_not_publication_date', 'source_kind': 'public',
                'source_url': capture['source_url'], 'source_locator': f'#divReviewList > li[data-review-id="{ident}"] .message',
                'capture_kind': 'visible_DOM_observation_not_server_HTML_download',
                'sort': capture['sort'], 'screen_rank': raw['rank'], 'observed_at': capture['observed_at'],
                'DOM_snapshot_location': 'snapshots/' + name, 'private_capture_file_sha256': digest,
                'manual_version': product_by_id[sku]['manual_version'],
                'manual_time_alignment': 'current_reference_only_not_purchase_time_verified',
                'quality_flags': flags, 'eligible_for_model_input': False,
                'input_hold_reasons': ['purchased_sku_not_independently_verified', 'research_only_purposive_UI_sample'],
                'v1_lineage': lineage,
            }
            safe_capture['rows'].append({'id': ident, 'md': raw['md'], 'rank': raw['rank'], 'rating': rating, 'purchase_date': purchase, 'body': text, 'fragment': fragment, 'redactions': redactions})
            rows.append(row)
        dump('snapshots/' + name, safe_capture)
        capture_proofs.append({'file': 'snapshots/' + name, 'original_private_capture_sha256': digest,
                               'public_snapshot_sha256': sha((OUT / 'snapshots' / name).read_bytes()),
                               'observed_at': capture['observed_at'], 'source_url': capture['source_url'], 'sort': capture['sort'], 'rows': 10})
    assert len(rows) == 60 and len({r['original_review_id'] for r in rows}) == 60
    # Connect repeated IDs and every identical normalized body, regardless of date.
    # Preserve old assignments; conflicting old labels quarantine only the new component.
    all_ids = sorted(set(original) | {r['original_review_id'] for r in rows})
    parent = {i: i for i in all_ids}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        a, b = find(a), find(b)
        parent[max(a, b)] = min(a, b)

    bodies = {}
    for r in old + rows:
        ident = r['original_review_id']
        key = sha(normalize(r['text']).encode())
        if key in bodies:
            union(ident, bodies[key])
        bodies[key] = ident
    components = {}
    for ident in all_ids:
        components.setdefault(find(ident), []).append(ident)
    splits = {}
    conflicts = []
    for component, ids in components.items():
        old_labels = {original[i]['split'] for i in ids if i in original}
        if len(old_labels) > 1:
            conflicts.append({'IDs': ids, 'v1_splits': sorted(old_labels), 'resolution': 'v1_unchanged_new_rows_quarantined'})
            splits[component] = 'quarantine'
        elif old_labels:
            splits[component] = next(iter(old_labels))
        else:
            slot = int(sha((component + ':' + SPLIT_VERSION).encode())[:8], 16) % 100
            splits[component] = 'development' if slot < 60 else 'independent_evaluation' if slot < 80 else 'demonstration'
    for r in rows:
        ident = r['original_review_id']
        component = find(ident)
        r['body_group_id'] = 'LGE-R5-V2-BODYGROUP-' + component
        r['split'] = original[ident]['split'] if ident in original else splits[component]
        r['split_version'] = original[ident]['split_version'] if ident in original else SPLIT_VERSION
        if r['quality_flags'] and not r['v1_lineage']:
            r['split'] = 'quarantine'
        r['body_group_sha256'] = sha(normalize(r['text']).encode())
    new = [r for r in rows if not r['v1_lineage']]
    combined = [{'original_review_id': r['original_review_id'], 'split': r['split'], 'body_group_id': 'LGE-R5-V2-BODYGROUP-' + find(r['original_review_id']), 'body_group_sha256': sha(normalize(r['text']).encode())} for r in old] + new
    old_only = combined[:179]
    cross = {field: intersections(combined, field) for field in ['original_review_id', 'body_group_id', 'body_group_sha256']}
    old_cross = {field: intersections(old_only, field) for field in ['original_review_id', 'body_group_id', 'body_group_sha256']}
    # Never manufacture a global zero by altering v1. Distinguish any inherited conflicts.
    newly_introduced = {field: {pair: sorted(set(values) - set(old_cross[field][pair])) for pair, values in pairs.items()} for field, pairs in cross.items()}
    assert not any(values for pairs in newly_introduced.values() for values in pairs.values())
    dump('records.json', rows)
    dump('new_unique_records.json', new)
    dump('products.json', [product_by_id[s] for s in PILOTS])
    manifest = {
        'version': VERSION, 'purpose': 'research_only_contrasting_recent_and_low_rating_UI_sample',
        'collection': {'screen_rows': 60, 'unique_IDs_in_sidecar': len(rows), 'old_ID_overlap': len(rows) - len(new),
                       'new_unique_IDs': len(new), 'combined_unique_IDs': len(combined),
                       'sidecar_split_counts': dict(Counter(r['split'] for r in rows)),
                       'new_unique_split_counts': dict(Counter(r['split'] for r in new)),
                       'combined_split_counts': dict(Counter(r['split'] for r in combined)),
                       'rating_counts_by_sort': {s: dict(Counter(str(r['rating']) for r in rows if r['sort'] == s)) for s in ['recent', 'scoreAsc']}},
        'v1_input_hashes': PINS, 'private_capture_receipt_sha256': CAPTURE_PIN, 'browser_hash_receipt_sha256': HASH_PIN,
        'capture_proofs': capture_proofs, 'body_group_rule': 'all_NFKC_whitespace_normalized_identical_text_regardless_of_purchase_date',
        'split_intersections': cross, 'inherited_v1_intersections': old_cross,
        'newly_introduced_intersections': newly_introduced, 'inherited_v1_body_components_with_conflicting_splits': conflicts,
        'eligible_for_model_input': 0, 'verified_purchased_SKUs': 0, 'known_publication_dates': 0,
        'source_capture_kind': 'browser_visible_DOM_not_downloaded_server_HTML',
        'limitations': ['purposive_first_page_selection_not_population_representative', 'rating_is_not_sentiment',
                       'purchase_date_is_not_publication_date', 'displayed_page_and_review_MD_are_not_purchase_SKU_proof',
                       'current_manual_not_purchase_time_verified', 'no_model_evaluation_or_generation'],
        'privacy': {'author_names_photos_demographics_not_collected': True, 'redacted_IDs': [r['original_review_id'] for r in rows if r['redactions']], 'manual_body_read_rows': 60},
        'model_calls': 0, 'network_calls_during_build': 0,
    }
    dump('manifest.json', manifest)
    dump('files.json', {str(p.relative_to(OUT)).replace('\\', '/'): sha(p.read_bytes()) for p in sorted(OUT.rglob('*.json'))})
    print(json.dumps({'version': VERSION, 'rows': len(rows), 'new_unique': len(new), 'split_counts': manifest['collection'], 'intersections': cross, 'models': 0}))


if __name__ == '__main__':
    main()
