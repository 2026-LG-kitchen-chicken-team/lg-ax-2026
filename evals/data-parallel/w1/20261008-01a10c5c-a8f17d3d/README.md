# DATA-W1-01a10c5c-a8f17d3d — 결과 원문 대조의 부분 검수

2026-10-08 KST. 사용자 지정 W1 / 신진하(DATA). 시작 main `eab85d48385f965eef48c07a6cdd8f6fd9851c62`, PR269 head `2672f00b2a9ac5bad38e7b523f67e2814d0ec144`, PR273 head `92d5258f04d377b144d4c81cac89687917650861`. 별도 `codex/data-w1-01a10c5c-a8f17d3d` worktree의 새 파일만 작성했다.

## 받은 자료와 검수 범위

| 작업 | 이번에 실제 확인한 범위 | 미완료 |
| --- | --- | --- |
| 최신 정상/조건 두 결과 | 고정 PM report·DATA 인계·원문을 연결한 10항목/23선택 발췌의 의미 진단. R9 출처 인용34구간과 파일17개의 raw SHA256/Git blob/bytes 확인 | 실제 원 JSON 0. 출력 연속인용·정확 필드 위치·전체 누락·generation commit·실제 전체 입력/모델/usage/부모 수신증 |
| 동일 7입력 비교 | 기존 공개 발신 metadata의 7입력/6그룹과 raw/canonical SHA·자료/모델·판본을 각각 연결한 비교 인수표 | 기존 Agent/일반 LLM 원출력·조건/모델/full-input·실패/retry/usage 미수신, 인정 가능한 비교0 |
| 무Gold 4질의 | 저장 검색행 중 해당60행/12방법-질의 그룹과 반환 원문13개를 읽고 원문 의미 범위를 대조. 인용10구간, 전체44구간 | 실제 AI 답변/보류/확인 질문0. AI 의미 판정/승인 정확도는 null |

이 폴더는 최종 독립 채점이나 Gold 승인 결과가 아니다. 원문 의미를 사람이 읽는 방식으로 대조한 W1 진단과 SHA/span/metadata 검사를 구분한다. 코드 검사는 의미 함의를 자동 입증하지 않는다.

## 선언 SHA와 실제 파일 SHA

| 실행 | PM이 선언한 public output SHA256 | W1이 받은 실제 원 출력 파일/SHA |
| --- | --- | --- |
| `run-1f83d846191941aea21153897b944ec1` | `4e84728d07aedff38cc30c26f839abce2ae54719e341954f27dff353c79ed3d2` | 미수신 / null |
| `run-754268c6b0cb41bba50c5b8d713332d9` | `0fd3a2047a7fd884af1c89e6d87ef46e83a446f5b277d18c838876bf63427c1d` | 미수신 / null |

받은 **PM report 파일** raw SHA256은 `f7d69e6fbd9ac43cd08754c7c7dfd51032b02472df90be37db160f17cb2f55fa`다. 보고서 바이트를 실제 모델 출력 바이트로 바꾸지 않았다. 모든 실제 받은 파일의 Git commit/path/blob/raw SHA/bytes는 [source-pins.json](source-pins.json)에 있다. `sources/`의 원바이트 문서 사본에 있는 상대 링크는 원 `repository_path` 기준이며 새 폴더용으로 바꾸지 않았다. 읽을 때 pins의 원 GitHub URL을 사용한다. 원 출력 SHA의 계산 형식도 수신증이 필요하다. 일부 승인 필드를 받더라도 부분 파일의 해시는 전체 출력 해시와 별도로 기록한다.

[두 실행 계보 JSON](run-provenance.json) · [CSV](run-provenance.csv). 생성 commit은 아직 null이며 main/PR 게시 commit 또는 `core-next-actions`의 짧은 baseline commit을 생성 commit으로 대입하지 않았다. 모델 27B/digest/context16384/output4096·각2call/0repair·source count6은 **PM 선언**으로 저장했다. 조건 실행의 output token619/1729도 보고된 일부 값일 뿐 전체 prompt/실패/retry/usage 또는 비용 총계가 아니다. 미측정 총 사용량·비용은 null이다.

정상1조건과 revision5조건은 다르다. report에 parent/previous brief가 있어도 실제 저장된 부모/입력과 대조한 수신증은 없다. R9 공개 selected6 결과를 별도의 합성7입력 비교에 대입하지 않았다.

## 결과별 원문 의미 표

[정상 결과 표](normal-review.md) · [조건 변경 결과 표](changed-review.md) · [정상 CSV](normal-source-review.csv) · [조건 CSV](changed-source-review.csv) · [상세 원문/범위/SHA와 진단](excerpt-source-review.json) · [23발췌의 report 위치](report-excerpt-index.csv).

발췌는 정확 모델 JSON 인용이 아니다. 한 finding에 여러 필드가 붙어 있어 각 발췌의 정확 출력 필드는 null로 남겼다. `CG-N-03`은 출력 예시가 없는 보고 항목이다. 실제 summaries의 완전한 누락을 독립 확인했다고 표시하지 않는다.

- 752651: 다리 불편의 주체는 배우자, 편리함은 구매 희망이다. 약1개월의 청소 언급과 총약3달 사용을 구분한다. 냄새 치료의 정확 순서·지속/재발·분해/방법 무지/상담 전화는 원문에서 확인되지 않는다.
- 853593: 편리함·건조/성능 만족과 투입 준비에 대한 당황이 함께 있다. 645400의 기사 태도는 고객 인식이며 명시적 설치 거부와 다르다. 분류의 실제 배열/누락은 raw 수신 후 확인한다.
- 공식 p49: `80 ml ~ 100 ml보다 많은 경우`와 전원 켜기→전원 버튼3초→취소 선택을 함께 보존한다. 수치 자체는 원문에 있다. 음식물/세제/잔수량 조건 분기를 모든 고객의 상담 전 필수 조치로 합칠 근거는 없다. 다른 청소 절 참조는 세부 청소법 전체가 아니다.

원문에 없는 사실이 현실에서도 없었다는 뜻은 아니다. 미래 제안/가상 장면은 가능하나 실제 경험과 같은 위치에서 구분해야 한다. 정확 구매 SKU·구매 당시 판본·고객 원인/해결은 미확인이다. p49 원문은 기존 PDF 감사의 공개 발췌를 읽었고 W1은 PDF 재추출/OCR/자료 수집을 하지 않았다.

## 동일 7입력과 무Gold 4질의

[7입력 인수 비교 JSON](same-seven-input-comparison.json) · [CSV](same-seven-input-comparison.csv). 발신자가 계산해 공개한 원 input SHA와 canonical SHA를 별도 열로 유지했다. W1은 이번 작업에서 private ZIP/입력을 다시 열거나 전송하지 않았다. raw input producer Git commit은 기존 null을 유지한다. 실제 입력/조건/자료·모델 설정/출력 계약이 일치하지 않거나 수신증이 없으면 동일 입력 비교로 인정하지 않는다. 원 실패와 모든 retry·stage usage가 포함된 기존 결과만 받을 예정이다.

[무Gold4 진단 표](no-gold-review.md) · [상세 JSON](no-gold-source-diagnostics.json) · [CSV](no-gold-source-diagnostics.csv) · [기존 저장 검색순위 문맥](saved-no-gold-retrieval-context.csv).

FR04 이전판본 미제공, FR05 타모델 기능 적용, DW05 개인 식기 치수/배열 미제공, MW05 음식별 사전 기억/출력 설정과 사용자 임의 시간·출력 저장의 차이를 구분했다. 기존 `expected_response`는 공개 개발 대응표의 정책 metadata이며 신규 Gold/승인 점수가 아니다. 저장 검색순위와 검색 정책 상태는 자연어 AI 응답이 아니다. MW05의 받은 발췌는 사용자 저장 기능의 존재를 확인하지 못하며 제품 전체에 그 기능이 없다는 증명도 아니다.

공개 원 대응표에는 다른11문항의 기존 정답 metadata도 있다. 파일은 원바이트로 보존했지만 그11문항 채점·분모 재계산·225검색·기존 생산자 검사 코드를 실행하지 않았다. 비공개 Gold/reviewer-only/demo ZIP은 열지 않았다.

## 실행·인계와 다음 하나

[검수 결과](verification.json) · [실행 수신증](execution.json) · [최종 validator 원 로그](history/data-audit-v2.log) · [기록](work-record.md). 기존 고정 image와 외부 실행기를 검증해 무인증/network-none/read-only/UID1000 validator에서 새 감사 도구·해당 Ruff·AGENTS/CLAUDE 바이트 검사를 실행했다. 모델/OCR/검색 재실행0. 실제 원문 대조는 W1 진단이고 검사는 인용/참조 무결성 범위다.

[추가 인계 요청 #15](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/15#issuecomment-6050694450)에 `DATA-W1-01a10c5c-a8f17d3d`로 막힘과 최소 인계를 남겼다. W3 [6050766403](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/15#issuecomment-6050766403)의 기존 연락 경로를 재사용한다. W1은 메일/ZIP/운영 DB/자동 표·분류·자료 수집/Gold·최종 채점 담당 파일을 수정하지 않았다. 사용자 지시에 따라 개인 README와 기존 코드/자료도 변경0이다.

**다음 하나:** PM이 연결한 기존 정상/조건 raw JSON 또는 source ID·정확 field path가 있는 승인 일부 필드를 받으면 그 부분부터 파일 SHA/계보와 원문 의미를 대조한다. 전체 packet·Gold·ZIP 완료를 이 착수의 선행 조건으로 붙이지 않는다. 같은7입력/무Gold4는 기존 원응답이 실제 들어올 때만 이어간다. 새 호출을 요구하지 않는다.
