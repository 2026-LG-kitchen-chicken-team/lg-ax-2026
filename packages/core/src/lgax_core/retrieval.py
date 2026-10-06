"""Deterministic Korean BM25 development search, separate from the public method.

The current EvidenceSearchResponse pins literal_token_count. Its adapter below
keeps that response truthful. BM25 results expose their own internal method and
scores until PM adopts a public contract; original evidence text never changes.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

from lgax_contracts import CONTRACT_VERSION, validate

from .document_store import DocumentStore
from .errors import DomainError
from .evidence_catalog import EvidenceCatalog
from .store import DemoStore

TOKENIZER_VERSION = "nfc-casefold-words-hangul-bigrams.v1"


def _arguments(q, limit):
    if not isinstance(q, str) or not q.strip() or len(q) > 500:
        raise DomainError("INVALID_ARGUMENT", "검색어는 1~500자여야 합니다.", {"field": "q"})
    if type(limit) is not int or not 1 <= limit <= 50:
        raise DomainError("INVALID_ARGUMENT", "limit은 1~50의 정수여야 합니다.", {"field": "limit"})
    if not re.search(r"\w", q, re.UNICODE):
        raise DomainError("INVALID_ARGUMENT", "검색어에 문자 또는 숫자가 필요합니다.", {"field": "q"})


def tokenize(text):
    """Normalize the index only. Add Korean bigrams for deterministic particle recall."""
    words = re.findall(r"[^\W_]+", unicodedata.normalize("NFC", text).casefold())
    tokens = list(words)
    for word in words:
        for match in re.finditer(r"[가-힣]{2,}", word):
            run = match.group()
            tokens.extend("ko:" + run[index:index + 2] for index in range(len(run) - 1))
    return tokens


def bm25_search(catalog, q, *, model_id=None, document_version=None, dataset_version=None,
                source_kind=None, limit=10, k1=1.2, b=0.75):
    _arguments(q, limit)
    if (isinstance(k1, bool) or isinstance(b, bool) or not isinstance(k1, (int, float))
            or not isinstance(b, (int, float)) or not math.isfinite(k1) or not math.isfinite(b)
            or k1 <= 0 or not 0 <= b <= 1):
        raise DomainError("INVALID_ARGUMENT", "BM25 설정 범위를 확인해 주세요.", {})
    # Apply scope BEFORE document frequencies and average length, not after ranking.
    scope = {"model_id": model_id, "document_version": document_version,
             "dataset_version": dataset_version, "source_kind": source_kind}
    documents = catalog.select(**scope)
    query_terms = sorted(set(tokenize(q)))
    if not query_terms:
        raise DomainError("INVALID_ARGUMENT", "검색 가능한 문자가 필요합니다.", {})
    counts = [Counter(tokenize(item["text"])) for item in documents]
    lengths = [sum(count.values()) for count in counts]
    average = sum(lengths) / len(lengths) if lengths else 0
    frequencies = {term: sum(term in count for count in counts) for term in query_terms}
    matches = []
    for item, count, length in zip(documents, counts, lengths):
        score = 0.0
        for term in query_terms:
            frequency = count[term]
            if frequency:
                inverse = math.log1p((len(documents) - frequencies[term] + 0.5) / (frequencies[term] + 0.5))
                score += inverse * frequency * (k1 + 1) / (
                    frequency + k1 * (1 - b + b * length / average))
        if score > 0:
            matches.append({"evidence": item, "score": score})
    matches.sort(key=lambda match: (-match["score"], match["evidence"]["id"]))
    return {"query": q, "filters": scope, "items": matches[:limit], "total": len(matches),
            "corpus_size": len(documents), "search_method": "bm25", "tokenizer_version": TOKENIZER_VERSION,
            "parameters": {"k1": k1, "b": b}, "contract_version": CONTRACT_VERSION}


def canonical_search(catalog, q, model_id=None, document_version=None, limit=10):
    _arguments(q, limit)
    tokens = re.findall(r"[\w]+", q.casefold())
    matches = []
    for item in catalog.select(model_id=model_id, document_version=document_version):
        score = sum(item["text"].casefold().count(token) for token in tokens)
        if score:
            matches.append((score, item["id"], item))
    matches.sort(key=lambda match: (-match[0], match[1]))
    result = {"ok": True, "data": {"query": q, "model_id": model_id, "document_version": document_version,
              "items": [item for _, _, item in matches[:limit]], "total": len(matches),
              "contract_version": CONTRACT_VERSION, "search_method": "literal_token_count"}}
    validate("EvidenceSearchResponse", result)
    return result


class _CatalogReads:
    def bootstrap(self):
        self.catalog.select()  # Re-check retained originals before a new workspace snapshot.
        return super().bootstrap()

    def get_evidence(self, evidence_id):
        result = {"ok": True, "data": {"evidence": self.catalog.get_evidence(evidence_id),
                                      "contract_version": CONTRACT_VERSION}}
        validate("EvidenceResponse", result)
        return result

    def search_evidence(self, q, model_id=None, document_version=None, limit=10):
        return canonical_search(self.catalog, q, model_id, document_version, limit)

    def search_ranked_evidence(self, q, **kwargs):
        return bm25_search(self.catalog, q, **kwargs)


class GroundedDocumentStore(_CatalogReads, DocumentStore):
    def __init__(self, dataset, *, sources=None, source_reader=None):
        super().__init__(dataset)
        self.catalog = EvidenceCatalog([dataset], sources=sources, source_reader=source_reader)


class GroundedDemoStore(_CatalogReads, DemoStore):
    def __init__(self, dataset):
        super().__init__(dataset)
        self.catalog = EvidenceCatalog([dataset])
