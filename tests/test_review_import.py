"""Synthetic fixtures only; examples for the new-review public API."""

import csv
import hashlib
import io
import unittest
from copy import deepcopy

from lgax_contracts import validate
from lgax_core.errors import DomainError
from lgax_core.review_csv import FIELDS
from lgax_core.review_import import import_review_csv


class ReviewImportTests(unittest.TestCase):
    def setUp(self):
        self.products = [{"model_id": "SYNTH-M1", "name": "합성 냉장고",
                          "product_group": "fridge", "document_version": "fixture-v1",
                          "source_kind": "synthetic"}]
        self.sources = [{"document_id": "SYNTH-CSV", "product": deepcopy(self.products[0]),
                         "document_version": "fixture-v1", "source_kind": "synthetic"}]

    def row(self, **changes):
        row = {"id": "NEW-R1", "model_id": "SYNTH-M1", "text": "새 합성 리뷰",
               "source_kind": "synthetic", "document_version": "fixture-v1",
               "source_id": "SYNTH-CSV", "row": "2", "evidence_id": "NEW-E1"}
        row.update(changes)
        return row

    def csv(self, rows, *, bom=False, newline="\n"):
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator=newline)
        writer.writeheader()
        writer.writerows(rows)
        return (b"\xef\xbb\xbf" if bom else b"") + stream.getvalue().encode("utf-8")

    def parse(self, data, **kwargs):
        return import_review_csv(data, products=self.products, sources=self.sources,
                                 dataset_version="synthetic-import-v1", **kwargs)

    def fails(self, code, data, **kwargs):
        with self.assertRaises(DomainError) as caught:
            self.parse(data, **kwargs)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_public_api_new_content_contracts_and_exact_multiline_origins(self):
        for newline in ("\n", "\r\n", "\r"):
            for bom in (False, True):
                with self.subTest(newline=newline, bom=bom):
                    text = '한글, "따옴표"' + newline + '=SUM(1,2); $(명령은 데이터)'
                    raw = self.csv([self.row(text=text), self.row(id="NEW-R2", evidence_id="NEW-E2", row="4")],
                                   bom=bom, newline=newline)
                    result = self.parse(raw)
                    self.assertEqual(result.original, raw)
                    self.assertEqual(result.sha256, hashlib.sha256(raw).hexdigest())
                    self.assertEqual(result.dataset["reviews"][0]["text"], text)
                    self.assertEqual(result.dataset["reviews"][1]["locator"], {"row": 4})
                    self.assertEqual([(o["row"], o["end_row"]) for o in result.origins], [(2, 3), (4, 4)])
                    for definition, collection in (("Product", "products"), ("Review", "reviews"), ("Evidence", "evidence")):
                        for item in result.dataset[collection]:
                            validate(definition, item)
                    self.assertEqual(result.store().get_evidence("NEW-E1")["data"]["evidence"]["text"], text)

    def test_inputs_and_returned_trees_cannot_poison_snapshot_or_store(self):
        raw = bytearray(self.csv([self.row()]))
        result = self.parse(raw)
        before = result.dataset
        store = result.store()
        raw[:] = b"changed"
        self.products[0]["name"] = "changed"
        self.sources[0]["product"]["model_id"] = "changed"
        result.dataset["reviews"][0]["locator"]["row"] = 900
        result.origins[0]["sha256"] = "changed"
        view = store.bootstrap()
        view["data"]["evidence"][0]["text"] = "changed"
        self.assertEqual(result.dataset, before)
        self.assertEqual(result.origins[0]["sha256"], result.sha256)
        self.assertEqual(store.get_evidence("NEW-E1")["data"]["evidence"]["text"], "새 합성 리뷰")

    def test_content_is_not_restricted_to_existing_36(self):
        first = self.parse(self.csv([self.row(text="첫 입력")]))
        second = self.parse(self.csv([self.row(text="다른 새 입력")]))
        self.assertNotEqual(first.sha256, second.sha256)
        self.assertNotEqual(first.dataset["reviews"], second.dataset["reviews"])

    def test_unapproved_scope_and_invalid_fields_are_distinct(self):
        for changes, code in [({"model_id": "OTHER"}, "UNAPPROVED_MODEL"),
                              ({"source_id": "MISSING"}, "UNKNOWN_SOURCE"),
                              ({"document_version": "fixture-v2"}, "SOURCE_MISMATCH"),
                              ({"source_kind": "public"}, "SOURCE_MISMATCH"),
                              ({"source_kind": "invented"}, "INVALID_FIELD"),
                              ({"text": " \n "}, "INVALID_FIELD"),
                              ({"id": "bad id"}, "INVALID_FIELD"),
                              ({"id": " NEW-R1"}, "INVALID_FIELD"),
                              ({"row": "3"}, "INVALID_LOCATOR"),
                              ({"row": "2.0"}, "INVALID_LOCATOR")]:
            with self.subTest(changes=changes):
                self.fails(code, self.csv([self.row(**changes)]))

    def test_duplicate_review_or_evidence_and_preexisting_ids(self):
        for changes in ({"id": "NEW-R1", "evidence_id": "NEW-E2"},
                        {"id": "NEW-R2", "evidence_id": "NEW-E1"}):
            self.fails("DUPLICATE_ID", self.csv([self.row(), self.row(row="3", **changes)]))
        self.fails("DUPLICATE_ID", self.csv([self.row()]), existing_review_ids=["NEW-R1"])
        self.fails("DUPLICATE_ID", self.csv([self.row()]), existing_evidence_ids=["NEW-E1"])

    def test_encoding_header_columns_and_malformed_quotes(self):
        header = (",".join(FIELDS) + "\n").encode()
        for raw, code in [(b"", "INVALID_DOCUMENT"), (header + b"\xff", "INVALID_ENCODING"),
                          (self.csv([self.row()]).decode().encode("utf-16"), "INVALID_ENCODING"),
                          (b"id,id\n", "INVALID_HEADER"), (header, "EMPTY_REVIEWS"),
                          (header + b"\n", "INVALID_FIELD"),
                          (header + b"one,two\n", "INVALID_FIELD"),
                          (header + b'"unterminated', "PARSING_FAILED"),
                          (self.csv([self.row(text="a\x00b")]), "INVALID_FIELD"),
                          (self.csv([self.row()]).rstrip(b"\n") + b",extra\n", "INVALID_FIELD")]:
            with self.subTest(code=code, raw=raw[:30]):
                self.fails(code, raw)

    def test_physical_not_logical_row_and_atomic_failure(self):
        raw = self.csv([self.row(text="첫줄\n둘째줄"), self.row(id="R2", evidence_id="E2", row="3")])
        error = self.fails("INVALID_LOCATOR", raw)
        self.assertEqual(error.details["row"], 4)
        self.assertEqual(len(self.products), 1)
        self.assertNotIn("reviews", self.sources[0])

    def test_exact_size_row_limits_and_optional_source_hash_pin(self):
        raw = self.csv([self.row()])
        self.parse(raw, max_bytes=len(raw), max_rows=1)
        self.fails("SIZE_LIMIT_EXCEEDED", raw, max_bytes=len(raw) - 1)
        self.fails("ROW_LIMIT_EXCEEDED", self.csv([self.row(), self.row(id="R2", evidence_id="E2", row="3")]), max_rows=1)
        self.fails("INVALID_ARGUMENT", raw, max_rows=True)
        self.sources[0]["sha256"] = hashlib.sha256(raw).hexdigest()
        self.parse(raw)
        self.fails("SOURCE_MISMATCH", self.csv([self.row(text="changed")]))

    def test_approval_metadata_is_validated(self):
        self.sources[0]["document_version"] = "other"
        self.fails("INVALID_APPROVAL", self.csv([self.row()]))


if __name__ == "__main__":
    unittest.main()
