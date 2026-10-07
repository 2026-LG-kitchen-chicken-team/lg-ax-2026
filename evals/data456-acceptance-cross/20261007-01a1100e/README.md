# DATA 4·5·6 후속 — 고정 결과 소비·독립 대조

기록 ID: `DATA456-ACCEPTANCE-CROSS-20261007-01a1100e`. 신진하의 사용자 직접 요청에 따른 수동 검수다. 번호는 이번 사용자 목록의 4·5·6이며 과거 하네스 1~7단계가 아니다.

새 worktree와 이 고유 폴더에서만 작성했다. 기존 코드·자료·개인 README·원 검수/실패 이력을 보존했다. PR222 후보 생성, PR226 수집/SQLite/HTTP 실행, 다른 창의 #14 자동 표 생산을 반복하지 않았다.

## 원자료·권한

| 근거 | 불변 pin / 지시 | 이 검수에서 읽은 범위 |
|---|---|---|
| 새 R5 팩 PR218 | `0d920df7d1afd09490e91cd40bf9c6cb9dfaf75d` | 공개 JSON·분할·SHA·원문 위치 |
| 독립 후보 PR222 | `d5d33c46a5f27d7ccd805713c784ec4c9f0ace55` | 공개 역할·패키지 metadata |
| 격리 실행 PR226 | `06701a5979920abb6d18da039056b64af6c84df9` | 고정 manifest와 저장된 JSON/DB snapshots/응답 SHA |
| PR226 실행 코드 | `8ec1e8a51faabd6db032e52245680bef4229f93f` | 기존 dataset·등록 plan·원 PDF 바이트 |
| 이 검수 기준 main | `1f25e547f46ef155798fbc27f35aa2c7098ae912` | 버전 드리프트·기존 바이트 보존 대조 |
| PM 평가 범위 | [#15 6029601114](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/15#issuecomment-6029601114) | 후보 준비, CORE 매핑, 최종 채점자 분리 |
| CORE 수신 상황 | [#15 6030290912](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/15#issuecomment-6030290912) | 수신 폴더만 있음·실제 input-only 수신0·승인 무료 전송 연결 없음 |
| PM 격리 인수 | [PR226 review 5437336094](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/226#pullrequestreview-5437336094) | 격리 source8ec 원문/무결성 범위 승인 |

원문 자료 pin·파일 SHA·크기는 [source-pins.json](source-pins.json)에 있다. Git `show`로 원바이트를 읽으며 원 작성자의 실행 helper를 import/실행하지 않는다. 모델/OCR/새 HTTP/서비스 재시작/SQLite 재생성/ZIP 열람은 모두 0이다.

## 완료 범위와 남은 일

| 번호 | 이번 수행 | 상태 | 실제 완료에 필요한 다음 입력/담당 |
|---|---|---|---|
| 4 독립 평가 | PR222의 역할별 SHA/11·1·1 entry metadata와 PR226의 작성자 opaque digest 인계를 대조. 6 primary + paired1은 6그룹이며 R5 evaluation36과 분리. 기존 공개8/heldout7은 PM 지시대로 진단·회귀용 제외 | metadata 일치. 실제 독립 평가 미실행·점수 null | PM의 기존 무료 비공개 전달 경로와 수신 PC 매핑 → CORE input-only 실수신증·원문 매핑 → Gold/의미 독립성 승인·작성자와 분리된 최종 채점자 → 승인 실행자의 동일 전체 입력 Agent/강한 기준선 원출력 → 지정 채점자 평가 |
| 5 실제 후기 동향 | 원239→중복1 제거→고유238. 격리12 제외→연구226. 분할141/36/49/12, 모델별 분모·원문 ID/locator/SHA 연결과 분할 교집합·한국어 본문 SHA를 재계산 | PR226 membership/분모/별점수와 일치. 월·주제 실측은 보류 | PM 보조 DATA의 확인 게시일 provenance와 승인된 실제 후기 주제 annotation/version. 현재 게시일0·주제 Gold 없음 |
| 6 등록·조회 무결성 | 고정 109응답 중 JSON103을 명시적 UTF-8 compact serialization으로 SHA/size 재계산; PDF6 선언 SHA/size를 원 PDF3과 대조. 재시작 전/후 51쌍 전체 필드·DB snapshot·문서 GET/원문21·모델/판본 검색을 대조 | 저장된 격리 증빙 일치. PM도 이 범위 승인. 새 R5 운영 인수는 미확인 | PM의 운영 producer/consumer pin·승인 read/export와 동일 운영 DB의 원 record/API/raw bytes/restart 쌍·PM 인수증. 전체238 DB 인수도 미확인 |

독립 평가의 세부 결정 항목은 [evaluation-release-gates.json](evaluation-release-gates.json), 패키지 역할·SHA 대조는 [candidate-package-metadata.csv](candidate-package-metadata.csv)다. 이 개발 대화는 후보·코드 작성자와 독립된 최종 채점자가 아니다. 작성자의 opaque digest 확인을 CORE 전달 성공으로 계산하지 않는다.

기준 main의 PM `r5-public-independence-holds.20261007.v1`도 연결했다. 알려진 개발 노출3그룹(848850/776453/842682)은 평가후보36 안에는0, 시연후보49 안에는2다. 이들은 독립 평가/시연 승인 전에 본문 동등 그룹 전체를 제외하는 규칙이며, 원 연구 split을 수정하거나 36건의 의미 독립성을 승인한 기록이 아니다. 나머지 과거 lineage 검수와 런타임 적용도 남아 있다.

## 5 — 분모와 제외 건수

| 계산 항목 | 값 | 해석 |
|---|---:|---|
| 관측값 | 179 + 60 = 239 | 팩별 고정 원자료 |
| 중복 원 ID | 1 (`860977`) | 동일 SHA·정규화본문 확인 후 fixed18 항목 유지 |
| 고유 원 리뷰 | 238 | 중복 제거 후 ID별 1행 |
| 격리 제외 | 12 | 제품 불일치 등 기존 quarantine 유지 |
| 연구 분모 | 226 | 전체 고객/시장 모집단 비율이 아님 |
| 게시일 미상 | 고유238, 격리 후226 | 구매일을 게시일로 바꾸지 않음 |
| 격리∩게시일 미상 | 12 | 두 제외 사유를 단순 합산하지 않음 |
| 월별 제외 합집합 | 238 | 격리12 + 남은 게시일 미상226 |
| 월별 분모 | 0 | 유효 게시일 없음 |
| 주제별 분자·비율 | null | 승인 annotation 없음, 0/0 계산 안 함 |
| 정확 구매 SKU·모델 입력 적격 | 0 / 0 | page-only 연구 후기를 제품 사실로 승격하지 않음 |

10월 `[2026-10-01, 2026-11-01)` 및 겨울 `[2026-12-01, 2027-03-01)`은 Asia/Seoul 기준 빈 결과다. 날짜 경계의 정의는 명시했지만 실제 날짜가 있는 R5 입력으로 경계 동작을 검증한 것은 아니다. 과거 합성 날짜 경계 검사와 구분한다. 별점수 197/21/2/6의 합은 연구 분모226이며 이를 불만 주제 분자로 쓰지 않는다.

- [재계산·제외 합집합·기간](trend-recalculation.json)
- [238건 membership와 원문 연결](review-membership.csv): pin된 source 파일 + JSON pointer + 원 리뷰 ID + 공개 URL/locator + 원문 SHA
- [모델별 분모·eligible 원 ID](page-model-denominators.csv)

## 6 — 검수 가능한 저장 증빙과 제한

- [109개 응답 재대조](HTTP-recorded-body-audit.csv), [51쌍 전후 연결](restart-pairs.csv), [DB snapshot](DB-snapshot-audit.csv)
- [다른 모델/미등록 모델/잘못된 판본 거절](search-scope-audit.csv): 정상 항목의 ID·한국어 text·모델·판본은 고정 evidence21과 대조. 다른 유효 모델의 결과도 요청한 모델/판본으로 범위를 확인. 미등록/틀린 판본은 404/400, workspace 미등록 모델은422.
- [요약](capture-audit-summary.json): canonical reviews0, documents3/evidence21/features9. 연구 DB179는 작성자가 재생성해 원 선언 SHA와 일치했다고 기록한 범위다. 이 검수는 DB 바이너리를 받거나 재생성하지 않았다. combined238 운영 DB의 증명이 아니다.
- JSON 원 wire 파일이 없으므로 JSON103 검증은 파싱된 객체를 명시적 serialization으로 재구성한 결과다. 응답 선언 SHA와 일치하지만 실제 wire 파일 인수증을 대신하지 않는다. PDF 응답도 저장된 선언 SHA/크기를 원 PDF bytes와 대조한 범위다.
- [10개 PR219 소비 파일 SHA](consumer-version-audit.csv)는 선택된 파일에 한정된다. [전체 중요 범위 드리프트](capture-current-main-bridge.json)의 변경이 있으면 source8ec 캡처를 기준 main의 새로운 런타임 실행으로 표시하지 않는다. 원 PR219 schema source와 후속 schema의 차이도 PR226 원 기록에 보존돼 있다.

## 재현·기록

저장소의 기존 Git objects가 있는 checkout에서 `python evals/data456-acceptance-cross/20261007-01a1100e/audit.py`를 실행한다. 표/JSON은 이 폴더에만 쓰며 네트워크나 서비스에 접근하지 않는다. [verification-checks.json](verification-checks.json)은 이 작성자의 독립 파일 대조 결과이며 원 작성자의 584개 실행 assertion·1416개 연구 audit를 새 실행 횟수로 합산하지 않는다.

[PR226 manifest 바이트 대조](PR226-artifact-byte-audit.csv) · [작업 상세](작업기록.md) · [필요한 인계](인계요청.md). 정식 DATA005 보고는 #16, 동향 연결은 #148, 등록 무결성은 #13, 독립 평가는 #15다. 부분 인수·품질 승인·운영 배포·부모 Done은 각각의 실제 수신증으로 구분한다.
