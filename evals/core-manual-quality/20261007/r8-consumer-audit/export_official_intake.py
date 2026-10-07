"""Actual X1 official-source exports only; no model or proposed concept."""
import hashlib
import json
from pathlib import Path

from lgax_core.guides import build_official_guide, render_guide_html, render_guide_markdown


def main():
    root = Path("data/research/r8-public-official-expansion-20261007/bundles")
    exports, checks = {}, []
    for group, model in (("microwave", "MW23FDI"), ("dishwasher", "DUE6BGL2E"), ("fridge", "T876MEE1H1")):
        path = root / f"{group}.development.research-bundle.json"
        raw = path.read_bytes()
        bundle = json.loads(raw)
        guide = build_official_guide(bundle, model)
        expected = [source for source in bundle["sources"]
                    if source["source_type"] == "manual" and source["source_role"] == "official_document"
                    and source["page_model"] == model]
        assert guide["sources"] == expected and expected
        assert guide["proposal"] is None
        assert guide["guide_kind"] == "official_excerpt"
        assert all(source["coverage"] == "excerpt" for source in expected)
        html, markdown = render_guide_html(guide), render_guide_markdown(guide)
        assert "<script" not in html.lower() and "<iframe" not in html.lower()
        assert "전체 정식 설명서를 대체하지" in html
        assert "runtime" not in guide
        faqs = [source for source in bundle["sources"] if source["source_type"] == "faq"]
        assert all(source["page_model"] is None for source in faqs)
        exports[model] = {"html": html, "markdown": markdown, "guide": guide}
        checks.append({"product_group": group, "page_model": model, "bundle_id": bundle["bundle_id"],
                       "bundle_sha256": hashlib.sha256(raw).hexdigest(),
                       "source_ids": [source["source_id"] for source in expected],
                       "manual_excerpt_count": len(expected), "facts_preserved": True,
                       "source_fields_preserved": True, "proposal": None,
                       "unconfirmed_model_faq_ids": [source["source_id"] for source in faqs],
                       "exact_model_faq_available": False,
                       "html_sha256": hashlib.sha256(html.encode()).hexdigest(),
                       "markdown_sha256": hashlib.sha256(markdown.encode()).hexdigest()})
    print(json.dumps({"audit": {
        "fixed_head": "e04f42b5de37b2d1cad606f2f06a3f7fe6a91f30",
        "kind": "actual_official_excerpt_export_intake", "models": checks,
        "actual_model_calls": 0, "generated_concepts": 0,
        "independent_semantic_quality_verified": False,
        "browser_and_print_visual_check": "pending",
        "limits": "Official excerpts only; FAQ model scope is unconfirmed. No invented instructions or full-manual claim."
    }, "exports": exports}, ensure_ascii=False))


if __name__ == "__main__":
    main()
