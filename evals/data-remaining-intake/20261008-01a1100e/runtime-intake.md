# #13 새 R8 운영 인계 검토 — 2026-10-08

기록 ID: `DATA-R8-RUNTIME-INTAKE-20261008-01a1100e` · GitHub 확인: **2026-10-08 00:38 KST** · 상태: **UNCONFIRMED**. 고정 생산팩과 P0 계약은 수신했지만 실제 운영 원응답·DB export·재시작쌍은 이 감사에 인계되지 않았다. 자료 불일치가 확인된 FAIL은 아니다. 기계 판독 항목은 [runtime-intake-requirements.json](runtime-intake-requirements.json)에 보존한다.

## 실행 보고와 직접 검수 범위

| 근거 | 확인한 사실 | 이번 독립 검수의 한계 |
|---|---|---|
| [PM PR245](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/245), head `5fdb3ad55349726fbe03c9f69651f895d73e8f10` / 병합 main `ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f` | PM이 실제 모델12호출, 정상·조건변경·국소수리 저장 흐름5회와 공식자료 고의 제외 CORE1회, API/MCP 저장·재조회를 보고했다. [병합 인수](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/245#issuecomment-6039652489)도 존재한다. | PM 실행이 없었던 것으로 기록하지 않는다. DATA가 직접 대조할 운영 raw export·재시작쌍은 미수신이며 부모 Done/의미 품질 승인과 구분한다. |
| [PR226](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/226), head `06701a5979920abb6d18da039056b64af6c84df9` | source `8ec1e8a51faabd6db032e52245680bef4229f93f`의 격리 HTTP109(JSON103/PDF6), 재시작51쌍·DB snapshot이 저장돼 있다. | 새 R8 운영 또는 새 care팩 소비 증명이 아니다. |
| [PR227](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/227), 최종 head `bc7a164fe6687a0d6303a289c4301aab11536c82` | 저장된 PR226 격리 기록의 독립 대조가 완료돼 있다. | [원 #13 보고](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/13#issuecomment-6030700759)의 raw JSON wire 파일·SQLite binary 미수신 및 최신 런타임 승계 제한을 유지한다. 재실행하지 않았다. |
| [새 PR254](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/254), head `94b560de72f91795cfd50aada9e17d6773383ae1` | D1·D2 생산팩과 관리14 Source가 올라왔다. P0 pin은 `ef29aa8`, 원자료 pin은 `58feb9c30fc5faae1cc8acfb0ff409106a6d7174`다. | [current-delivery](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/94b560de72f91795cfd50aada9e17d6773383ae1/evals/data-d1-d2/20261007-01a10600/current-delivery.json)는 생산 범위의 runtime 실행 및 canonical/care 등록을 false로 명시한다. 운영에 실제 선택된 묶음은 미확인이다. |

이전 요청의 **P0 규격 미수신**은 현재 막힘에서 제외한다. 남은 막힘은 실제 소비 캡처와 운영 인수다. [#234의 이전 인계 요청](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/234#issuecomment-6038212910)은 당시 기록으로 보존한다.

## 새 생산팩의 고정 ID·SHA

아래 세 파일을 PR254 고정 head의 GitHub Contents API에서 base64 원바이트로 읽고 Python `hashlib.sha256`으로 계산했다. receipt의 SHA와 같다. 생산기/D4 감사기/모델/OCR은 실행하지 않았다. 이 확인은 파일 인계 범위이며 표본·분할·Excel D4 전체 감사나 운영 등록 통과를 대신하지 않는다.

| 제품군 | 고정 bundle ID | Source / 후기 | SHA256 |
|---|---|---:|---|
| 냉장고 | `LGE-D1-D2-fridge-20261007-01a10600-v1` | 58 / 48 | `75423a9844a468ad5e64e9086e43b68649335faf0c7c68b82f3a949ebf6bf4dc` |
| 식기세척기 | `LGE-D1-D2-dishwasher-20261007-01a10600-v2-care` | 73 / 48 | `e922c51dd7f1f805953fd8e4df4ea1a75479ad8da0e2ba500b541acd720e84d0` |
| 전자레인지 | `LGE-D1-D2-microwave-20261007-01a10600-v1` | 53 / 45 | `457461ebd8cf13a1be6b171ed1a80802d33ed3b5714118179afef11ce1b87a5d` |

고정 원파일: [냉장고 bundle](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/94b560de72f91795cfd50aada9e17d6773383ae1/data/research/r8-public-research-20261007/d1-d2-01a10600/agent-input/fridge/research-bundle.json), [식기세척기 bundle](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/94b560de72f91795cfd50aada9e17d6773383ae1/data/research/r8-public-research-20261007/d1-d2-01a10600/agent-input/dishwasher/research-bundle.json), [전자레인지 bundle](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/94b560de72f91795cfd50aada9e17d6773383ae1/data/research/r8-public-research-20261007/d1-d2-01a10600/agent-input/microwave/research-bundle.json).

합계는 Source184·개발 후기141이다. 식기세척기 `D2-DUE-CARE-DW-*` 14 Source는 판본 `MFL71959117 Rev.07_030626`, PDF SHA `ff60f78ab8326c40b9a3446f11b49531b8f0c823a310ba98366716b633ba63f5` 및 native 쪽/start/end locator를 가진다. full Source ID와 PDF 단위 source ID는 [care index](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/94b560de72f91795cfd50aada9e17d6773383ae1/data/research/r8-public-research-20261007/d1-d2-01a10600/d2-care-evidence-index.json)에서 구분한다. 입력에 구간이 존재한다는 사실은 운영 소비, 정확 구매 SKU, 고객의 원인·호전 확인을 뜻하지 않는다.

## 세 저장 범위의 구분

| 범위 | 확인한 구조 | 필요한 운영 대조 |
|---|---|---|
| 생산 연구 landing DB | [D1 manifest](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/94b560de72f91795cfd50aada9e17d6773383ae1/data/research/r8-public-research-20261007/d1-d2-01a10600/d1-delivery-manifest.json)는 `research-238.sqlite3` / SHA `6a01e8e3e2a18b7325abf068e15cf8d17f5e72a6b4a8f3ec4776a3c4065ab8fd`를 새238행·local/private 연구 DB로 선언한다. 이번 감사는 DB binary를 인수하지 않았다. | 운영 app DB와 동일하다고 승계하지 않는다. 실제 선택한 저장·소비 경로와 record export를 받아 producer 원문/ID/버전에 대조한다. |
| 파일 기반 ResearchBundle | [고정 API 코드](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f/apps/api/src/lgax_api/research_planning.py)의 `ResearchWorkspace`는 파일 bytes를 읽고 검증·SHA 계산 후 메모리에 보존한다. `/api/research/bundles`와 `/bundles/{bundle_id}`가 이를 반환한다. | 실제 loaded bundle ID·파일 SHA와 원 GET/MCP 응답을 비교한다. bundle GET에 model/version 검색 인수는 없으므로 존재하지 않는 필터 거절을 검증했다고 쓰지 않는다. |
| 운영 run DB | 같은 코드가 SQLite `research_runs`, `research_attempts`에 실행·attempt snapshot을 저장하고 `/api/research/planning-runs/{run_id}`에서 저장 brief를 공개 projection으로 반환한다. | 같은 run/bundle ID·digest·brief/source 참조와 운영 DB export·전후 GET을 연결한다. 원 private row와 공개 projection의 범위를 구분한다. |
| 기존 등록 문서/근거 | `/api/documents`와 evidence 경로가 실제 운영 경로에 포함되는지는 PM이 명시해야 한다. | 포함됐다면 metadata/original/evidence/scoped-search 원응답도 대조한다. 이 경로만으로 새 care14 ResearchSource의 소비를 증명하지 않는다. |

## PM에게 필요한 인계와 현재 상태

책임: **PM 정이량 `@jeongiryang`**. CORE 황대겸 `@unknownamed`은 같은 고정 run/source 매핑을 소비한다. 기존 결과에서 제공 가능한 비밀 없는 export 또는 승인된 읽기 경로로 인계한다. 토큰·접속정보·개인정보·원 private 로그를 일반 GitHub 댓글에 받지 않는다.

| ID / 필요한 인계 | 원응답·DB export | 재시작 전후 | PM 인수 |
|---|---|---|---|
| R13-01 운영 선택 pin·승인 읽기/export 범위 | 실제 producer/consumer commit, loaded bundle ID·SHA 및 PR254 v2-care 채택/미등록 상태 **미수신** | 같은 DB·loaded 자료 설정 연결 **미확인** | 새 care팩 운영 범위 **미확인** |
| R13-02 ResearchBundle API | GET list/각 bundle의 method/path/params/status/시각·원응답 파일·byte SHA **미수신**. full Source ID·한국어 text·page_model/purchased_model·판본·locator·facts·metadata 및 null 보존 | 같은 조회의 before/after 파일쌍 **미수신** | 캡처 범위/자료 선택 확인 필요 |
| R13-03 같은 서버 MCP | 기존 `list_research_bundles`/`get_research_bundle` 및 관련 `get_research_run`의 인수·원결과·SHA **미수신** | 대응 전후 조회쌍 또는 명시적 미확인 범위 필요 | HTTP/MCP의 bundle/run/source 대응 확인 필요 |
| R13-04 원파일·저장 경로 매핑 | loaded bundle·원 PDF/CSV의 전체 SHA/ID/판본, 파일/연구DB/run DB 연결 **미수신**. legacy 등록을 사용했으면 그 원응답도 포함 | 같은 원파일/ID의 전후 보존 **미수신** | 실제 등록 경로·범위 확인 필요 |
| R13-05 실제 운영 DB | 관련 record/schema snapshot 및 run_id/bundle_id/bundle_sha256/brief 참조 export **미수신**. 필요한 경우 일관된 owner 가명과 비공개 범위 명시 | 같은 DB의 논리 행·스키마 snapshot 전후 **미수신** | DB 정체성/export 범위 확인 필요 |
| R13-06 재시작 receipt | 확보된 기존 재시작 receipt·시각·비밀 없는 설정/source pin **미수신** | 원문·ID·해시·판본·run 대응쌍 **미수신**. 파일 byte hash와 DB 논리 행 hash를 구분 | 실제 재시작/보존 인수 **미확인** |
| R13-07 제품·버전 선택/오연결 | 실제 지원하는 인터페이스의 정상/다른 제품/다른 버전 원요청·응답 **미수신**. bundle ID→product_group·source 모델/판본 매핑부터 대조 | 지원된 같은 scope 조회 전후쌍 필요 | 실제 scope 계약·관측 결과 확인 필요 |

수령 후 생산 파일을 수정하지 않고 고정 운영 출력만 독립 대조한다. 원응답이 없으면 미확인으로 유지하며, 준비·CI·자료형식 통과를 운영 인수나 #13 Done으로 바꾸지 않는다. 새 서비스 등록·모델 실행·재시작을 이 문서 작성 과정에서 요청하거나 수행한 것은 아니다.

## 다른 사용자 창과 작업 경계

**#14 자동 구조 출력 검수와 #148 동향 검수·sidecar 생성은 다른 사용자 창에서 진행 중이므로 보류한다.** 이 기록은 #13의 원응답 인계 범위만 정리하며 D1·D2 생산/D4 감사 파일을 수정하거나 그 프로그램을 실행하지 않는다. 새 두 파일 외 기존 코드·자료·개인 README 변경0, 모델/OCR·운영 HTTP·DB 생성/수정·서비스 재시작0, GitHub 게시0이다. 읽기 전용 GitHub API 조회와 고정 파일 SHA 계산은 수행했다.
