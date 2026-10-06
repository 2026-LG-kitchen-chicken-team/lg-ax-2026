# DATA 남은 배정의 실제 후속 — 2026-10-06

담당 신진하/@ginaginaring. 사용자 지시대로 이전 #12의1~7단계를 진행 기준으로 삼지 않았다. 최신 [PM DATA-SOURCE-R3](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/13#issuecomment-6011538542)와 본인 #111~#114/#148을 진행했다. 자동화OFF·새 모델 호출0·판단 코드 변경0·원본 변경0이다.

## 실제 결과

|범위|산출물|
|---|---|
|공개 원문 등록→검색→재시작|[HTTP46요청](document-http-after.json), PDF3·근거21의 바이트/텍스트 정확 일치와 ID·모델·버전·원본 변경/삭제 거부. [구현 전 baseline](document-http-before.json)을 분리 보존|
|자료 카탈로그·한국어 BM25·CSV/PDF 연결|신규 evidence_catalog/retrieval, ReviewDocumentRepository, 기존 DocumentRepository/WorkspaceDocumentStore 연결. 기존8열CSV36·합성demo1.0/2.0·공통literal API 보존|
|동일 입력 검색 비교|[개발 CPU4질의](retrieval-development-measured.json): 라벨3·무관1, top3 recall/MRR/nDCG1.0. BGE-M3/재정렬은null. 독립 평가/기존45·225행/모델 우위 아님|
|대겸의 새 R4 원문 대조|[결과별 표](r4-original-audit.md), [해시·전체ID](r4-original-audit.json).11/11·11/11·10/10 source exact. 세 결과 모두 질문 없는 보류failed, 기능·gap·concept 미도달|
|별도 날짜 시연|[인계 metadata](demo-handoff.json), [새 원문·구성 날짜](source.synthetic-dated-demo.v1.json), [dataset](dataset.synthetic-dated-demo.v1.json), [sidecar](annotation.synthetic-dated-demo.v1.json). 원 CSV와 다른source/ID/자료집 버전. 구성 날짜를 원 게시일로 표시하지 않음|
|집계→API→MCP→원문→재시작|[실제 수신증](dated-api-mcp-restart.json): 동일 aggregate와 비어 있지 않은 원문. [10월](demo-october.json) 분모4/날짜누락1, [겨울](demo-winter.json)2건, [빈 결과](demo-empty.json)ratio null|
|주제 표시명|[7개 한국어 표시명](topic-display-labels.preview.v1.json). PM 결정대로 **주제 언급 비율**, polarity 없음·human preview|
|회귀·오류 보존|[85검사+5무결성 검사](checks-final/checks.json) 모두exit0, [로컬 초기 오류 이력](setup-failure-history.json) 보존|

청소 언급1/분모4=0.25는 청소가 크게 불편하지 않다는 긍정 원문006을 포함한다. 불편비율로 표현하면 잘못이다. 원36건은 여전히 날짜 없음이며 원집계 분모0/ratio null이다.

## PM·CORE·WEB 인계

- @jeongiryang: 새 자료 코드 검수/병합, BM25 공개 방법명 계약 채택, 새 dated demo/taxonomy 승인 및 운영 collector 주입. 현재 원 실행409의 소유 세션 확인은 새 독립 로컬 HTTP 통과와 구분한다. #15 자료교체/진단용 처분·독립검수자·승인 비공개 수신경로가 필요하다.
- @unknownamed: 새 R4 원문 대조의 상황 맥락/희망 문장과 질문 없는 보류를 확인하고 고정 후속 배정으로 수정·검증한다. 이전27B unmentioned/unsupported 조합은 SUPPORT_BASIS_MISMATCH, 계약상insufficient_evidence다. DATA는 판단을 중복 편집하거나 모델을 재생성하지 않았다.
- @choigilung: 승인된 새 버전과7표시명으로 동일aggregate ID 차트·원문·내보내기를 WEB에서 검증한다. API/MCP까지는 이번 실제 수신증으로 연결됐지만 새 날짜 버전의 브라우저 검사는 WEB 담당이다.

공개 설명서의 실고객 리뷰0·SKU 선택기능 적용/독립 의미 품질·실등록45/225행 모델 비교·실고객 시계열·PM 운영 반영·부모 Done은 남아 있다. 각 담당자가 막힌 지점과 다음 행동을 개인 날짜/기록ID 및 정식 Issue 보고에 연결한다.

## 제출 후 추가 자기검수

[승인계획 외부 모델·개정 변경 회귀](plan-freeze-regression.json)를 재현·수정했다. constructor 입력을 변경해도 원 승인계획의 모델·버전·SHA만 사용한다. [추가 검증85PASS/무결성](checks-plan-freeze/checks.json), [GitHub 보고·인계 수신증](github-report-receipts.json)을 추가했다. 원 로그/실패는 보존했다. 이전 구현head d5b3ee7의CI4/4 성공과 새 수정commitCI·PM 승인/병합을 구분한다.
