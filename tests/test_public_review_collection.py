import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from lgax_core.public_review_collection import group_and_split, parse_public_review_html, save_landing_db, verify_public_product_page


class PublicReviewCollectionTests(unittest.TestCase):
    def parse(self, body, *, group='dishwasher', ident='123', model='MD12345678', extra=''):
        raw = ('<html><ul id="divReviewList"><li data-review-id="' + ident
               + '" data-model-id="' + model + '"><span class="user-name">비공개 대상 이름</span>'
               + '<span class="purchase-date"><em>구매 일자</em>2025.10.03</span>'
               + '<span class="star-wrap">리뷰 별점 5점 중 5점</span><p class="message">'
               + body + '</p>' + extra + '</li></ul></html>').encode()
        product = {'model_id': 'DUE6BGL2E', 'lge_model_id': 'MD12345678', 'product_group': group,
                   'source_kind': 'public', 'document_version': 'manual.v1', 'manual_version': 'manual.v1'}
        source = {'sha256': hashlib.sha256(raw).hexdigest(), 'source_url': 'https://www.lge.co.kr/normal',
                  'captured_at': '2026-10-07T01:00:00+00:00'}
        return parse_public_review_html(raw, product=product, source=source)[0]

    def test_purchase_date_never_becomes_publication_date_or_exact_sku(self):
        row = self.parse('식기세척기 편리합니다.<br>만족합니다.')
        self.assertEqual(row['text'], '식기세척기 편리합니다.\n만족합니다.')
        self.assertEqual(row['purchase_date'], '2025-10-03')
        self.assertIsNone(row['published_at'])
        self.assertIsNone(row['actual_purchased_model_id'])
        self.assertEqual(row['sku_binding'], 'official_product_review_page_only')
        self.assertNotIn('비공개 대상 이름', json.dumps(row, ensure_ascii=False))
        self.assertEqual(row['rating'], 5)

    def test_category_confusion_and_contact_details_are_quarantined(self):
        other = self.parse('하이라이트 쓰다가 화력이 좋아졌어요')
        self.assertFalse(other['eligible_for_model_input'])
        contact = self.parse('식세기 좋아요. 연락처 010-1234-5678 someone@example.com')
        self.assertNotIn('010-1234-5678', contact['text'])
        self.assertNotIn('someone@example.com', contact['text'])
        self.assertFalse(contact['eligible_for_model_input'])
        self.assertEqual(group_and_split([other, contact | {'original_review_id': '124'}])[1]['split_counts']['quarantine'], 2)

    def test_global_shared_review_dedup_precedes_split(self):
        row = self.parse('식기세척기 만족합니다')
        other = row | {'displayed_model_id': 'DFE5BGE'}
        result, summary = group_and_split([row, other])
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]['page_associations']), 2)
        self.assertEqual(summary['unique_original_ids'], 1)
        self.assertEqual(summary['captured_page_rows'], 2)
        self.assertEqual(group_and_split([other, row])[0][0]['split'], result[0]['split'])

    def test_reposted_long_text_stays_in_same_group_but_short_praise_is_not_collapsed(self):
        text = '식기세척기 사용 후 설거지 시간이 줄고 큰 냄비를 적재하는 방법을 익혀 편리하게 사용하고 있습니다.'
        a = self.parse(text, ident='100')
        b = self.parse(text, ident='101')
        result, _ = group_and_split([a, b])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['dedup_group_id'], result[1]['dedup_group_id'])
        self.assertEqual(result[0]['split'], result[1]['split'])
        a = self.parse('좋아요', ident='102')
        b = self.parse('좋아요', ident='103')
        result, _ = group_and_split([a, b])
        self.assertNotEqual(result[0]['dedup_group_id'], result[1]['dedup_group_id'])

    def test_conflicting_original_id_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'conflicting text'):
            group_and_split([self.parse('식세기 좋아요'), self.parse('식세기 불편해요')])

    def test_later_shared_page_quality_flag_cannot_be_lost(self):
        first = self.parse('식기세척기 만족합니다')
        later = first | {'quality_flags': ['review_list_model_differs'], 'quarantined': True}
        for rows in ([first, later], [later, first]):
            result, summary = group_and_split(rows)
            self.assertEqual(result[0]['split'], 'quarantine')
            self.assertEqual(result[0]['quality_flags'], ['review_list_model_differs'])
            self.assertEqual(summary['group_intersection_count'], 0)

    def test_product_page_identity_is_checked_and_not_purchased_identity(self):
        raw = ('<title>LG 식기세척기 | DUE6BGL2E | 식기세척기</title>'
               '<link rel="canonical" href="https://www.lge.co.kr/product/dishwashers/due6bgl2e">').encode()
        product = {'model_id': 'DUE6BGL2E', 'lge_model_id': 'MD10492836',
                   'category': 'dishwashers', 'product_group': 'dishwasher'}
        source = {'sha256': hashlib.sha256(raw).hexdigest(),
                  'source_url': 'https://www.lge.co.kr/product/dishwashers/due6bgl2e?modelId=MD10492836&pdpType=PURCHASE'}
        result = verify_public_product_page(raw, product=product, source=source)
        self.assertNotIn('actual_purchased_model_id', result)
        for wrong in (product | {'model_id': 'DFE5BGE'}, product | {'lge_model_id': 'MD00000000'},
                      product | {'product_group': 'microwave'}):
            with self.assertRaisesRegex(ValueError, 'identity mismatch'):
                verify_public_product_page(raw, product=wrong, source=source)

    def test_html_scripts_are_not_review_text(self):
        row = self.parse('식세기<script>stealCredential()</script> 좋아요')
        self.assertEqual(row['text'], '식세기 좋아요')

    def test_fresh_db_roundtrip_and_no_overwrite(self):
        rows, summary = group_and_split([self.parse('식세기 편리해요')])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'reviews.sqlite3'
            save_landing_db(path, records=rows, products=[{'model_id': 'DUE6BGL2E'}], manifest=summary)
            with sqlite3.connect(path) as db:
                saved = json.loads(db.execute('SELECT metadata_json FROM reviews').fetchone()[0])
                self.assertEqual(saved, rows[0])
                self.assertIsNone(db.execute('SELECT published_at FROM reviews').fetchone()[0])
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            with self.assertRaisesRegex(ValueError, 'already exists'):
                save_landing_db(path, records=rows, products=[], manifest={})


if __name__ == '__main__':
    unittest.main()
