# W1 결과 검수 — CORE 수신 회신과 비교 범위 대조

기록: DATA-W1-01a1100e-26f07a6f · 신진하(DATA) · 2026-10-08 KST. 시작 main `eab85d48385f965eef48c07a6cdd8f6fd9851c62`.

이번 새 인수 자료는 CORE의 [#15 보유 범위 회신](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/15#issuecomment-6051070034)과 [PR279 실제 수신 회신](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/279#issuecomment-6051149074) 2개다. 두 run의 원 JSON, 동일7 비교 원출력, 4질의 AI 응답을 새로 받은 것은 아니다. [원 회신 스냅샷](sources/core-replies.json) · [파일 pin](reference-pins.json) · [구조화 검수표](review-delta.json) · [수신 해시](source-receipt.json).

## 확인·상충·미확인

| 대상 | 받은 범위·상태 | 이번 판정 | 남은 근거와 담당 |
| --- | --- | --- | --- |
| 기존 PR279 발췌 검수 | CORE가 54파일/17 source pin/44 원문 구간의 수신·대조를 회신 | **확인: CORE 수신 진술**. 이번 W1은 연결하는7개 공개 참고파일의 고정 blob만 대조; 54파일/44구간 검사를 반복하지 않음 | 원 모델 JSON 수신·모델 품질 승인·PM 인수와 별도 |
| 정상 `run-1f83d846191941aea21153897b944ec1` | 선언 SHA `4e84728d07aedff38cc30c26f839abce2ae54719e341954f27dff353c79ed3d2`; CORE 원파일 미수신 회신 | **미확인**: 실제 파일 SHA/전체 입력/생성 commit/native/전체 실패·재시도·usage | PM 보유 원파일 또는 Source ID+정확 field path/value → W3 인계 → W1 검수 |
| 변경 `run-754268c6b0cb41bba50c5b8d713332d9` | 선언 SHA `0fd3a2047a7fd884af1c89e6d87ef46e83a446f5b277d18c838876bf63427c1d`; 부모 정상 run/brief는 보고 선언 | **미확인**: 위 항목과 실제 부모 결과 연결 | 부모 brief `brief-fe7412d6635c4822988f8d42ae6acddc` 원파일·필드 연결 |
| 정상/조건 비교 | 보고상 조건1개/5개, R9 공개 selected source6 | **상충: 동일 조건 A/B 대입 불가**. 조건 revision의 변화 검수는 가능 | 두 방식의 같은 자료·입력·조건·모델 설정 수신 전 비교 인정0 |
| 동일7 Agent/일반LLM | 공개 metadata의 합성7입력/6그룹만 확보; CORE도 두 방식 원출력 미수신 | **미확인**. 현재 R9 두 public run을 합성7 입력 결과로 대입하면 **상충** | 기존 Agent/baseline 각 결과·full-input canonical SHA·실패/retry/usage. 미수신 값은 null |
| PM의 기존7 run/12 call | 실제 실행 checkpoint를 확인 | **확인: PM 실행 보고**. 숫자7만으로 합성7 case의 대응/동일 방법쌍을 인정할 수 없음 | 그7run의 실제 입력과 각 방법 연결은 미확인. PM 실행 자체를 미생성으로 바꾸지 않음 |
| FR04·FR05·DW05·MW05 | 기존 원문 진단/저장 검색은 PR279에서 확보; CORE 실제 AI 응답 미식별 | **미확인**: AI 답변·질문·보류의 의미 판정/정확도는 null | 해당 기존 응답과 질의/input/source/code/data/model/output pin |
| 과거6 legacy 또는 검색순위 대체 | CORE가 다른 synthetic/legacy 입력·스키마라고 회신 | **상충: current 출력 대체 제외** | 다른 입력/제품/판본 결과를 이번 출력으로 인정하지 않음 |

상충은 **비교대상·증거 종류가 맞지 않는 경우**다. 원 JSON이 없으므로 이번 run에서 새 제품/버전 오류를 실제 관측했다는 뜻은 아니다. CORE의 미보유 회신은 PM 전체의 미생성을 증명하지 않는다. PM report 파일의 실제 SHA `f7d69e6fbd9ac43cd08754c7c7dfd51032b02472df90be37db160f17cb2f55fa`(27,801 bytes)는 모델 원파일 SHA와 다르다.

## 원문 진단의 재사용

| 결과 | 이미 검수한 범위 | 원 JSON에서 이어 확인할 것 |
| --- | --- | --- |
| [정상5항목](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/0a34871e7a46bc2599cca5dd264877b258ac0178/evals/data-parallel/w1/20261008-01a10c5c-a8f17d3d/normal-review.md) | 배우자/구매자, 청소/기간, 희망·혼합 경험, 80–100ml 조건과 배수 순서, 고객 조치/제조사 안내 | 해당 description/target_user/assumptions/source_ids, before/scene, summaries3배열, after/proposed/question 전체 |
| [조건5항목](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/0a34871e7a46bc2599cca5dd264877b258ac0178/evals/data-parallel/w1/20261008-01a10c5c-a8f17d3d/changed-review.md) | 주체·가상 이력, 약1개월/총약3달, 기사 태도 인식/거부, 조건별 제조사 조치 | 실제 전체 문맥·같은 자리의 가설/질문/적용 조건·부모 연결 |
| [무Gold4 진단](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/0a34871e7a46bc2599cca5dd264877b258ac0178/evals/data-parallel/w1/20261008-01a10c5c-a8f17d3d/no-gold-review.md) | 이전 판본 부재, 식기세척기↔냉장고 기능 경계, 개인 식기 치수/배열 부재, 사전 메뉴 기억↔임의 시간/출력 저장 | 실제 해당 AI 응답/질문/보류. 기능 미확인을 제품 전체의 명시적 미지원으로 바꾸지 않음 |

23 발췌는 보고서가 선택하거나 축약한 문장이다. 연속 모델 인용이나 전체 출력 누락을 확인한 것으로 올리지 않는다. **CG-N-03은 출력 예시 없는 report-only finding**이며 전체 요약에서 누락됐다는 독립 판정은 미확인이다. W1 파생 anchor는 실제 output Evidence ID가 아니다. 구매 SKU/게시일/구매시점 판본·원인/호전도 기존 미확인을 유지한다.

## 경계와 다음 작업 하나

새 worktree `C:/Users/user/Documents/ChatGPT/LG공모전/.worktrees/data-w1-20261008-01a1100e-26f07a6f`, branch `codex/data-w1-01a1100e-26f07a6f`, 새 고유 폴더만 작성한다. 기존 코드/자료/개인 README/다른 창 파일 변경0. 모델/OCR·225실험·11재채점·기존 producer 검사·DB/API/MCP·서버 재시작·CI 수동 재실행·메일 발송0. Gold/독립성 승인·최종 채점자 결정은 PM, 메일/ZIP/운영 무결성은 W3, 표/후기/제품 자료는 W2 담당이다.

[기존 최소 인계 요청](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/15#issuecomment-6050694450)을 재사용한다. **다음 하나: 기존 정상 run의 승인된 Source ID+정확 필드 경로/값 또는 원 JSON부터 받아 대조한다.** 전체 packet·Gold·ZIP 완료를 일부 필드 검수의 선행조건으로 추가하지 않는다.
