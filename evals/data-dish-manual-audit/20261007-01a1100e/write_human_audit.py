"""Write reviewer-authored judgments in the new audit folder only."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ins = json.loads((OUT / "source-inspection.json").read_text(encoding="utf-8"))
snippets = json.loads((OUT / "manual-native-excerpts.json").read_text(encoding="utf-8"))
by_id = {x["audit_evidence_id"]: x for x in snippets}
completed = datetime.now(timezone(timedelta(hours=9))).isoformat()

judgments = []
existing_claims = {
    "DUE6BGL2E-MANUAL-D12": ("바구니별 큰 식기/작은 식기/수저류 배열 용도", "하단/상단/최상단 바구니 용도 안내. 공용 제품군 조건을 유지."),
    "DUE6BGL2E-MANUAL-D09": ("상단 바구니 높이3단계 조절", "높이 조절 절의 조건은23쪽 빈 바구니 및24쪽 양쪽 높이 동일 확인과 함께 보존."),
    "DUE6BGL2E-MANUAL-D13": ("높이 조절 전 식기 바구니를 모두 비우기", "높이 조절 시 주의이며 필터/제품 청소를 위한 비우기 지침과 구분."),
    "DUE6BGL2E-MANUAL-D14": ("상단 먼저/하단 나중 수납 및 큰 식기의 상단 노즐 간섭", "식기가 상단 노즐에 닿아 회전을 방해하는 수납 문맥. 노즐 구멍 막힘/청소와 구분."),
    "DUE6BGL2E-MANUAL-D13-P24": ("상단 바구니 양쪽 높이 동일 확인 후 밀어 넣기", "바구니 높이와 수납 조건이며 청소 주기/효과 근거가 아님."),
    "DUE6BGL2E-MANUAL-D14-P20": ("상단 바구니를 빼낸 상태에서 식기 세척 금지", "제품 사용 중 바구니 유지 주의. 관리 단계의 부품 분리 금지를 뜻하지 않음."),
}
for old in ins["existing_manual_records"]:
    claim, condition = existing_claims[old["source_id"]]
    judgments.append({
        "audit_row_id": "EXISTING-" + old["source_id"], "source_id": old["source_id"],
        "page": old["page"], "section": old["section"], "origin": "existing_R8_official_source",
        "document_version": old["document_version"], "pdf_sha256": old["document_sha256"],
        "text_sha256": old["text_sha256"], "link_verdict": "일치",
        "claim": claim,
        "support_verdict": "지지", "unsupported_extension": "내부/필터/노즐 청소법 또는 냄새 해결로 전이하면 미지지",
        "conditions": "공용 DUE6 계열 설명서. " + condition,
        "actual_customer_cause_or_recovery_verdict": "미확인",
        "manual_visual_check": True, "automatic_structure_output_received": False,
    })

specs = [
    ("DW-CLEAN-SAFETY-P05", "청소 전 전원 플러그 분리와 안전 금지 사항", "청소 전 플러그 분리; 드라이기/촛불/물 직접 분사/거친 금속 솔 금지. 실제 절차는 관련 관리 절을 함께 확인.", "이 경고 자체를 증상 원인 또는 냄새 제거 효과로 바꾸지 않음"),
    ("DW-INTERNAL-CLEAN-P39", "내부는 물 적신 부드러운 천으로 닦는 안내", "인화성 물질·치약·연마제·락스 등을 뿌려 닦지 않는 제품 손상 주의; 안전5쪽과 함께 읽음.", "특정 후기의 물비린내를 이 방법이 해결했다는 효과 주장"),
    ("DW-FOOD-FILTER-P39", "음식물 거름 필터 분리(1~3단계) 및 배수/잔수 설명", "하단 바구니를 꺼내고 필터를 반시계 방향으로 분리. 스테인리스 모서리 주의. 40쪽4~6단계와 연결. 냄새 역류 차단용 일정량 잔수는 설명서가 정상 구조로 설명함.", "모든 잔수를 고장·냄새 원인으로 판정하거나 이3단계를 완결된 청소법으로 표시"),
    ("DW-FOOD-FILTER-P40", "필터 솔/흐르는 물 세척·재조립(4~6단계)와 악취 가능성", "39쪽1~3단계에 이어 부드러운 솔/흐르는 물, 필터 재조립, 시계 방향 딸깍, 하단 바구니 복귀. 미청소 음식물 찌꺼기로 악취/성능 저하가 생길 수 있다는 조건부 주의.", "고객이 필터를 청소하지 않았다고 추정하거나 실제 냄새 원인을 필터로 확정"),
    ("DW-TUB-CITRIC-P41", "세척조의 찌꺼기·냄새·얼룩에 구연산 및 통살균(P13) 안내", "빈 내부, 구연산 분말 투입, ThinQ 다운로드 통살균 P13 선택, 시작/시작정지 순서. 세제 불필요라는 알아두기 포함. 앱/코스/실제 버튼·모델 적용 확인 필요.", "모든 제품의 기본 코스라고 단정하거나 고객의 비린내·세균 문제 해결을 보장"),
    ("DW-TUB-VINEGAR-P41", "식초 세척조 청소 시작(1단계: 내부 비우기)", "42쪽2~5단계 및 식초 사용량/직접 붓기 금지/뜨거운 그릇 주의와 반드시 연결.", "이 한 쪽의 첫 단계만 완결된 식초 청소법으로 제공"),
    ("DW-TUB-VINEGAR-P42", "식초 세척조 청소 후속(2~5단계) 및 사용량/주의", "41쪽1단계에 이어 상단 바구니 중앙 그릇에 식초200~300 ml, 통살균 P13 및 시작. 직접 붓기/과도 사용의 제품 손상과 뜨거운 그릇 주의를 포함.", "단위·200~300 ml·상단 바구니 중앙 그릇·금지 조건 삭제 또는 실제 효과 보장"),
    ("DW-NOZZLE-P42", "막힌 노즐 구멍의 청소, 하단 고정 노즐·상단 분리 절차 구분", "하단은 막힌 구멍 이물질 제거/강제로 당기거나 회전 금지. 상단은 바구니 꺼내기·너트 반시계 분리·물 흔들기/구멍 이물질 제거.43쪽 재조립까지 연결.", "배열 간섭 조건을 노즐 청소법으로 대체하거나 고정 하단노즐을 상단처럼 분리"),
    ("DW-NOZZLE-P43", "상단 노즐 재조립(6단계)과 부드러운 회전 확인", "42쪽1~5단계에 이어 너트를 시계 방향으로 조립하고 회전을 확인. 수동 청소 절차의 이어지는 단계.", "42쪽 내용 없는 분리/조립 단편 지침 또는 자동 구조 연결 성공 주장"),
    ("DW-STORAGE-P43", "장기간 보관 전 필터·세척조·세제통 청소와 보관 조건", "수도꼭지 잠금·플러그 분리·필터 분리 후 남은 물기 닦기. 실외 겨울 동결 안내는 별도 조건이다. 렌더의50℃가 native text에서는50 7로 깨져 보이므로 값은 시각 원문으로만 확인.", "정상 사용 중 모든 잔수 제거 지침, 자동 숫자/단위 추출 성공 또는 상시 동결 조건으로 전이"),
    ("DW-ODOR-DEVICE-P49", "제품 냄새의 조건별 문제 해결 표", "처음 사용/장기간 미사용/미세척 식기 장기보관/많은 잔수/바닥 찌꺼기 각각 별도 질문·조치. 잔수80~100 ml보다 많은 경우의 취소3초 배수와 세척조 청소 참조를 원문 조건 그대로 보존.", "각 경우를 한 원인으로 합치거나 고객의 실제 원인·지원 약속·해결 완료로 단정"),
    ("DW-ODOR-FISHY-P49", "세척 후 비린내의 조건별 질문·세제/식품/세척조 안내", "세제 향을 물비린내로 느낄 수 있음과 어패류/간유/젤라틴/치즈/계란 식기 경우를 구분. 애벌 세척, 세제/린스 변경, 세척조 청소 참조는 조건을 함께 읽음.", "고객이 특정 식품/세제를 사용했다고 추정, 모든 물비린내의 원인 확정, 반드시 해결된다는 약속"),
    ("DW-POOR-CLEANING-P50", "세척 성능 표에서 배열 문제와 노즐/필터 막힘의 조치 구분", "서로 겹침/노즐에 식기 걸림→배열, 노즐 구멍 막힘→노즐 청소, 필터 막힘→필터/주변 이물질 제거. 서로 다른 행의 조건·조치를 교차 연결하지 않음.", "배열/바구니 경고만으로 제품 청소/냄새 근거를 대신함"),
    ("DW-NOZZLE-DIAG-P48", "노즐 회전 불량/구멍 막힘 행이 노즐 청소 절로 연결", "증상 노즐이 부드럽게 돌아가지 않음→노즐 구멍 막힘 질문→제품관리의 노즐청소 참조. 동일 표의 문 닫힘/바구니 높이 행과 구분.", "인접한 바구니 높이/문닫힘 행을 노즐청소의 원인·조치로 연결"),
]
for identifier, claim, conditions, unsupported in specs:
    snippet = by_id[identifier]
    judgments.append({"audit_row_id": identifier, "source_id": snippet["source_id"], "page": snippet["page"],
                      "section": snippet["section_start"], "origin": "new_audit_only_native_manual_excerpt",
                      "document_version": snippet["document_version"], "pdf_sha256": snippet["pdf_sha256"],
                      "text_sha256": snippet["native_excerpt_sha256"], "start_char": snippet["start_char"], "end_char": snippet["end_char"],
                      "link_verdict": "일치", "claim": claim, "support_verdict": "지지", "conditions": conditions,
                      "unsupported_extension": unsupported, "actual_customer_cause_or_recovery_verdict": "미확인",
                      "manual_visual_check": True, "automatic_structure_output_received": False,
                      "registered_in_existing_R8_bundle": False})

scope_rows = [
    {"audit_row_id": "SCOPE-M11", "source_id": "MW23FDI-MANUAL-M11", "page": 25,
     "claim": "공개 M11 ID를 식기세척기 관리 근거로 연결", "link_verdict": "오류", "support_verdict": "미지지",
     "conditions": "실제 registry의 full ID는 MW23FDI/전자레인지 출력 조절. runtime shorthand M11은 별도 매핑을 수령해야 검수 가능.",
     "observed_bad_runtime_connection": False},
    {"audit_row_id": "SCOPE-SKU", "source_id": "LGE-R8-REVIEW-752651", "page": None,
     "claim": "실제 구입 SKU와 구매 당시 설명서가 DUE6BGL2E/current manual과 같음", "link_verdict": "미확인", "support_verdict": "미확인",
     "conditions": "page_model만DUE6BGL2E, purchased_model=null/published_at=null/current reference only. 실제 SKU·사용조건 인계 필요."},
    {"audit_row_id": "SCOPE-CAUSE-RECOVERY", "source_id": "LGE-R8-REVIEW-752651", "page": 49,
     "claim": "실제 고객 물비린내 원인이 확인되고 공식 관리법으로 해결됨", "link_verdict": "미확인", "support_verdict": "미확인",
     "conditions": "후기는 발생 경험, 설명서는 경우별 지침. 실제 원인검사·새로운 사용자 실행/결과 또는 고정 모델 출력의 독립 검수 근거 없음."},
    {"audit_row_id": "SCOPE-AUTO-TABLE", "source_id": "DUE6BGL2E-manual-ff60f78ab832", "page": 49,
     "claim": "자동 셀·행·열·모델·숫자·단위·각주 연결이 출력되고 검증됨", "link_verdict": "검증 불가", "support_verdict": "미확인",
     "conditions": "실제 자동 구조 출력을 이번 작업에 받지 못함.14쪽 수동 렌더 읽기·native text 범위 성공으로 자동 성능을 대체하지 않음."},
]

payload = {"record_id": ins["record_id"], "source_commit": ins["source_commit"], "completed_at_kst": completed,
           "document_version": ins["pdf"]["document_version"], "pdf_sha256": ins["pdf"]["sha256"],
           "applies_to": "shared_DUE6_family_reference_not_confirmed_purchased_SKU",
           "existing_records": 6, "audit_only_native_excerpts": 14, "verdict_rows": judgments,
           "scope_or_rejected_connection_rows": scope_rows,
           "all_actual_customer_recovery_claims_unconfirmed": True,
           "automatic_structure_verified": False, "model_calls": 0, "ocr_runs": 0}
(OUT / "audit-table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

lines = ["# 연결별 원문 검수표", "", f"고정 source `{ins['source_commit']}` / 판본 `{ins['pdf']['document_version']}` / PDF SHA `{ins['pdf']['sha256']}`.", "",
         "`일치`는 이 원문·쪽·절 연결의 수동 확인이다. `지지`는 표시된 제한적 문서 주장에 한한다. 실제 고객의 구입 SKU·냄새 원인·호전은 모두 미확인이다.", "",
         "## 기존 R8 발췌6개", "", "| source ID | 쪽·절 | 원문/facts/locator 연결 | 지지하는 범위 | 청소/냄새 해결로 전이 |", "|---|---|---|---|---|"]
for x in judgments[:6]:
    lines.append(f"| `{x['source_id']}` | {x['page']} · {x['section']} | 일치 | {x['claim']} | 미지지 |")
lines += ["", "기존6개의 등록 위치는20/23/24쪽이다. `source-inspection.json`은 PDF native text의 공백만 정규화한 문장 존재, bundle 전체 source record, dataset/plan 원문·쪽, facts·locator, 모델·판본·SHA의36개 항목을 대조한다.", "",
          "## 이번에 확보한 실제 공식 관리/문제 해결 구간14개", "", "| 검수 ID | 쪽 | 연결/지지 | 공식 문서가 지지하는 주장 | 함께 보존할 조건·전후 절 | 미지지 확장 |", "|---|---|---|---|---|---|"]
for x in judgments[6:]:
    lines.append(f"| `{x['audit_row_id']}` | {x['page']} | 일치/지지 | {x['claim']} | {x['conditions']} | {x['unsupported_extension']} |")
lines += ["", "이14개는 새 **검수용** native 범위다. 기존 R8 생산 bundle에 등록하거나 공통 계약을 수정하지 않았다. 적용 제품군은 공용 DUE6 설명서이고 정확 구입SKU/구입시점 판본은 미확인이다.", "",
          "## 오류·미확인·검증 불가 경계", "", "| 검수 ID | 주장 | 판정 | 이유·필요한 인계 |", "|---|---|---|---|"]
for x in scope_rows:
    lines.append(f"| `{x['audit_row_id']}` | {x['claim']} | {x['link_verdict']} / {x['support_verdict']} | {x['conditions']} |")
lines += ["", "`SCOPE-M11`은 공개 registry의 제품 불일치 연결을 거부하는 검수 기준이다. 실제 새 runtime에서 그 잘못된 연결이 발생했다고 관측한 결과는 아니다.", "",
          "## 실제 표 행 연결의 수동 확인", "", "49쪽 냄새 표는 **제품 냄새**와 **세척 후 비린내**를 서로 다른 증상 행으로 나눈다. 제품 냄새 내부의 첫 사용/장기 미사용/장기 식기 보관/잔수/찌꺼기와 세척 후 비린내 내부의 세제 향/특정 식품은 각 질문과 조치를 유지한다.50쪽 배열 문제와 노즐·필터 막힘 행도 서로 다른 조건이다.48쪽 노즐 회전/막힘 행을 인접한 문 닫힘·바구니 높이 행과 섞지 않았다. 이것은 육안 검수이며 자동 셀 구조 출력은 없다.", "",
          "## 남은 작업", "", "D2 생산 담당이 고정된 새 관리/냄새 sources를 별도 자료 버전으로 인계하고 PM이 공용 판본 적용 범위를 인수해야 한다. CORE는 근거를 소비한 새 고정 결과와 source ID 매핑을 인계해야 한다. 이후 새 결과의 주장별 대조를 수행한다. 고객 실제 원인/호전·시장 효과·자동 표 연결·최종 품질 승인과 부모Done은 이번 부분 검수 범위에서 미완료다.", ""]
(OUT / "audit-table.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")

observations = {
    1: "공용 적용 패턴과 MFL71959117 Rev.07_030626을 확인; 정확 DUE6BGL2E 표기는 없음",
    2: "목차의 관리39/문제해결45 및 공용 설명서 적용 주의를 확인",
    5: "청소 플러그 분리/촛불·드라이기·거친 솔·물분사 금지 문맥을 확인",
    20: "왼쪽 사용주의와 오른쪽 바구니 배열을 구분; 청소 절이 아님",
    23: "바구니3단 높이 및 비운 후 조절 주의를 확인; 필터 청소 절이 아님",
    24: "양쪽 같은 높이/노즐 간섭/최상단 바구니 등 인접 절을 구분",
    39: "내부 청소와 음식물 필터1~3단계/잔수 설명/모서리 주의를 확인",
    40: "필터4~6단계와 미청소 악취 조건을 에어필터 교체 절과 구분",
    41: "에어필터 초기화의 각주1과 세척조 구연산/식초 시작 절을 구분; P13/버튼/빈 내부 조건 확인",
    42: "식초200~300ml/직접 붓기 금지와 하단·상단 노즐 청소를 구분; 강제 당김/회전 금지 확인",
    43: "상단 노즐6단계가42쪽에서 이어짐; 보관의50℃는 native의50 7 문자오류와 구분",
    48: "노즐 회전/구멍 막힘→노즐 청소 행이 문닫힘/바구니 높이 행과 구분됨",
    49: "제품 냄새와 세척 후 비린내 증상 및 원인 질문/조치의 행 연결 확인;80~100ml/3초 수치·조건 확인",
    50: "배열과 노즐·필터 막힘의 조건별 조치를 구분; 성능 표를 냄새 원인 확정으로 전이하지 않음",
}
visual = []
for number, observation in observations.items():
    relative = f"visual/manual-page-{number:02d}.png"
    raw = (OUT / relative).read_bytes()
    visual.append({"page": number, "printed_page": number, "image_path": relative, "bytes": len(raw),
                   "sha256": hashlib.sha256(raw).hexdigest(), "reviewed_by_current_independent_DATA_agent": True,
                   "visual_link_verdict": "일치", "observation": observation,
                   "manual_review_not_automatic_structure_output": True})
v = {"record_id": ins["record_id"], "completed_at_kst": completed, "pdf_sha256": ins["pdf"]["sha256"],
     "renderer": "Poppler pdftoppm", "render_dpi": 95, "full_page_renders": len(visual),
     "total_render_bytes": sum(x["bytes"] for x in visual), "pages": visual,
     "native_text_caveats": ["pypdf cover encoding produced corrupt characters; PDFium native text and visual render used",
                              "page43 storage50℃ appears as50 7 in native text; exact native excerpt retained, numeric reading manual only"],
     "model_calls": 0, "OCR_runs": 0, "automatic_cell_graph_received": False}
(OUT / "visual-review.json").write_text(json.dumps(v, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

history = {"record_id": ins["record_id"], "completed_at_kst": completed,
           "events": [{"step": "native_anchor_first_execution", "exit_code": 1,
                       "reason": "Reviewer initial page5 start anchor 제품을 관리할 때 was absent; ValueError substring not found",
                       "action": "Read actual page5 native text and fix only new audit script to actual • 청소할 때는 anchor"},
                      {"step": "native_anchor_corrected_execution", "exit_code": 0, "input_byte_checks": 6,
                       "existing_record_comparisons": 36, "native_excerpt_count": 14},
                      {"step": "common_manual_caution_locator_precision", "exit_code": 0,
                       "action": "Caution exists on page2 rather than cover; correct new audit metadata field and preserve original bytes"},
                      {"step": "visual_review", "page_count": 14, "status": "reviewed", "automatic_structure_status": "no_output_received"}],
           "model_calls": 0, "ocr_runs": 0, "legacy_code_and_data_changes": 0}
(OUT / "execution-history.json").write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"manual_verdicts": len(judgments), "scope_verdicts": len(scope_rows), "visual_pages": len(visual), "render_bytes": v["total_render_bytes"]}, ensure_ascii=False))
