# R8 고정 소비 검수 — C2 실패 경계와 X1 공식 발췌

2026-10-07 황대겸 / unknownamed. PM [PR245](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/245)의 고정 head `e04f42b5de37b2d1cad606f2f06a3f7fe6a91f30`을 소비했다. 이전 branch 미게시 기록 뒤 새 게시를 수신한 후속 결과다.

## C2 실제 검수 결과

[검사 코드](verify_failure_boundaries.py) · [관측 결과](failure-boundaries.json)

원 후기837305의 정확 발췌·공식 M11·기존 실제 Qwen 오류 문장을 재사용했다. 새 고객 리뷰나 콘셉트를 만들지 않았고 test-only wire ID는 의미 판정/기획 결과가 아니다. 모든 수정 응답을 거절시켜 최종 문제/기획은 비어 있고 source_facts는 원 입력과 같다.

- 공유 최대2: 항목3개에서 `discover → repair_fields ×3` 관측. 후보마다 한 번이라는 제한은 run 전체의 최대2를 보장하지 않는다. 요구 미충족이다.
- 부분 보존: 정확 원문 복사 wire 항목과 title 누락 항목을 함께 반환하면 배열 전체 schema에서 거절되어 정상 항목도 제외된다. 원응답은 runtime에 남지만 항목별 검사까지 도달하지 않는다. 요구 미충족이다. plan의 비교/기획 배열도 같은 전체 검사 경로를 사용한다는 것은 코드 대조이며, 실제 새 콘셉트 재현으로 확대하지 않는다.
- 고정 Docker `sha256:36ad082dbccf05bc9cff7c4dc5766e9ab7ed8c42198b0b731cf3831c546aaaf0`, UID65534, network=none, readonly/source-only/zero-auth에서 실행했다. 모델·재채점0이다. 기존 여섯 사례와 완료된 검사 묶음을 반복하지 않았다.

PM 활성 코드는 중복 수정하지 않고 [원 검수 인계](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/245#issuecomment-6039065292)를 게시했다. CLI/schema/API/MCP의 기존 검사 조건을 완화하지 않는다.

## CI 및 연결 잔여

e04의 Python CI [run37626673758](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/actions/runs/37626673758), [run37626665836](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/actions/runs/37626665836)는 `Unexpected private MCP tool set`에서 실패했다. `test_public_validation_projection.py:170`이 기존 `replay_workspace.py:138`의 정확 tool set 대조를 호출한다. API/MCP 담당이 새 연구 tools의 정확 계약을 인수해야 한다.

`customer_context[:2]`는 지지 출처2개 뒤의 counter 원문을 plan에서 제외할 수 있다. 관계 ID와 기획 입력 문맥을 따로 검수해야 한다. P0의 문자열 단계에는 WEB243이 요청한 단계별 observed/inferred·근거ID가 없어 담당 간 규격 조율이 남는다. C4의 양면/맥락별 실제 분모·의미 판정은 원 모델 응답 수신 뒤 확인하며 source_type_counts를 감정 건수로 바꾸지 않는다.

## X1 독립 준비

[공식 발췌 생성·원문 검사](export_official_intake.py) · [고정 입력/결과 해시](official-guide-audit.json)

고정 확장 bundle에서 MW23FDI3개, DUE6BGL2E6개, T876MEE1H1 6개의 공식 manual 발췌를 모델 없이 내보냈다. 구매 SKU/게시일 미확인·문서판·locator·coverage와 전체 source/facts를 그대로 보존한다. FAQ는 page_model=null이며 계열/제품군 안내일 뿐 정확 SKU 적용 확인이 아니다. 정확 모델 FAQ로 전환하거나 Q&A를 고객 리뷰로 채우지 않는다.

첫 인쇄 검수에서 본문 없는 제목 페이지와 긴 fact JSON의 분할을 발견했다. 원 실패 출력은 비공개 재개 기록에 보존하고, 후속 X1 print-only branch에서 CSS를 보완한다. 이 디렉터리의 원 고정 출력은 해당 CSS 보완의 최종 산출물이 아니다. 새 기획 설명서는 실제 저장된 콘셉트 수신 전 보류하며 placeholder를 만들지 않는다.

전체 모델 품질·PM 인수·병합·통합·Done은 미완료다. 사용자 추가 판단 대기0이며, C1은 PM이 진행 중인 실제27B 실행의 원응답·usage·version을 인계받아 검수한다. 이 창에서 live run을 중복 시작하지 않는다.

## 5fdb follow-up

[후속 고정 결과](failure-boundaries-5fdb.json)는 같은 원 입력/실패 probe를 새 5fdb 코드에서 대조한 것이다. 원 e04 실패를 덮어쓰지 않는다. 새 모델/리뷰/콘셉트/AI채점0. 별도 국소 검수 patch가 추가됐으나 기존 생성 경계의 공유2/정상 형제 보존 요구는 미충족이다.
