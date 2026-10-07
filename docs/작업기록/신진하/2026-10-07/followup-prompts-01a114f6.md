# 신진하 DATA 후속 병렬 작업 프롬프트

사용자 요청에 따른 제안이다. 실제 배정·착수·완료를 대신하지 않는다. D1·D2 생산은 LGAX #12, D3·D4는 세션01a114f6, P0/R8 공통 소비·운영 인수는 조정 창/PM 담당이다.
3창이면 A/B/C를 각각 맡기고, 2창이면 A/C를 먼저 진행한 뒤 B를 후속으로 배정한다. 각 창은 아래 세 작업을 순서대로 수행한다.

## 공통 시작 문장 — 각 프롬프트와 함께 복사

신진하/ginaginaring의 DATA 후속 수동 작업이다. 최신 AGENTS.md/CLAUDE.md, 승인된 본인 LG 관련 메일, #234와 담당 Issue, 본인 재개 기록을 먼저 읽고 현재 상태에서 이어가라. 현재 D1·D2/D3·D4/조정 창의 고정 head·산출물·편집 경계를 확인하고 중복된 작업은 원 결과를 인수한다. 고유 session ID와 별도 codex/ 브랜치·작업 공간을 사용한다. 아래 자기 폴더와 자기 날짜별 고유 기록/근거 파일만 수정한다. 개인 README와 공통 문서는 단일 기록자에게 요약/링크를 인계하고 동시 편집하지 않는다. 공통 Schema/API/MCP/CORE 판단/WEB/PM 큐와 D1·D2 생산 파일은 읽기 전용이다. 저장소 검사는 별도 source 복사본의 network=none/auth=none 격리 환경에서 수행한다.

PM의 [R8 PR245](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/245)는 새 ResearchBundle/PlanningBrief 계약·소비·양면 요약/시각 기획과 D3 공식 발췌12개 adapter를 구현했다고 보고했다. 착수 시 최신 고정 head·실제 병합/운영 상태·본인에게 인계된 파일을 확인하고 구현된 부분은 재사용하라. 예전 legacy source_type 제한을 이유로 공통 계약이나 양면 요약을 다시 개발하지 마라. DATA는 원문 대조·수신·버전/분모·독립 인수의 남은 범위에 집중한다.

실제 공개 자료만 사용하고 구매 SKU·게시일 미상을 추정하지 않는다. 합성 리뷰, Figma, 자동화 재활성화, 추가 유료 호출, 기존 모델/OCR/완료 검사 반복은 하지 않는다. 새 변경·새 입력·미완료 인수에 필요한 확인만 수행한다. 지시 원문과 해석·실제 행동·실패/미수신·한계를 분리해 기록한다. 한 작업의 검토 가능한 결과가 완성될 때마다 작은 PR을 올리고 URL·head·검사·미완료를 보고한다. PR은 이 사용자 지시로 승인됐으며 main 병합/정식 Done은 PM이 판정한다.

## 창 A — 실제 입력 전달과 수신 증거 (3작업)

담당 Issue #15의 CORE 인계와 관련 DATA 전달을 진행하라. 수정 범위는 evals/data-input-delivery/{session}/, 본인 날짜별 고유 기록, 기존 승인된 비공개 DATA 전달 영역의 자기 새 폴더다.

1. CORE의 [실제 input-only 미수신 요청](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/227#issuecomment-6030764591)을 최신 회신과 대조하라. 기존 input-only ZIP의 SHA·11엔트리·사례/제품군/모델/판본/원문 범위를 고정하고, reviewer-only/Gold/답안/방식키가 없는지 확인하라. 기존 승인된 비공개 경로의 정확한 입력이 없으면 빠진 파일·원 SHA·소유자·다음 행동을 남기고 원문을 임의 재생성하지 마라.
2. 동일한 고정 입력을 기존 승인된 무료 비공개 전달 경로로 인계하고 CORE가 실제 받은 ZIP SHA·바이트·엔트리 수의 수신 증거를 대조하라. 실제 전달이 필요한 경우 GitHub의 해당 담당 Issue에서 정확한 인계/수신 확인을 요청한다. prepared·outbox·opaque SHA 일치를 실제 상대 수신으로 기록하지 마라. Gold/원평가 자료를 일반 PR/Issue나 CORE 개발 대화에 공개하지 마라.
3. 고정 코드/자료/판본/입력 SHA와 동일 Agent·일반 LLM 원출력/전체 사용량 수신 여부를 목록으로 연결하라. 기존 모델을 다시 호출하거나 채점 기준을 완화하지 마라. PM의 실제 실행/검수와 CORE의 수신 판정은 각각 별도 상태로 남겨 전달 단위 PR을 제출하라.

## 창 B — 개발용 주제 근거와 WEB 동향 인계 (3작업)

담당 Issue #16/#148의 남은 자료 근거를 진행하라. 수정 범위는 data/research/r8-public-research-20261007/trend-annotations/{session}/, evals/data-trend-handoff/{session}/ 및 자기 고유 기록이다.

1. D1 고정 version/manifest/ID membership을 인수하라. 전체 연구 관측·격리 제외 연구·개발용 subset의 분모를 구분하고 source_url·원문 SHA·원 분할을 유지하라. 주제 annotation을 만들 때는 development만 읽고 독립 평가·시연·Gold는 보지 마라. 장점/불편/혼합/불명, 제품 사용/배송·설치/케어를 분리한 검토용 draft를 원 ID·정확 인용·반례와 연결하라. vendor 요약 제목을 개별 리뷰 정답으로 복사하지 말고 승인 상태는 pending으로 남겨라.
2. 기존 review-trends의 완료된 집계/필터를 재사용해 고정 membership·producer version·SHA sidecar를 준비하라. 실제 published_at이 없으면 월/계절 시계열을 생성하지 말고 날짜 미상 제외·분모0·ratio null을 그대로 보존하라. 구매일을 게시일로 바꾸지 말고 선택 표본의 건수를 시장 수요 비율로 해석하지 마라.
3. [WEB의 동일 버전 집계 요청](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/227#issuecomment-6030715222)에 producer/version·sidecar SHA·ID membership·분모·제외 수·원문 연결을 고정 파일로 인계하라. 이 인계는 GitHub의 담당 Issue/PR에서 정확히 요청할 수 있다. 운영 DB/API/MCP 재시작/배포와 웹 코드는 조정 창/PM/WEB 담당으로 유지하라. 승인되지 않은 주제 비율이나 실제 화면 확인을 완료로 만들지 말고 세 단위를 작은 PR으로 제출하라.

## 창 C — PDF 표 구조·원문 범위·CORE 소비 자료 (3작업)

담당 Issue #14의 [CORE 표 근거 요청](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/14#issuecomment-6030572022)을 진행하라. 수정 범위는 data/research/r8-public-research-20261007/table-grounding/{session}/, evals/data-table-handoff/{session}/ 및 자기 고유 기록이다.

1. 정확한 기존 PDF SHA·판본과 DUE6BGL2E p57/MW23FDI p37의 첫 두 페이지 출력을 인수하라. 기존 파서/OCR 원 결과가 있으면 재사용하고, 없는 실제 graph/producer 출력과 source pin을 정확히 요청하라. 헤더→제품 열→치수 셀 및 소비전력→고주파 출력→각주의 실제 연결을 위치·단위·쪽·셀 관계로 보존하라. 자동 출력이 없으면 원문/기대 셀 대응 준비만 했다고 기록하고 자동 추출 성능을 주장하지 마라.
2. cell graph와 canonical Evidence 대응을 별도 producer sidecar로 작성하라. DUE의845/815mm 열을 섞지 말고, MW의1570W 소비전력과1000W*1 출력/짧은 시간 각주를 분리하라. 연속 원문 [start_char,end_char)와 모델/판본을 유지하고 떨어진 셀·각주를 합친 문장을 기존 연속 인용으로 위장하지 마라. Evidence 추가 필드는 넣지 말고 별도 관계 JSON에 cell_id를 둬라.
3. 기존 공개 PDF와 신규 sidecar의 원문 범위·해시·헤더/단위/각주 대응 및 결손/상충 사례를 독립적으로 대조하라. feature_ids가 비어 있는 근거를 자동 기능 지원으로 바꾸지 마라. 고정 출력·실패·미확인을 CORE/PM에 GitHub 담당 Issue/PR로 인계한다. 공통 계약/CORE 어댑터 변경과 신규 모델/OCR 비교는 맡지 않고 자료 단위별 PR을 제출하라.

## 뒤로 둘 작업

X2/#240의 김치냉장고·광파오븐 확장은 PM P2 첫 사용자 테스트/프로토타입 인수 뒤 진행한다. 지금의 세 창은 미전달 입력·미승인 주제·미수신 표 구조를 해소하는 범위다.
