"""Synthetic text/extraction fixtures; not real customers or PDF/OCR validation."""

import hashlib
import unittest
from copy import deepcopy

from lgax_core.errors import DomainError
from lgax_core.source_ranges import capture_source, verify_source_range


def sha(data):
    return hashlib.sha256(data).hexdigest()


class SourceRangeTests(unittest.TestCase):
    def setUp(self):
        self.text = "합성 제목\n\n첫째 문단\n한글, 인용문\n\n마지막 문단\n"
        self.raw = self.text.encode("utf-8")
        self.kwargs = dict(document_id="SYNTH-DOC", model_id="SYNTH-M1",
                           document_version="fixture-v1", source_kind="synthetic")
        self.source = capture_source(self.raw, **self.kwargs)
        quote = "첫째 문단\n한글, 인용문"
        start = self.text.index(quote)
        self.evidence = {"id": "SYNTH-E1", "source_id": "SYNTH-DOC", "model_id": "SYNTH-M1",
                         "document_version": "fixture-v1", "source_kind": "synthetic",
                         "source_type": "manual", "locator": {"page": 1, "row": 3},
                         "text": quote, "feature_ids": []}
        self.origin = {"evidence_id": "SYNTH-E1", "page": 1, "sha256": sha(self.raw),
                       "text_sha256": sha(quote.encode()), "document_version": "fixture-v1",
                       "start_char": start, "end_char": start + len(quote), "end_row": 4,
                       "paragraph_start": 2, "paragraph_end": 2}

    def verify(self, **kwargs):
        return verify_source_range(self.source, self.evidence, self.origin,
                                   current_original=kwargs.get("raw", self.raw))

    def fails(self, code, **kwargs):
        with self.assertRaises(DomainError) as caught:
            self.verify(**kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_public_api_exact_korean_multiline_line_and_paragraph(self):
        result = self.verify()
        self.assertTrue(result["verified"])
        self.assertEqual(result["sha256"], sha(self.raw))
        self.assertEqual(result["text_basis"], "utf8_original")
        self.assertFalse(result["pdf_or_ocr_verified"])
        result["start_char"] = 0
        self.assertEqual(self.verify()["start_char"], self.text.index("첫째"))

    def test_missing_changed_original_and_wrong_origin_hash_are_distinct(self):
        self.fails("SOURCE_MISSING", raw=None)
        self.fails("SOURCE_CHANGED", raw=self.raw + b" ")
        self.origin["sha256"] = "0" * 64
        self.fails("SOURCE_MISMATCH")

    def test_identical_bytes_different_document_version_rejected(self):
        self.evidence["document_version"] = "fixture-v2"
        self.fails("VERSION_MISMATCH")
        self.evidence["document_version"] = "fixture-v1"
        self.origin["document_version"] = "fixture-v2"
        self.fails("VERSION_MISMATCH")

    def test_wrong_identity_kind_and_text_hash(self):
        for field, value in (("source_id", "OTHER"), ("model_id", "OTHER"), ("source_kind", "public")):
            old = self.evidence[field]
            self.evidence[field] = value
            self.fails("SOURCE_MISMATCH")
            self.evidence[field] = old
        self.origin["text_sha256"] = "0" * 64
        self.fails("TEXT_HASH_MISMATCH")

    def test_quote_must_be_at_selected_location_not_elsewhere(self):
        self.evidence["locator"] = {"page": 1}
        for key in ("end_row", "paragraph_start", "paragraph_end"):
            self.origin.pop(key)
        self.origin["start_char"] = 0
        self.origin["end_char"] = len(self.evidence["text"])
        self.fails("QUOTE_MISMATCH")
        self.evidence["text"] = "존재하지 않는 인용"
        self.origin["text_sha256"] = sha(self.evidence["text"].encode())
        self.origin["end_char"] = len(self.evidence["text"])
        self.fails("QUOTE_MISMATCH")

    def test_out_of_range_reversed_boolean_and_wrong_line_paragraph(self):
        for field, value in (("page", 2), ("start_char", -1), ("start_char", True),
                             ("end_char", len(self.text) + 1), ("end_char", 1),
                             ("end_row", 3), ("end_row", 99),
                             ("paragraph_start", 1), ("paragraph_end", 3)):
            with self.subTest(field=field, value=value):
                original = deepcopy(self.origin)
                self.origin[field] = value
                self.fails("INVALID_LOCATOR")
                self.origin = original
        self.evidence["locator"]["row"] = 2
        self.fails("INVALID_LOCATOR")

    def test_documents_origin_format_page_character_offsets(self):
        # Same origin keys as documents.py; no invented section lookup.
        self.evidence["locator"] = {"page": 1, "section": "합성절"}
        self.origin = {k: v for k, v in self.origin.items()
                       if k not in ("end_row", "paragraph_start", "paragraph_end")}
        sections = {"합성절": [1, self.origin["start_char"], self.origin["end_char"]]}
        pages = [self.text]
        raw = bytearray(b"synthetic-binary-not-a-PDF")
        source = capture_source(raw, pages=pages, sections=sections, **self.kwargs)
        self.origin["sha256"] = sha(raw)
        expected_raw = bytes(raw)
        pages[0] = "changed"
        sections["합성절"][1] = 0
        raw[:] = b"changed"
        result = verify_source_range(source, self.evidence, self.origin, current_original=expected_raw)
        self.assertEqual(result["text_basis"], "caller_supplied_extraction")
        self.assertFalse(result["pdf_or_ocr_verified"])
        self.evidence["locator"]["section"] = "unknown"
        with self.assertRaises(DomainError) as caught:
            verify_source_range(source, self.evidence, self.origin, current_original=expected_raw)
        self.assertEqual(caught.exception.code, "INVALID_LOCATOR")

    def test_exact_bom_crlf_and_page_selection_no_fuzzy_normalization(self):
        raw = b"\xef\xbb\xbf" + "앞 페이지\f한글\r\n둘째줄".encode()
        source = capture_source(raw, **self.kwargs)
        evidence = {**self.evidence, "text": "한글\r\n둘째줄", "locator": {"page": 2, "row": 1}}
        origin = {"evidence_id": evidence["id"], "sha256": sha(raw), "document_version": "fixture-v1",
                  "text_sha256": sha(evidence["text"].encode()), "page": 2,
                  "start_char": 0, "end_char": len(evidence["text"]), "end_row": 2}
        self.assertTrue(verify_source_range(source, evidence, origin, current_original=raw)["verified"])
        evidence["text"] = evidence["text"].replace("\r\n", "\n")
        origin["text_sha256"] = sha(evidence["text"].encode())
        with self.assertRaises(DomainError) as caught:
            verify_source_range(source, evidence, origin, current_original=raw)
        self.assertEqual(caught.exception.code, "QUOTE_MISMATCH")

    def test_missing_origin_and_unsupported_section_are_failures(self):
        self.origin.pop("sha256")
        self.fails("INVALID_ORIGIN")
        self.setUp()
        self.evidence["locator"]["section"] = "not registered"
        self.fails("INVALID_LOCATOR")

    def test_capture_rejects_invalid_encoding_and_section_bounds(self):
        with self.assertRaises(DomainError) as caught:
            capture_source(b"\xff", **self.kwargs)
        self.assertEqual(caught.exception.code, "INVALID_ENCODING")
        with self.assertRaises(DomainError) as caught:
            capture_source(self.raw, sections={"bad": (1, 0, 9999)}, **self.kwargs)
        self.assertEqual(caught.exception.code, "INVALID_LOCATOR")


if __name__ == "__main__":
    unittest.main()
