# DATA-WEB-VERSION-01a1100e

## 요청과 의도

- 담당: 신진하 / `ginaginaring`, 수행 AI: 현재 조정 대화 `01a1100e-bff9-7b81-b245-c9d0f56986e2`.
- 사용자 지시: “두작업 지금 실행하자”, “끝나고 내역할중 어떤게 남아있는지 알려줘”.
- 유효한 요청: [WEB O-R8-2](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/6#issuecomment-6039996324) — 실제 후기의 `document_version` 의미를 DATA가 확인해 WEB에 회신.
- 시작일: 2026-10-07 KST. 기준 source `ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f`, PM producer `5fdb3ad55349726fbe03c9f69651f895d73e8f10`.
- AI 해석: 고정 후기/모델 카탈로그 → 수집 필드 → ResearchBundle 변환 → WEB 표시 경로를 독립 대조한다. 후기 본문의 버전·구매 당시 제품/설명서 확인으로 확대하지 않는다.

## 경계와 시작 확인

- D1·D2 생산, D3·D4 및 PR246 보완은 기존 두 사용자 대화에 유지한다. 이번 작업은 메타데이터 의미/인계 검수다.
- 새로운 개인 날짜/ID 기록과 `evals/data-web-version-audit/20261007-01a1100e/`에만 쓴다. 사용자 보호 지시에 따라 개인 README·기존 코드·자료는 변경하지 않는다.
- AGENTS.md, 관련 개인 README, 최신 PM 수동 인수·관련 Issue/PR를 읽었다. 과거 요약보다 최신 #234·PR245 고정 인수를 우선한다.
- 본인 연결 메일의 `after:2026/10/07 ("lg-ax-2026" OR "LGAX")` 최근15건을 읽기 전용 검색했고 관련 #6·#5·PR246 요청 원문3건을 확인했다. 다음 페이지가 있어 전체 메일을 확인했다고 주장하지 않는다. 이메일 주소·원 헤더·HTML·접속 비밀은 게시하지 않는다.
- 새로운 모델/OCR 호출, 수집, 운영 HTTP·DB 생성·재시작 및 자동화 활성화는 없다.

## 진행

- 수집기는 후기의 `document_version`을 제품 카탈로그에서 복사한다. ResearchBundle은 후기 record의 해당 키가 없으면 `manual_version`을 사용한다.
- 현재 개발 후기141건에는 설명서 판51건과 공식 제품 페이지 스냅샷90건이 있다. 원문 ID별 독립 대조와 고정 producer/main 바이트 비교를 작성 중이다.
- 완료 결과, 실제 GitHub 회신/PR, 원본 보존 및 미완료를 종료 전에 이 기록에 연결한다.
- 날짜 경계 뒤의 [10/8 완료 기록](../2026-10-08/DATA-WEB-VERSION-01a1100e.md)과 [검수 요약](../../../../evals/data-web-version-audit/20261007-01a1100e/README.md)에 고정 결과를 연결했다. 기존 README는 변경하지 않았다.
