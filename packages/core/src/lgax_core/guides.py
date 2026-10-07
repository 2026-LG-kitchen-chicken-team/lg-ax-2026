"""Model-free exports: official manual excerpts and separate concept drafts."""
from __future__ import annotations

import html
import json
import re
from copy import deepcopy
from urllib.parse import quote, urlparse

from lgax_contracts.research import validate_planning_brief, validate_research_bundle

_OFFICIAL_DOMAINS = {"lge.com", "lge.co.kr", "samsung.com", "samsungsvc.co.kr"}
_SOURCE_TYPES = {"manual": "공식 설명서", "review": "고객 후기", "qa": "공개 Q&A", "faq": "공식 FAQ",
                 "spec": "제품 사양", "installation": "설치 안내"}
_COVERAGE = {"excerpt": "일부 발췌", "full": "원자료 전체", "unknown": "범위 미확인"}


def _official_manual(source: dict, page_model: str) -> bool:
    host = urlparse(source["url"]).hostname or ""
    return (source["source_kind"] == "public" and source["source_type"] == "manual"
            and source["source_role"] == "official_document" and source["page_model"] == page_model
            and any(host == domain or host.endswith("." + domain) for domain in _OFFICIAL_DOMAINS))


def build_official_guide(bundle: dict, page_model: str) -> dict:
    """Copy only the selected model's official manual sources; generate no device settings."""
    validate_research_bundle(bundle)
    if not isinstance(page_model, str) or not page_model.strip():
        raise ValueError("A confirmed page model is required")
    selected = [deepcopy(source) for source in bundle["sources"] if _official_manual(source, page_model)]
    if not selected:
        raise ValueError("No verified official manual source for this page model")
    return {"guide_version": "1.0", "guide_kind": "official_excerpt", "bundle_id": bundle["bundle_id"],
            "page_model": page_model, "title": f"{page_model} 공식 설명서 발췌 안내",
            "notice": "선택한 모델의 공식 원문을 모은 발췌 안내입니다. 전체 정식 설명서를 대체하지 않습니다. "
                      "새 조리 수치나 사용 절차를 생성하지 않았으며, 정확한 원문 범위와 문서판은 각 출처에서 확인하세요.",
            "sources": selected, "proposal": None}


def build_concept_guide(bundle: dict, brief: dict, concept_id: str) -> dict:
    """Assemble an unapproved proposed-product guide, keeping sources separate from proposals."""
    validate_research_bundle(bundle)
    validate_planning_brief(brief)
    expected_facts = [{"source_id": source["source_id"], "facts": source["facts"]} for source in bundle["sources"]]
    if (brief["bundle_id"] != bundle["bundle_id"] or brief["product_group"] != bundle["product_group"]
            or brief["analysis_scope"] != bundle["analysis_scope"] or brief["source_facts"] != expected_facts):
        raise ValueError("Concept brief and actual source snapshot differ")
    candidates = [concept for concept in brief["concepts"] if concept["id"] == concept_id]
    if len(candidates) != 1:
        raise ValueError("A unique existing concept is required; no placeholder concept is generated")
    concept = candidates[0]
    problems = [problem for problem in brief["problems"] if problem["id"] in concept["problem_ids"]]
    if {problem["id"] for problem in problems} != set(concept["problem_ids"]):
        raise ValueError("Concept references an unknown problem")
    cited = set(concept["source_ids"])
    for problem in problems:
        cited.update(problem["source_ids"])
        cited.update(problem["counter_source_ids"])
    if not cited <= {source["source_id"] for source in bundle["sources"]}:
        raise ValueError("Concept references an unknown actual source")
    return {"guide_version": "1.0", "guide_kind": "concept_draft", "bundle_id": bundle["bundle_id"],
            "brief_id": brief["brief_id"], "run_id": brief["run_id"], "revision": brief["revision"],
            "brief_status": brief["status"], "title": f"{concept['title']} · 가상 제품 기획 설명서",
            "notice": "새 콘셉트의 가상 제품 기획 설명서 초안입니다. 개선 후 과정과 장면은 제안이며, "
                      "실제 탑재 기능이나 검증된 사용법으로 확정하지 않습니다. 실제 근거 원문은 별도 영역에 보존합니다.",
            "sources": [deepcopy(source) for source in bundle["sources"] if source["source_id"] in cited],
            "proposal": deepcopy(concept), "problem_hypotheses": deepcopy(problems),
            "uncertainties": deepcopy(brief["uncertainties"]), "independent_quality_verified": False}


def _escape(value) -> str:
    return html.escape(str(value), quote=True)


def _markdown(value) -> str:
    return re.sub(r"([\\`*_{}\[\]#+!|])", r"\\\1", _escape(value))


def _kind(guide: dict) -> str:
    if guide["guide_kind"] not in {"official_excerpt", "concept_draft"}:
        raise ValueError("Unknown guide kind")
    return "공식 원문 발췌 안내" if guide["guide_kind"] == "official_excerpt" else "가상 제품 기획 설명서 · 초안"


def _list_html(values: list) -> str:
    return "<ul>" + "".join(f"<li>{_escape(value)}</li>" for value in values) + "</ul>"


def render_guide_html(guide: dict) -> str:
    """Self-contained HTML; every external string is escaped, with no scripts or remote assets."""
    kind = _kind(guide)
    sections = []
    proposal = guide.get("proposal")
    if guide["guide_kind"] == "concept_draft":
        if not isinstance(proposal, dict):
            raise ValueError("Concept guide requires an existing proposal")
        sections.append(f"<section><h2>기획 제안 · 구현 전 가설</h2><p>{_escape(proposal['target_user'])}</p>"
                        f"<p>{_escape(proposal['use_context'])}</p><p>{_escape(proposal['mechanism'])}</p>"
                        f"<div class='grid'><article><h3>현재 사용 과정</h3>{_list_html(proposal['before_steps'])}</article>"
                        f"<article><h3>제안하는 사용 과정</h3>{_list_html(proposal['after_steps'])}</article></div></section>")
        scenes = "".join(f"<article><h3>{_escape(scene['title'])}</h3><p><b>개선 전</b> {_escape(scene['before'])}</p>"
                         f"<p><b>제안 장면</b> {_escape(scene['after'])}</p></article>" for scene in proposal["visual_scenes"])
        sections.append(f"<section><h2>시각 장면 · 제안</h2><div class='grid'>{scenes}</div></section>")
        sections.append(f"<section><h2>가정과 확인할 질문</h2>{_list_html(proposal['assumptions'])}"
                        f"{_list_html(proposal['validation_questions'])}<h3>남은 불확실성</h3>"
                        f"{_list_html(guide.get('uncertainties', []))}</section>")
    cards = []
    for source in guide["sources"]:
        facts = "".join(f"<li>{_escape(fact['kind'])} · {_escape(fact['text'])}"
                        f"<pre>{_escape(json.dumps(fact, ensure_ascii=False, indent=2))}</pre></li>" for fact in source["facts"])
        cards.append(f"<article class='source'><span class='tag'>{_escape(_SOURCE_TYPES[source['source_type']])}</span>"
                     f"<h3>{_escape(source['title'])}</h3><p class='meta'>{_escape(source['source_id'])} · "
                     f"페이지 모델 {_escape(source['page_model'] or '미확인')} · "
                     f"{_escape(_COVERAGE[source['coverage']])}</p><blockquote>{_escape(source['text'])}</blockquote>"
                     f"<p class='meta'>문서판 {_escape(source.get('document_version') or '미확인')} · "
                     f"구매 모델 {_escape(source['purchased_model'] or '미확인')} · "
                     f"게시일 {_escape(source['published_at'] or '미확인')}</p>"
                     f"<a href='{_escape(source['url'])}' rel='noopener noreferrer'>공개 원문 출처 ↗</a>"
                     f"<p class='meta'>원문 위치 {_escape(json.dumps(source['locator'], ensure_ascii=False))}</p>"
                     f"<h4>보존한 원문 사실</h4><ul>{facts}</ul></article>")
    sections.append("<section><h2>실제 근거 원문 · 제안과 구분</h2>" + "".join(cards) + "</section>")
    return ("<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{_escape(guide['title'])}</title><style>"
            "*{box-sizing:border-box}body{margin:0;background:#f7f8f3;color:#233c2f;font-family:Arial,sans-serif;"
            "line-height:1.7}main{max-width:1000px;margin:40px auto;padding:24px}header,section{background:white;"
            "border:1px solid #dce4d5;border-radius:14px;padding:28px;margin-bottom:24px}h1{font-size:30px;"
            "line-height:1.4}h2{font-size:22px}h3{font-size:18px}.grid{display:grid;grid-template-columns:"
            "repeat(auto-fit,minmax(240px,1fr));gap:16px}article{padding:18px;border:1px solid #dce4d5;"
            "border-radius:10px;margin-bottom:16px}.tag{background:#edf3e7;padding:5px 10px;border-radius:6px}"
            ".notice{padding:14px;background:#fff6e9;border-left:4px solid #b18446}.meta{color:#59685d;"
            "font-size:14px}blockquote{white-space:pre-wrap;margin:12px 0;border-left:3px solid #759963;"
            "padding-left:16px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;background:"
            "#f6f8f3;padding:12px}a{color:#355b33;overflow-wrap:anywhere}@media print{"
            "body{background:white;font-size:13px;line-height:1.5}main{margin:0;padding:0;max-width:none}"
            "header,section{border-radius:0;padding:14px;margin-bottom:12px}"
            "h1{font-size:22px}h2{font-size:18px}h3{font-size:15px}h2,h3{break-after:avoid}"
            "article{break-inside:avoid;padding:10px;margin-bottom:10px}"
            "pre{display:none}"
            "a:after{content:' (' attr(href) ')';font-size:11px}}@page{size:A4;margin:16mm}</style></head>"
            f"<body><main><header><span class='tag'>{_escape(kind)}</span><h1>{_escape(guide['title'])}</h1>"
            f"<p class='notice'>{_escape(guide['notice'])}</p><p class='meta'>실제 자료 묶음 "
            f"{_escape(guide['bundle_id'])}</p></header>{''.join(sections)}</main></body></html>\n")


def render_guide_markdown(guide: dict) -> str:
    kind = _kind(guide)
    lines = [f"# {_markdown(guide['title'])}", "", f"**{_markdown(kind)}**", "", _markdown(guide["notice"]), "",
             f"자료 묶음: {_markdown(guide['bundle_id'])}", ""]
    proposal = guide.get("proposal")
    if guide["guide_kind"] == "concept_draft":
        if not isinstance(proposal, dict):
            raise ValueError("Concept guide requires an existing proposal")
        lines += ["## 기획 제안 · 구현 전 가설", "", _markdown(proposal["target_user"]), "",
                  _markdown(proposal["use_context"]), "", _markdown(proposal["mechanism"]), ""]
        for title, key in (("현재 사용 과정", "before_steps"), ("제안하는 사용 과정", "after_steps"),
                           ("가정", "assumptions"), ("확인할 질문", "validation_questions")):
            lines += [f"### {title}", ""] + [f"- {_markdown(value)}" for value in proposal[key]] + [""]
        lines += ["### 시각 장면 · 제안", ""]
        for scene in proposal["visual_scenes"]:
            lines += [f"**{_markdown(scene['title'])}**", "", f"- 개선 전: {_markdown(scene['before'])}",
                      f"- 제안 장면: {_markdown(scene['after'])}", ""]
        lines += ["### 남은 불확실성", ""] + [f"- {_markdown(value)}" for value in guide.get("uncertainties", [])] + [""]
    lines += ["## 실제 근거 원문 · 제안과 구분", ""]
    for source in guide["sources"]:
        lines += [f"### {_markdown(source['title'])}", "", f"출처 ID: {_markdown(source['source_id'])}", "",
                  f"자료 범위: {_markdown(_COVERAGE[source['coverage']])} · 페이지 모델: {_markdown(source['page_model'] or '미확인')}",
                  f"문서판: {_markdown(source.get('document_version') or '미확인')} · 구매 모델: {_markdown(source['purchased_model'] or '미확인')}",
                  f"게시일: {_markdown(source['published_at'] or '미확인')}", ""]
        lines += ["> " + _markdown(line) for line in source["text"].splitlines()] + [""]
        destination = quote(source["url"], safe=":/?=&%+#")
        lines += [f"[공개 원문 출처]({destination})", "", "원문 위치: " + _markdown(json.dumps(source["locator"], ensure_ascii=False)),
                  "", "보존한 원문 사실:", ""]
        lines += [f"- {_markdown(json.dumps(fact, ensure_ascii=False))}" for fact in source["facts"]] + [""]
    return "\n".join(lines)
