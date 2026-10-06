# 신진하 — 고정 결과 원문 대조와 리뷰 동향 collector 부분 제출

- 기록 ID: `신진하-20261006-DATA-ORIGINAL-AUDIT-TRENDS-01a1100e`
- 근거 ID: `신진하-E-DATA-ORIGINAL-AUDIT-TRENDS-01a1100e`
- 담당/AI: 신진하 / Codex
- 작성일: 2026-10-06 17:34 KST
- 기준 main: `531e2be` (`origin/main`, PR #171 PM closeout 반영)
- 작업 branch: `codex/data005-review-trends-20261006`

## 사용자 지시와 해석

사용자는 10/6 14:12 배정된 자료·검색 점검을 수행하고, 자료 ID/제품/모델/버전 오혼입 차단과 한글 원문·파일 보존을 확인하며 황대겸의 **고정 결과**를 원문별 표로 대조하라고 지시했다. 판단 코드를 중복 수정하거나 같은 모델 생성 작업을 반복하지 않는다. 추가로 기존 리뷰 36건과 8열 CSV를 보존하는 날짜·주제 집계기를 구현하고, 날짜 누락·빈 결과·중복·날짜 경계·계산 오류를 검사한다. 작업은 코어 전체 승인을 기다리지 않고 #148과 연결하며, 공식 진행 보고는 #16에 남긴다. 18:00 KST는 내부 운영 목표다.

이번 진행에서 알게 된 변경: #13에 황대겸이 16:54 KST 기존 고정 결과 3개를 source/review ID와 함께 전달했다([댓글 6011902780](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/13#issuecomment-6011902780)). 따라서 세 산출물은 다시 실행하지 않고 직접 대조했다. #13의 가장 최근 자료 담당 보고(16:56, [댓글 6011937003](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/13#issuecomment-6011937003))는 다른 작업 소유자의 활성 예약과 HTTP 409를 기록하고 있다. 해당 예약/작업 이력은 변경하지 않았으며, live 등록·검색·재시작 검증은 진행하지 않았다.

사용자가 제공한 #15 상태는 16:07 `review requested`이며 통과 판정이 아니다. PR #167은 이후 main에 병합됐지만, 고정 attestation은 `external_transfer_complete=false`; #13 R1 의미 검수나 실제 외부 전달 승인으로 읽지 않는다. PR #166도 DATA003 원문 비교/기존 점수 재계산 산출물이며 #13 등록/search 회귀 통과를 대신하지 않는다.

최신 main의 PR #171 closeout은 API/MCP 소비 경로 10개 검사를 `consumption_path_ok`로 기록한다([api-mcp-path.json](../../../../evals/pm-prototype/20261006/closeout/api-mcp-path.json), [validation.json](../../../../evals/pm-prototype/20261006/closeout/validation.json)). 단, 사용된 `FixtureCollector`는 DATA #148 구현이 아니며, `actual_DATA_collector=false`, `actual_customer_dates=false`, `planning_accept=false`, model calls 0이다. 픽스처 집계의 9건 undated/1건 eligible은 그 테스트 결과일 뿐이며, 현재 저장소의 실제 36건은 날짜 0건 보유로 집계 결과 0건이다. 두 결과를 합치거나 실자료 연결 완료로 간주하지 않는다.

## 고정 결과별 원문 대조

세 고정 결과의 `original_input.sources`를 실행 원본 commit `45fe0f23afb9c68e115088cef9e10cd122d181f1`의 `data/demo/dataset.json`과 대조했다. ID/evidence ID, source type, 제품 model ID, 문서 version, source kind, source ID, locator, 한국어 원문 모두 일치했다. 결과별 정량 및 판단 비교표는 [result-comparison.md](../../../../data/research/P2-DATA-002-fixed-output-audit-20261006/result-comparison.md), SHA/실행 metadata는 [manifest.json](../../../../data/research/P2-DATA-002-fixed-output-audit-20261006/manifest.json)에 있다.

| 고정 결과 | 자료 identity | 결과 대조와 누락/오류 |
|---|---|---|
| qwen3:8b 냉장고 | 11/11 exact. `FRIDGE-A`, 문서 1.0, synthetic. `MANUAL-001` p.1 §선반 분리 + 리뷰 001~010 행2~11. | 명시 불편 8개(001~005,007,009,010)를 `positive`로 분류했다. 009·010은 NEED/GAP에서 누락되고, 희망만 적힌 008은 NEED로 승격됐다. 모든 GAP이 shelf FEATURE-001에 연결돼 findability/family 표시/basket 범위를 섞었다. `failed`, validator `NON_COMPLAINT_AS_NEED`/`ASSESSMENT_COVERAGE`, independent quality null. |
| qwen3:8b 전자레인지 | 4/4 exact. `MICROWAVE-A`, 문서 1.0, synthetic. `MANUAL-005` p.5 §설정 저장과 호출 + 리뷰 034~036 행35~37. | NEED-001은 034만 인용하지만 GAP-001~003 모두 034·035·036을 공유한다. 035(저장 기능 인지)와 036(호출 버튼 탐색)의 별도 NEED가 없고, 설정 저장 후 원터치 호출 기능(MANUAL-005)과 discoverability를 분리하지 않았다. `failed`, independent quality null. |
| qwen3.5:27b 냉장고 | 11/11 exact. `FRIDGE-A`, 문서 1.0, 같은 합성 냉장고 자료. | 8개 불편을 `positive`로 분류. unsupported로 둔 GAP-003/006은 shelf 설명서와 무관함을 맞게 구분했다. GAP-005는 basket 세척을 shelf-only 매뉴얼로 지지하고, GAP-007은 청소 미루기와 선반 제거 지시 사이 원문에 없는 인과를 암시한다. 세 concept에서 `duplicate` 판정과 차별화 사유가 상충한다. `held`, independent quality null. |

세 결과 모두 원 ID/source/model/version 교차 혼입은 발견하지 못했다. 의미 층에서는 인용이 존재하는 것만으로 기능 지원·불편 원인·gap 판정을 확정할 수 없음을 확인했다. 이 출력들은 `source_kind=synthetic`이고 36개 synthetic demo 자료이므로 실제 LG SKU 설명서/고객 리뷰 품질이나 독립 평가 결과로 확대하지 않는다. 모델 digest, fixed output bytes, 입력 파일·CSV 해시는 근거 manifest에 보존했다. 새 모델 호출은 0이다.

## 날짜·주제 집계기 부분 구현

`apps/api/src/lgax_api/review_trends.py`에 승인 sidecar를 받아 `TrendCollection(aggregate, metadata, memberships)`을 만드는 결정적 DATA collector를 추가했다. 공통 validation, `trend_identity`, `trend_periods`, `trend_sample_warnings`를 재사용하고, source/review/model/version/text hash/evidence를 묶는다. 누락된 in-scope row, 틀린 source/model/version, conflicting duplicate text, 중복 annotation을 거절한다. 완료된 bucket마다 분모 `__all__`과 주제별 **완전 Evidence ID 목록**을 함께 낸다. PM이 주입 callable을 명시적으로 연결하도록 factory만 제공했다. Workspace server/API/schema/MCP/판단 코드는 수정하거나 자동 연결하지 않았다.

| 입력/계산 | 결과 |
|---|---|
| 현재 원자료 | `data/demo/dataset.json` 36 reviews; 실제 날짜 0. source kind synthetic. 파일 SHA `97fe4b6badd54f3b64daf5e34f71033732e0e0b9d696d8bfc67b03b981512cf0`, canonical SHA `8cbc9a492bd41f1112907a166744972501095aca49325630afbabe27b43b2c03`. |
| 기존 CSV | `reviews-v1.0.csv` 36 rows/8 columns 그대로; SHA `3c7560aec2d3fa855590baf097b3514aa348ee40a77037c69ef358b413f488b9`. 원본 review/CSV의 한글 bytes를 바꾸지 않았다. |
| 실제 원자료 FRIDGE-A 2026-10 | input 36, out-of-scope 26, in-scope 10, undated 10, outside 0, duplicates 0, eligible unique 0, `total_reviews=0`, cleaning `ratio=null`, evidence IDs 빈 배열. 빈 분모를 0%로 만들지 않았다. |
| test-only synthetic winter | KST `[2026-12-01,2027-03-01)` 겨울2026, 경계 UTC 시각 둘을 KST로 옮기고 중복 1건 축약: scope10, undated6, outside2, duplicate1, unique1, denominator1, cleaning1. `TREND-EVIDENCE-001`이 bucket/topic/full membership에 연결됨. |
| test-only 윤일/multi-topic | 2028-02-29 case: denominator 1, 두 topic ratio 각 1, 같은 evidence ID `TREND-EVIDENCE-003`을 `__all__`/topic membership에서 원문 evidence로 연결. |
| 오류 회귀 | source ID, model ID, document version 혼입 및 같은 dedup key의 서로 다른 원문을 거절. 성공 출력은 common `validate_trend_collection`을 통과. |

날짜 없는 36건에는 날짜를 만들지 않았다. `annotation.candidate.v1.json`에는 각 row를 original review/evidence ID 및 본문 SHA와 연결하고 published date를 null/unknown/null로 두었다. 이는 PM/CORE 승인 전 후보이며 주제 taxonomy도 승인되지 않았다. topics는 mention grouping이고 polarity를 포함하지 않으므로 complaint ratio/수요 지표가 아니다. 실제 원문 날짜의 출처 파일/URL/hash/locator 증빙이 승인돼야 집계에서 사용할 수 있다.

## 실행 검증

기존 `.venv`를 사용했고 새 환경을 설치하지 않았다. 최신 main은 실행 전 `origin/main`으로 다시 확인했다. loader에 이번 worktree의 API/contracts/core 경로를 앞세워 테스트를 실행했다.

| 실행 | 결과 |
|---|---|
| `tests/test_review_trends.py` | 3 passed: 빈 분모, KST 겨울, 중복, 다주제 분모, 윤일, 잘못된 binding/dedup, 원자료 hash 보호 |
| `tests/test_review_import.py` | 10 passed: NFC/NFD 각각 보존, CSV bytes/hash 불변 |
| `tests/test_document_registration.py` | 10 passed: model/version/raw-source mismatch 원자 거부 회귀 |
| `tests/test_source_ranges.py` | 10 passed: 등록된 source/version/range 및 인용 범위 회귀 |
| 기존 `tests/test_workspace_trends.py` | 22 실행. test assertions 중 HTTP/MCP mock 및 evidence request가 200으로 실행됐으나 Windows `TemporaryDirectory` cleanup 시 열린 `workspace.sqlite` 삭제 오류가 5건 발생해 명령은 `FAILED (errors=5)`. 성공으로 집계하지 않는다. 이 테스트는 기존 synthetic fake collector 경로이며 이번 DATA sidecar collector나 production injection을 검증하지 않는다. |

그 뒤 최신 main PR #171의 별도 PM closeout은 Docker validator에서 변경 파일 0, model calls 0, `FixtureCollector`로 API/MCP 10개 소비 경로 검사를 통과시켰다. 이는 기존 픽스처 수집기의 연결 검사이며 DATA collector·실제 날짜·production injection 검증은 아니다. 그래서 로컬 Windows teardown 오류를 성공으로 덮지 않고, 픽스처 검증도 이번 collector에 대한 통합 증거로 확대하지 않는다.

33개의 focused DATA tests는 통과했다. 전체 suite, live API/외부 MCP host, 운영 DB 주입, 실제 upload→search→restart는 수행하지 않았다. 두 차례 실행한 workspace trend 테스트는 Windows teardown 실패가 있어 최종 status에 그대로 남겼다. UI 패널/정식 issue status는 변경하지 않았다.

## 막힘과 역할별 다음 행동

1. **CORE — @unknownamed:** 고정 출력 semantic comparison의 polarity/evidence mapping 결과를 확인하고 judgement code/Skill 수정을 맡는다. DATA는 판단 코드 중복 편집이나 기존 generation 재실행을 하지 않는다. 27B proposal은 기존 기능 판정이 아니라 proposal로 구분돼야 한다.
2. **PM — @jeongiryang:** #13의 16:56 report에 있던 active manual-work reservation/409가 해소됐는지 확인하고, 해소 후에만 live source registration/search/restart 검증 경로를 지정한다. candidate topic taxonomy/sidecar를 승인 또는 수정 지시하고 `create_review_trend_collector()`를 어느 PM-controlled runtime에 주입할지 확인한다. #16 본문은 “PM 미채택 확장” 상태로 보이지만 최신 DATA assignment는 #16/#148을 진행 지시하고 있어, issue adoption/official receipt 경계를 정리해야 한다. #15의 review request는 별도 검수로 남긴다.
3. **WEB — @choigilung:** PM approval 이후 동일 aggregate ID와 `memberships` Evidence ID를 소비하고, evidence drilldown에서 고정 당시 원문/locator로 연결되는 fixture/API 흐름을 맞춘다. 지금 결과는 collector/API `None` 경계를 넘지 않는다.

목표는 오늘 18:00 KST까지 부분 PR·근거 또는 막힘을 연결하는 내부 기준이었다. 이 기록은 역할별 수신 요청이며 PM 인수/전체 과제 Done/실제 호스트 연결 보고가 아니다.
