# 세션 기록 — P2-WEB-003 사용자 변경·Agent 내부 수정 이력 UI

- Job ID: `auto-3a9bc38b3290fb504ed78dd67d0cbf172bcf1ad9`
- 배정 ID: PM-20261005-AUTO-3a9bc38b3290fb50 · 작업 ID: P2-WEB-003 · 요구: R21, R25
- 담당: 최길웅(choigilung) · 수행: 자동 Worker(Claude 계열 모델) · 기준 commit: 02f9a643e92c4665f2f0f71a5690f9ed6ed28930
- 승인 참조: https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/28#issuecomment-5997214746
- 성격: development-only 오프라인 구현 단위. 부모 Done, 실모델 독립 평가, 최종 제출과 무관.

## 원 요청(발췌)
"RevisionTimeline에서 원 요청·사용자 조건 변경·자료 변경·Agent 내부 최대2회 수정의 서로 다른 회차를 원문/이전 후보와 연결한다."
인수 조건 4개: (1) 다른 실행 ID 결과가 잘못 연결되지 않고 수정 전후 후보와 사용한 자료 버전을 추적, (2) 공통 계약을 소비하는 재사용 구현과 실제 실패/변경 입력 검사(고정 성공 응답·문서/테스트만 늘리기 금지), (3) 실자료/합성 구분 유지·과장 금지, (4) 개별 검사·자기 검수·불변 세션 기록·PR 제출(부모 완료·실모델 평가·최종 제출은 별도). 허용 경로 4개만 수정.

## AI 해석(사용자 확정 아님)
- `apps/web/src/RevisionTimeline.tsx`는 기준 commit에 없어 새로 만든다. 기존 `HistoryView`(PlanningViews.tsx)는 수정하지 않고(허용 경로 밖) 같은 계약 타입·`planning.ts` 순수 함수(`requestChanges`, `conceptDetailChanges`, `nextRequestRevision`)를 재사용한다.
- "회차"를 네 가지로 구분: 원 요청(첫 실행·원문과 동일), 사용자 조건 변경(요청 필드 차이), 자료 변경(run.dataset_version / dataset_sha256 / document_versions 차이), Agent 내부 수정(한 실행 안의 `run.revision_count`, 0~2). 내부 수정은 별도 실행/사용자 변경이 아니므로 원인 목록에 넣지 않고 실행별 수치로만 표시.
- "잘못 연결되지 않음"은 `previous_run_id` 체인만 따르고, 누락·순환·자기참조·중복 ID·다른 project_id·시각 역전·요청 회차 불일치를 보류로 처리하는 것으로 해석.

## 실제 행동
1. AGENTS.md와 CLAUDE.md 확인(AGENTS.md 전체는 두 번에 나눠 읽음; CLAUDE.md는 존재만 Glob으로 확인, 내용 대조는 하지 않음 — 한계).
2. 좁은 검색으로 `planning.ts`(1–135, 200–300, 376–406), `PlanningViews.tsx`(395–463), `fixtures/planning.fixture.ts`, `conceptTextChanges.test.ts` 읽음.
3. 생성: `apps/web/src/RevisionTimeline.tsx` — `buildRevisionTimeline(runs, selectedId, original)`와 `RevisionTimeline` 컴포넌트.
4. 생성: `apps/web/src/revisionTimeline.test.ts` — 데이터 11개 안팎 + DOM 2개 시나리오.
5. 이 기록과 근거 문서 작성.
저장소 코드는 실행하지 않았다(실행 도구 없음).

## 자기 검수(코드 정독, 미실행)
- 발견·수정한 결함: (a) 불필요한 `sameJson` 보조 함수·내보내기 제거. (b) 테스트에서 요청 회차 불일치 시 체인이 그 실행에서 멈추므로 `entries[1]`이 아니라 `entries[0]`을 검사하도록 정정.
- 호출자 영향: 새 컴포넌트는 아직 `App.tsx`/`HistoryView`에 연결하지 않음(허용 경로 밖). 따라서 기존 호출자 변경 없음.

## 인수 항목별 상태
| 항목 | 상태 | 근거 |
|---|---|---|
| 다른 실행 결과 오연결 방지, 전후 후보·자료 버전 추적 | 구현됨(실행 검증은 validator 대기) | `RevisionTimeline.tsx` `buildRevisionTimeline`; 테스트 'wrong or inconsistent links are held', 'compares candidates against the linked previous run only', 'separates original…' |
| 공통 계약 소비 재사용 구현 + 실제 실패/변경 입력 검사 | 구현됨(실행 대기) | `RunSnapshot`/`PlanningRequest` 타입과 `planning.ts` 함수 재사용; 누락/순환/타프로젝트/중복/회차 불일치/시각 역전/범위 밖 수정 횟수/자료 버전 불일치 입력 테스트. 계약 스키마 Ajv 검증은 이 모듈에서 새로 하지 않음 |
| 실/합성 구분·과장 금지 | 부분 | 모듈은 snapshot의 자료 버전/sha256만 표시하며 효과·모델 결과를 만들지 않음. 실자료/합성 모드 배지는 `HistoryView`의 `mode` 표시에 의존하고 이 컴포넌트에는 `mode` prop이 없음 → 미구현(한계) |
| 개별 검사·자기 검수·세션 기록·PR | 세션 기록·자기 검수 완료, 개별 검사 실행·PR은 validator/게시 단계 대기 | 이 문서, 근거 문서 |
| 앱 화면 연결(HistoryView 대체/삽입) | 미완료 | 허용 경로 밖. PM이 후속 경로 승인 필요 |

## 실패·미완료
- 테스트·typecheck·build 모두 이 세션에서 실행하지 않았다. 결과를 주장하지 않는다.
- 요청 회차 불일치 시 체인이 거기서 멈춰 이전 이력이 숨는 설계 선택(보류 우선)이다.
- 같은 모델의 document_versions 값이 동일해도 실제 문서 해시는 검증하지 않는다(스냅샷에 문서 해시 없음).
- Agent 내부 수정의 개별 회차 내용(1회차/2회차 후보)은 snapshot에 저장된 단일 `revision_count`와 events뿐이라 회차별 후보 비교는 하지 않았다.

## 대기 중인 validator 명령(신뢰 구역에서 실행)
1. `npm --prefix apps/web ci --offline --ignore-scripts --no-audit --no-fund`
2. `npm --prefix apps/web run test`
3. `npm --prefix apps/web run typecheck`
4. `npm --prefix apps/web run build`

## 다음 행동
validator 결과 확인 → 실패 시 원인별 수정 → PR 게시 → PM이 `App.tsx`/`PlanningViews.tsx` 연결 경로와 `mode` 표시 보강 단위를 배정. 자기 검수는 PR 승인·신뢰 검증·부모 완료를 대신하지 않는다.
- 사용자가 지금 직접 할 일: 없음.
