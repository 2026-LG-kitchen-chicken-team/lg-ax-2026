# P2-DATA-005 — 날짜·주제 동향 집계기 부분 검증

상태: **개별 구현·검증 완료, PM 검수/공식 인수 대기.** 작업공간 collector에는 아직 연결하지 않았다. 여기 날짜가 든 결과는 테스트 전용 합성 입력이다.

## 원자료 보존과 sidecar

| 원자료 | 확인 결과 |
|---|---|
| `data/demo/dataset.json` | 버전 `0.1.0`, 리뷰 36건, 제품 모델 5종. manifest에 실제 고객 자료가 아닌 합성 개발 입력으로 명시됨. 파일 SHA-256 `97fe4b6badd54f3b64daf5e34f71033732e0e0b9d696d8bfc67b03b981512cf0`, 공통 계약용 canonical SHA-256 `8cbc9a492bd41f1112907a166744972501095aca49325630afbabe27b43b2c03`. |
| `data/research/P2-DATA-002-step1-20261005/reviews-v1.0.csv` | 기존 36행·8열을 그대로 보존. SHA-256 `3c7560aec2d3fa855590baf097b3514aa348ee40a77037c69ef358b413f488b9`. 원문, ID, 모델, 버전, 물리행, 근거 ID의 열을 추가·이름변경하지 않음. |
| `annotation.candidate.v1.json` | 36개 canonical review ID 전부를 별도 sidecar로 연결. published date가 없는 원자료에는 `null/unknown/null`을 기록. annotation SHA-256 `3939b5eec99f4637dec60a84802052577711ea8242718d296d0977c466afe5a8`. PM 채택 전 후보 분류다. |

주제 ID는 원문에 나온 주제 언급을 묶는다. `cleaning`, `temporary_storage`, `food_findability`, `manual_guidance`, `dish_loading_guidance`, `rotating_arm_clearance`, `heating_preset_management`를 썼다. 예를 들어 REVIEW-006은 청소가 쉽다는 긍정 문장이지만 `cleaning` 언급으로 분류했다. 계약에는 감정 극성이 없으므로 이 비율은 **불만·감정 비율이 아니다.** 따라서 실제 불편률이나 시장 수요로 읽으면 안 된다. topic taxonomy는 PM/CORE 의미 검토 전이다.

모든 `text_sha256`은 실제 canonical Review의 UTF-8 본문에서 계산한다. dedup key는 source kind·source ID·model·문서 버전·본문의 정확한 UTF-8 SHA를 조합하며 본문 정규화는 하지 않는다. 같은 원문 ID/근거 ID·모델·버전을 metadata에 그대로 연결했다.

## 구현·출력

`apps/api/src/lgax_api/review_trends.py`는 DATA collector 순수 구현이다. 승인 sidecar를 주입받아 `TrendCollection(aggregate, metadata, memberships)`를 계산하며, 요청 때 날짜/주제를 추론하지 않는다. source/model/version/text/evidence 결합, annotation/data 해시, 누락 in-scope 리뷰, 중복 본문 충돌, 기간, 집계 ID, 완전 `__all__`·topic membership을 검사한다. `create_review_trend_collector()`는 PM이 명시적으로 주입할 callable을 만든다. `workspace_trends`에 자동 연결하지 않았다. 현 main의 collector 기본값은 여전히 None이며 live API에서 501이 정상 경계다.

실제 기존 자료의 FRIDGE-A 10개 리뷰는 날짜가 전부 없다. 2026년 10월 집계 결과는 다음과 같다.

| input | scope 밖 | scope 안 | 날짜 없음 | 기간 밖 | 중복 | 유효 고유 | 분모 | cleaning |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 36 | 26 | 10 | 10 | 0 | 0 | 0 | 0 | `ratio=null`, 근거 ID 0 |

빈 bucket을 지우거나 0%라고 꾸미지 않았다. `computed-checkpoint.json`은 위 결과와 synthetic 날짜 테스트 결과·membership·오류 거부 사례를 고정한다. synthetic 결과의 review/evidence ID는 테스트용 별도 namespace다.

## 검증

실행 Python은 기존 `.venv`를 사용하고 새 설치는 하지 않았다. 실행 위치별 패키지가 섞이지 않도록 테스트 loader 앞에서 이번 worktree의 `apps/api/src`, `packages/contracts/src`, `packages/core/src`를 `sys.path` 우선순위로 지정했다.

| 범위 | 결과 | 한계 |
|---|---|---|
| `tests/test_review_trends.py` | 3건 통과. empty/null, KST 겨울 경계, 중복, 다주제 분모, 윤일, 원자료 변경 없음, 틀린 source/model/version·충돌 dedup 거부. 성공 세 결과에 `validate_trend_collection` 통과. | in-memory 날짜는 계산 회귀용 synthetic fixture. |
| `tests/test_review_import.py` | 10건 통과. 기존 scope/ID 거부 포함. 신규 NFC/NFD 테스트에서 본문 두 표기를 각각 보존하고 CSV 원 bytes·SHA-256도 일치. | 기존 CSV importer 경로 검사. CORE 생성 산출물 대조가 아님. |
| `tests/test_document_registration.py` | 10건 통과. cross-model/version·원문 변경/누락·원자 거부 회귀 포함. | 고정 JSON/PDF 시험 입력. 실제 세 제품 새 실행이 아님. |
| `tests/test_source_ranges.py` | 10건 통과. 등록된 source/version/range와 인용 범위 거부 회귀 포함. | 고정 fixture. 실제 Daegyeom 결과의 citation audit가 아님. |
| `tests/test_workspace_trends.py` | 22건 실행. TestClient의 집계·원문 조회와 HTTP/MCP mock 호출이 200으로 실행됐지만, Windows 임시 디렉터리에서 열린 SQLite 파일을 지우지 못한 teardown 오류 5건으로 전체 명령은 실패했다. 통과로 계산하지 않는다. | 기존 synthetic fixture collector 경로다. 이번 승인 sidecar 주입이나 운영 서비스 검증이 아니다. |

전체 test suite, 외부 호스트, production collector wiring은 실행하지 않았다. API/MCP gateway 테스트는 로컬 TestClient·mock 경로만 실행했다. 이 결과는 구조·집계 검사이지 PM 승인이나 실리뷰 날짜의 증명이 아니다.

## CORE 고정 결과물 원문 대조 — #13

황대겸이 2026-10-06 16:54에 기존 고정 출력과 정확한 source/review ID를 #13에 인계했다. 새 모델 호출 없이 commit `9c7188a29138f43b377c2cac763ab954bc802330`의 세 결과를 `data/demo/dataset.json`의 실제 한국어 문자열·source ID·모델·문서 버전·locator와 대조했다. 모든 원입력 source row가 dataset과 byte-exact UTF-8 text/locator까지 일치했지만 결과의 판단/인용 연결에는 아래 이슈가 있다. 상세 표·파일 SHA는 [`P2-DATA-002-fixed-output-audit-20261006/result-comparison.md`](../P2-DATA-002-fixed-output-audit-20261006/result-comparison.md)에 기록했다.

| 고정 결과 | source 결합 | 확인된 원문 대조 문제 | 기존 상태 |
|---|---|---|---|
| qwen3:8b 냉장고 | 11/11 exact; FRIDGE-A 1.0 synthetic | 8개 명시 불편을 `positive`로 평가. NEED에서 REVIEW-EVIDENCE-009·010 누락. 식품 위치/가족 표시 불편까지 선반 분리 FEATURE-001에 연결. | failed; 9 calls, 2 revisions, independent quality null |
| qwen3:8b 전자레인지 | 4/4 exact; MICROWAVE-A 1.0 synthetic | NEED-001은 REVIEW-EVIDENCE-034만 인용하지만 세 GAP이 034·035·036을 모두 재사용. 저장 기능 인지도/호출 버튼 찾기 문제에 별도 NEED가 없음. | failed; 9 calls, 2 revisions, independent quality null |
| qwen3.5:27b 냉장고 | 11/11 exact; FRIDGE-A 1.0 synthetic | REVIEW-EVIDENCE-005의 바구니 세척을 shelf-only MANUAL-001이 뒷받침하는 것처럼 연결. REVIEW-EVIDENCE-009의 청소 미루기와 shelf-removal 간 인과는 원문에 없음. `duplicate` 판정과 차별화 이유도 상충. | held; 3 calls, independent quality null |

세 결과는 모두 합성 데모 자료이며 실제 LG SKU/고객 리뷰의 근거로 확장하지 않는다. PR [#166](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/166)은 별도 원문 비교 자료, [#167](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/167)은 private 인계 metadata 작업이다. 두 PR의 병합을 #13의 원문 교차거부/한글보존 회귀 또는 의미 검수 통과로 보지 않는다. #15 `review requested`도 승인이나 전달 완료가 아니다.

독립 대조 표를 완성하려면 황대겸 CORE의 **기존 고정 결과 JSON, 각 결과의 source/review/evidence ID, model/document version, 근거 locator와 고정 commit/hash**가 필요하다. 기존 결과를 재생성하거나 판단 코드를 중복 수정하지 않는다. 받은 뒤 결과별로 인용 일치·기능 설명 일치·빠진 근거·제품/모델/버전 혼입을 원문과 맞춰 대조한다. 이 파일의 synthetic 결과를 CORE 출력으로 대신하지 않는다.

다음: @unknownamed가 기존 고정 출력을 정확한 원문 ID와 함께 연결하고, @jeongiryang이 sidecar/topic taxonomy의 승인 및 PM-controlled collector 주입 위치를 지정한 뒤 실제 승인 경계에 맞춰 인계한다. PR·issue 자체 보고가 공식 accept/Project 상태 변경을 뜻하지 않는다.
