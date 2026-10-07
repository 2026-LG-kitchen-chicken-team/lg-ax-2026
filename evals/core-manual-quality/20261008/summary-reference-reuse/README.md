# CORE-C4-SUMMARY-REUSE-01a10729-01 — 같은 요약의 국소 수리 재사용

2026-10-08 KST, 황대겸/unknownamed. PR251의 C4 요약 인용 커버리지 뒤 독립 경로를 확인하니 public_repair가 runtime을 새로 만들면서 변경하지 않은 summaries의 원 건수·분모를 누락했다. 새 수리 호출을 discovery 분모로 세지 않고 기존 요약과 일치하는 원 집계만 복사한다. 같은 bundle의 중복 제외 고객 ID·기존 성공 denominator ID·요약 인용 집계를 재계산해 기존 metadata와 JSON digest까지 같은 경우에만 보존한다. 잘못된 건수·출처·승인값은 invalid_previous_metadata로 표시하고 과거 원 snapshot은 보존한다. legacy metadata 부재는 미확인으로 남기며 0이나 새 승인을 만들어내지 않는다. caller runtime_metadata로 이 근거를 덮어쓰지 못한다. 원 summaries/facts·정상항목·실패·공유최대2/추가 모델 호출 수는 보존한다.

CORE 저장 근거와 공개 API 전달은 별도다. 현재 apps/api/src/lgax_api/research_planning.py public_research_brief는 runtime allowlist를 새로 구성해 summary_reference_coverage를 HTTP/MCP 응답에 전달하지 않는다. 이 경계를 source-only 격리 관찰로 남기고 PM에 최소 안전 전달을 인계한다. API/MCP/공통 계약 파일을 편집하거나 런타임 등록/실제 모델/의견 분류/PM 인수 완료로 집계하지 않는다. 기존 실제 normal-r2 문장의 명시된 테스트 snapshot과 원 개발 입력을 재사용하며 새 고객 후기/모델/기존6사례 AI채점0이다. [격리 수신](verification.json).

격리 검증: 관련 public planner/repair36검사(신규 재사용6/이전30), Ruff, AGENTS/CLAUDE와 문서 탐색 PASS. 재사용 metadata 외 기존 수리 AST 동등, 시점 지침 외 planner AST 동등, 기존 로그231구간/818663바이트와 최종 문서 상대링크136개 존재를 확인했다. 공개 API 집계 누락은 실제 projection 함수로 재현했고 PM 전달 미완료이며 모델0·실제 의미 효과/PM 인수 미검증이다.
