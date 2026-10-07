# CORE-X1-D2-CONSUMER-01a10729-01 — 실제 자료·원문·출력 검증

2026-10-08 KST, 황대겸/unknownamed. [같은 ID 기록](../../../작업기록/황대겸/2026-10-08/CORE-X1-D2-CONSUMER-01a10729-01.md).

- [DATA PR254](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/254) head `94b560de72f91795cfd50aada9e17d6773383ae1`; [고정 전달](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/94b560de72f91795cfd50aada9e17d6773383ae1/evals/data-d1-d2/20261007-01a10600/current-delivery.json). 기존 `.producer.json` sidecar와 canonical ResearchBundle3을 구분했다.
- [실제 소비 대조](../../../../evals/core-manual-quality/20261008/d2-reference-consumer/consumer-audit.json):184source/141개 기존 후기 객체/공식42source/관리14개의 원문·판본·쪽·범위/SHA 및 ID 대응. 구매 SKU·후기 게시일 null·개발 split·원 hold 보존, QA 질문과 공식 답변 역할 분리.
- [검사 수신·소스 SHA](../../../../evals/core-manual-quality/20261008/d2-reference-consumer/verification.json): 관련7검사/Ruff, 명시적 ID·공식 도메인·역할·input/output guards, 기존 모델별3출력 세형식 byteexact. source-only Docker UID65534/networknone/read-only/auth0.
- [공식 참고자료](../../../../evals/core-manual-quality/20261008/d2-reference-consumer/official-references.zip): 실제 source42개의 JSON/HTML/MD, 공용 FAQ·설치·관리 절의 적용 미확인·연속 페이지·native 단위 경계 표시. 고객 질문 원문을 공식 답변에 포함하지 않는다.
- [화면·인쇄](../../../../evals/core-manual-quality/20261008/d2-reference-consumer/visual/render-receipt.json): 화면3/33쪽 직접 PNG검수·원문42ID/본문 보존·겹침/잘림 관찰0. PDF원문 시각 검수는 DATA의 원 기록과 구분한다.

표시·계약·소비 검사 성공은 실제 LG27B 의미 품질·정확 구매 모델·고객 원인/호전·운영 등록·PM 인수/병합·전체Done의 근거가 아니다. 새 실모델/설치/비용/계획 선택·6사례 재채점0. 기존 PM prepared27B 선택과 항목별 의존 보류를 유지하며 새 인간 질문은 없다.
