"""Build a narrow, source-pinned research comparison; no network/model calls."""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unicodedata

VERSION = "official-html-excerpts.1"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


class VisibleText(HTMLParser):
    """Read text and declared image alt; never evaluate script/style contents."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.pieces = []

    def path(self, extra=None):
        parts = [item[1] for item in self.stack]
        if extra:
            parts.append(extra)
        return "/" + "/".join(parts)

    def hidden(self):
        return any(tag in {"script", "style"} for tag, _ in self.stack)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        label = tag
        if attrs.get("id"):
            label += "#" + attrs["id"]
        if tag not in VOID:
            self.stack.append((tag, label))
        if not self.hidden() and tag == "img" and attrs.get("alt"):
            self.pieces.append((normalized(attrs["alt"]), self.path(label) + "/@alt", "image_alt"))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if not self.hidden() and normalized(data):
            self.pieces.append((normalized(data), self.path(), "html_text"))

    def finish(self):
        text = ""
        pieces = []
        for value, path, kind in self.pieces:
            if text:
                text += " "
            start = len(text)
            text += value
            pieces.append({"start": start, "end": len(text), "path": path, "kind": kind})
        return text, pieces


QUOTES = {
    "lg-t876-product": [
        ("LG-CAP", "전체 용량 (L) 870"),
        ("LG-DIMS", "914 x 1,787 x 918"),
        ("LG-INSTALL", "설치타입 프리스탠딩"),
        ("LG-LAUNCH", "동일모델의 출시년월 2026-04"),
        ("LG-FOLD", "접이선반"),
    ],
    "samsung-rm70-spec": [
        ("SS-CAP", "640 ℓ"),
        ("SS-DIMS", "후면핸들 포함 : 912 × 1,853 × 697 mm / 후면핸들 미포함 : 912 × 1,853 × 683 mm"),
        ("SS-INSTALL", "키친핏 Max"),
        ("SS-FOLD", "개수(접이선반) 1개"),
    ],
    "samsung-rm70-product": [
        ("SS-GAP", "좌, 우 단 4mm의 공간만"),
        ("SS-COUNTER", "싱크대 깊이 700mm 기준입니다."),
        ("SS-ILLUSTRATION", "이해를 돕기 위해 연출된 영상으로 실제와 다를 수 있습니다."),
    ],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    metadata = json.loads((args.inputs / "capture-metadata.json").read_text(encoding="utf-8-sig"))
    results = []
    for record in metadata:
        sid = record["id"]
        raw = (args.inputs / (sid + ".html")).read_bytes()
        assert record["status"] == 200
        assert sha(raw) == record["sha256"] and len(raw) == record["bytes"]
        reader = VisibleText()
        reader.feed(raw.decode("utf-8"))
        text, pieces = reader.finish()
        expected_model = "T876MEE1H1" if sid.startswith("lg-") else "RM70F63R231"
        assert expected_model in text, (sid, "model binding")
        excerpts = []
        for eid, quote in QUOTES[sid]:
            start = text.find(quote)
            assert start >= 0, (sid, eid, "quote missing")
            end = start + len(quote)
            loci = [p for p in pieces if p["start"] < end and p["end"] > start]
            excerpts.append({
                "id": eid, "text": quote, "text_sha256": sha(quote.encode()),
                "normalized_text_range": [start, end],
                "location_basis": "NFC whitespace-normalized HTML text plus declared image alt, not raw HTML offsets",
                "locators": loci,
            })
        assert sum(len(e["text"].split()) for e in excerpts) <= 25, (sid, "quotation budget")
        results.append({
            "id": sid, "model_id": expected_model,
            "publisher": "LG Electronics" if sid.startswith("lg-") else "Samsung Electronics",
            "requested_url": record["requested_url"], "final_url": record["final_url"],
            "captured_at": record["captured_at"], "http_status": record["status"],
            "source_sha256": sha(raw), "source_bytes": len(raw),
            "normalized_text_sha256": sha(text.encode()),
            "capture_version": "html-sha256:" + sha(raw),
            "extractor": VERSION, "excerpts": excerpts,
            "raw_source_storage": "private scratch; raw HTML, cookies, account data and review author data are not committed",
        })
    payload = {
        "schema_version": "d3-official-source-excerpts.1",
        "scope": "research sidecar, not an approved ResearchBundle or canonical Evidence import",
        "sources": results,
        "verification": {"sources": len(results), "excerpts": sum(len(r["excerpts"]) for r in results),
                         "http_sources_sha_matched": True, "all_excerpts_reproduced": True,
                         "network_requests_in_build": 0, "model_calls": 0},
        "builder_sha256": sha(Path(__file__).read_bytes()),
    }
    (args.output / "official-sources.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["verification"]))


if __name__ == "__main__":
    main()
