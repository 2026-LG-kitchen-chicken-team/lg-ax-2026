# 관리 근거 연결·공식 설명서 확대·운영 인계 독립 검수

기록 ID `DATA-REMAINING-INTAKE-20261008-01a1100e`, 신진하 / `ginaginaring`, 2026-10-08 KST. 사용자는 진행 중인 두 창에 지장이 생기는 작업을 보류하고, 가능한 나머지를 진행해 담당 팀원에게 GitHub로 인계를 요청하라고 지시했다.

## 이번 실제 결과

| 범위 | 결과 | 확인하지 못한 범위 |
|---|---|---|
| PR254 관리14 연결 | 기존 PR252 native 원문→새 Source의 ID·한글 text·판본·PDF/발췌 SHA·쪽/문자 locator·미확인 조건 **14/14 일치** | CORE 실제 고정 결과·API/DB 등록·고객 원인/호전 |
| 연속 단계 연결 | 원문 같은 절의 단계 연결과 `continuation_pages`를 대조해 **5개 경고** | 생산 metadata의 정의·실제 모델에서의 잘못 사용은 미확인 |
| 나머지15모델 설명서 | 정확 SKU 지원페이지15·모델별 후보19·공개 URL16 수령, 서로 다른 전체 PDF SHA15·표지15 확인 | 표지 정확SKU 명시는5모델. 나머지10의 공용 적용·모든 기능·구매시점판·운영 등록 |
| 사용 Q&A/게시일 후기 | 공식 Q&A3의 원 HTML bytes/SHA 수령, 후기1 보류·제휴1 제외 | 확정 신규 후기0. 기사 표시일·구매일을 후기 게시일로 변환하지 않음 |
| #13 | 새 R8 file bundle/run DB에 맞는 [인계 요구7항목](runtime-intake.md) 작성 | actual raw DB/API/MCP/restart 쌍 미수신·UNCONFIRMED |
| #14/#148 | 다른 사용자 창이 표 근거 sidecar·개발용 topic/동향 인계를 진행하는 것을 확인해 **중복 작업 보류** | 실제 자동 graph/adapter 미수신, 자동 정확도/오류 수는 null |

전체 승인이나 부모 Done을 판정한 기록이 아니다. D1·D2 생산·D4 전수 감사·CORE 판단·기존 검색/모델/OCR 실행을 반복하지 않았다.

## 고정 입력과 검수표

- 원 main: `ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f`.
- 원 관리 감사 PR252: `78a1906369479eb2336cecc3a134895a814f95b1`.
- 새 생산팩 PR254: `94b560de72f91795cfd50aada9e17d6773383ae1`.
- [14행 대조 CSV](care-source-bridge.csv), [판정/미확인 범위 JSON](care-bridge-result.json), [6개 원본 pin/bytes/SHA](care-source-pins.json).
- [15모델 설명서/표지/공식 원본 링크](../../../data/reference/data-remaining-intake/20261008-01a1100e/manual-reference.md), [원 수령 JSON](../../../data/reference/data-remaining-intake/20261008-01a1100e/manual-acquisition.json).
- [사용 Q&A·후기 후보](../../../data/reference/data-remaining-intake/20261008-01a1100e/qa-review-candidates.md), [Q&A 원 HTML 응답 receipt](../../../data/reference/data-remaining-intake/20261008-01a1100e/qa-original-captures.json).
- [Q&A 짧은 원구절3개 재대조·최초 비정확 인용1개 정정](../../../data/reference/data-remaining-intake/20261008-01a1100e/qa-excerpt-audit.json).
- [날짜·기록ID별 본인 상세 기록](../../../docs/작업기록/신진하/2026-10-08/DATA-REMAINING-INTAKE-20261008-01a1100e.md).

## `continuation_pages` 경고5개

기존 감사에서 실제 PDF 페이지와 렌더를 직접 판독한 **같은 절의 단계 연속성**을 기대값으로 사용했다. 자동 예측/셀 출력의 성능 평가가 아니다. Source 본문 자체는 모두 같고, 생산 metadata가 단순 이웃 페이지를 뜻하는지 같은 작업 단계를 뜻하는지는 PM·D2의 확인이 필요하다. 실제 CORE 결과에서 절을 혼동했다고 판정하지 않았다.

모든 아래 canonical Source ID는 `D2-DUE-CARE-`에 표의 audit ID를 붙인 값이다.

| audit ID / 쪽 | 생산 페이지 | 같은 절 기대 페이지 | 추가 페이지의 다른 절 | 다음 담당 행동 |
|---|---|---|---|---|
| `DW-INTERNAL-CLEAN-P39` /39 | `[40]` | `[]` | 음식물 필터 | D2가 일반 주변문맥/동일작업 정의 구분 |
| `DW-TUB-CITRIC-P41` /41 | `[42]` | `[]` | 식초 세척·노즐 | 구연산 완료 단계와 식초 단계를 분리 |
| `DW-TUB-VINEGAR-P42` /42 | `[41,43]` | `[41]` | 노즐·미사용 보관 | 같은 식초 절의 시작쪽만 연결 |
| `DW-NOZZLE-P42` /42 | `[41,43]` | `[43]` | 구연산·식초 | 노즐 절의 실제 다음쪽만 연결 |
| `DW-STORAGE-P43` /43 | `[42]` | `[]` | 식초·노즐 | 보관 절과 다른 작업을 분리 |

필터39↔40·식초41↔42·노즐42↔43의 실제 연속 단계와 상호 시작/끝 연결은 나머지 표에 보존했다. 기존 native `50 7`과 렌더 `50 ℃`의 차이도 고치지 않았고, 원 구매SKU/정확 구매시점판의 미확인 표시를 유지했다. 소비 담당은 source_id/text/locator를 고정한 원결과를 제공하고, DATA는 결과별 인용·기능/관리 설명·빠진 근거를 이어 대조한다.

## 두 창과의 편집 경계 및 남은 역할

| 담당/창 | 확인 상태 | 남은 작업·필요한 인계 |
|---|---|---|
| 「LGAX #12」 D1·D2 | PR254 제출·CI4/4 성공 보고 확인, head94b | PM 검토·인수·병합. 위 경고5의 의미 확인/필요한 별도 수정. 이 창은 생산 파일을 수정하지 않음 |
| 「컨설팅 질문 준비하기」 D3·D4 | D3 PR244 병합, PR246 head6f63 보완 제출·PM 검토 대기 | D4 고정 감사는 최초 producer6fd98c0 범위. 새 P0/care94b 전체 D4 인수로 승계하지 않음. 새 #14 sidecar·#16/#148 topic 초안은 그 창 진행 |
| DATA/CORE 관리 소비 | 이번14개 등록 입력 대조 완료 | 황대겸 `@unknownamed`의 고정 input/output/trace·Source ID·판본/SHA와 PM 인수 |
| DATA 설명서/사용 Q&A/후기 | reference 원본·SHA 및 후보 제출 | PM/D2가 선택 모델·구간/공용 적용·등록을 인수, 원 리뷰 ID·게시일 field 의미·실사용/중복 계보 수령 |
| #13 PM/등록·CORE | 인계 요구 갱신, 원 raw 미수신 | `@jeongiryang`의 실제 선택 bundle·runDB·GET/MCP 원응답/원파일·동일DB restart receipt·전후쌍 및 PM 인수 |
| #14 PM/생산·CORE | 중복 보류, 자동 출력 검증 불가 | 실제 cell/row/col/span/header/model/value/unit/footnote graph와 approved cell→Evidence adapter 고정 pin |
| #15 독립 평가 | 후보/역할/SHA 확인은 기존 제출 | 비공개 실제 수신, Gold·독립성 승인, 최종 채점자 지정·실제 평가. 이 창은 평가 원문/답안 재열람 안 함 |
| #148 동향 | 기존238·격리12·연구226 재계산은 제출, 월분모0 | 다른 창의 topic 초안 → PM 승인 topic/version·실제 후기 게시일 provenance → DATA 재계산·WEB 소비 |
| 무Gold4 의미검수 | 기존 순위/미수신 상태 유지 | CORE/PM의 해당 기존 고정 의미응답 인계. 완료된11문항/225회 재채점은 반복 안 함 |

PM PR245의 실제 모델12호출·저장 흐름5회/API·MCP 재조회 보고와 병합 인수는 보존했다. **실행이 없었다고 기록하지 않는다.** 이 독립 감사에 raw export가 없는 상태 및 아직 등록하지 않은 PR254 care팩과 구분한다.

## 재현과 보존

이 새 비교기는 고정 Git blob만 읽으며 생산 코드를 import하지 않는다. 먼저 원 PR252/254 head를 가진 저장소를 준비한 뒤 표준 Python으로 아래 명령을 수행한다. 최초 원본 JSON 구조 오해의 TypeError와 수정 후 결과는 [원 실행 이력](execution-history.json)에 보존했다.

```powershell
python -X utf8 evals/data-remaining-intake/20261008-01a1100e/audit_care_bridge.py
```

공식 PDF의 최초 수령은 `capture_manual_references.py`, 이미 받은 bytes의 표·표지 작성은 `finalize_manual_references.py`, 공식 Q&A 원 HTML 응답 수령은 `capture_qa_references.py`다. 모두 새 전용 private/reference 폴더만 사용한다. PDF 원본/FAQ full HTML은 local/private이고 PR에는 원 URL·전체 SHA·bytes·표지/짧은 발췌만 포함한다. PDF native 표지16회를 읽었고 OCR/모델·생산 수집기/DB 생성·API 등록·재시작·배포·예약/자동화 ON은0이다.

기존 코드·자료·개인 README는 읽기 전용으로 유지한다. 원문/실패/예산을 삭제하거나 CI/보호규칙을 완화하지 않았다. 같은 head의 GitHub 게시·검사·PM 검토는 별도 실제 수신증으로 보고한다.

[파일 보존·JSON/CSV·내부 링크 검수](artifact-checks.json)와 [새 산출물 bytes/SHA manifest](new-artifacts-manifest.json)는 `validate_artifacts.py`가 생성한다. manifest 자체와 check report는 자기참조를 피하려고 manifest 목록에서 제외하고, 게시 시 같은 Git head/blob로 별도 확인한다. 기존4,232파일/178,400,766bytes의 Git blob 대비 변경0을 확인했다. 이 검사는 원문 bytes/메타데이터 범위이며 실제 DB/API/자동 구조/의미 승인과 구분한다.
