# CORE-C4-SUMMARY-COVERAGE-01a10729-01

2026-10-08 KST, 황대겸/unknownamed. C4 건수·분모의 CORE 소비 구현이다. 기존 자료 종류별 source_type_counts는 의견 요약의 출처 커버리지를 뜻하지 않았다. 새 runtime.summary_reference_coverage는 반환된 요약의 원문 ID만 코드로 집계한다.

기존 중복 제외 고객-source 목록 중 성공한 discover 호출에 포함된 ID를 분모로 고정하고 긍정/부정/혼합별 요약 항목 수·고유 인용 ID 수, 전체 인용 합집합·극성 겹침·성공했으나 요약에 없는 수·미처리 입력 수를 분리한다. 실패 호출은 분모에 넣지 않고 분모0의 coverage_ratio는 null이다. 겹친 의견별 건수는 합산하지 않는다. 공식 문서·공식 답변은 고객-source 분모에 포함하지 않는다. 미인용/미처리를 어느 의견으로도 자동 분류하지 않는다.

요약 의미/분류 정확도·기간/시장 빈도·구매SKU·전체141 처리·실제27B 품질·PM 인수는 인증하지 않는다. 공통 계약·PM client/prompt·원 source/facts·생성/수리/공유최대2는 보존하며 모델·수리 호출을 추가하지 않는다. 검사는 기존 실제 후기837305/M11과 명시된 protocol-only source-reference 회귀를 사용한다. 새로운 고객 후기/기획/실모델 실행·기존6AI채점0. [격리 수신](verification.json).

격리 검증 완료: 관련 public planning 23검사(신규6/기존17), Ruff, AGENTS/CLAUDE 일치와 문서 탐색 PASS. 새 커버리지 계산 외 기존 AST/프롬프트 동등, 기존 원 로그231구간/818663바이트와 상대링크125개 존재를 확인했다. 첫 정적 검사의 import 순서 실패를 보존하고 공백만 정리한 뒤 재검증했다. 신규 모델0, 분류/시장빈도/실제 모델 품질/PM 인수 미검증.
