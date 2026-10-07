# CORE-X1-GUIDE-PRINT-01a10729-01 — 원문 보존과 시각 검수 근거

[수행 기록](../../../작업기록/황대겸/2026-10-07/CORE-X1-GUIDE-PRINT-01a10729-01.md) · [검사·3모델 출력](../../../../evals/core-manual-quality/20261007/x1-guide-print/README.md)

기준 `e04f42b5de37b2d1cad606f2f06a3f7fe6a91f30`의 실제 확장 bundle을 source-only Docker로 소비했다. 공식 MW23FDI3개/DUE6BGL2E6개/T876MEE1H1 6개와 전체 facts·page_model·문서판·null·locator·coverage를 그대로 복사한다. [audit JSON](../../../../evals/core-manual-quality/20261007/x1-guide-print/official-guide-audit.json)에 입력/renderer/HTML/Markdown의 SHA를 기록한다.

변경은 guides.py의 print CSS다. 고정 전 결과와 guide JSON/Markdown·HTML본문·screen CSS가 정확히 같다. PDF는 원문과 출처ID의 보존 대조와 전체 최종 PNG 판독에 사용한 QA 중간 산출물이며 정식 설명서로 배포하지 않는다. 기술 fact JSON은 HTML/JSON/Markdown에 계속 남고 인쇄에서는 중복 노출을 줄였다.

최종3/4/4쪽에서 원문15개와 ID15개가 일치했고 글자/수치/출처의 잘림·겹침, 첫 근거 제목의 단독 페이지가 없었다. Browser JavaScript OFF, scripts0, 외부요청0. 원 실패 출력과 도구 호출 수신/readonly snapshot·재개 상태는 비공개 기록에 보존했다. 기존 guard 검사는 재사용했고 CSS 보완 때문에 기존 전체 제품/독립 AI 품질 평가를 반복하지 않았다.

실제품 FAQ는 고정 자료의 적용 모델이 null인 별도 미완료다. 새 기획 설명서는 실제 저장 콘셉트 수신 전 만들지 않는다. 모델/새고객리뷰/콘셉트/비용사용/서비스·Worker·PM변경0, PM 인수/병합/전체 Done을 대신하지 않는다.
