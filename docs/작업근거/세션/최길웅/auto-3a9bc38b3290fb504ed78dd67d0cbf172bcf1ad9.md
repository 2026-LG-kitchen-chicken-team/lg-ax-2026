# 작업 근거 — P2-WEB-003 (Job `auto-3a9bc38b3290fb504ed78dd67d0cbf172bcf1ad9`)

연결 기록: `docs/작업기록/세션/최길웅/auto-3a9bc38b3290fb504ed78dd67d0cbf172bcf1ad9.md`
확인일: 2026-10-05 · 기준 commit 02f9a643e92c4665f2f0f71a5690f9ed6ed28930 (작업 디렉터리는 git 저장소가 아니어서 commit/해시를 직접 확인하지 못함 — 패킷 값을 인용)

## 읽은 원본(좁은 범위)
- `AGENTS.md` 1–189행 전체(두 번 읽기). `CLAUDE.md`는 존재만 확인, 동일성 비교 미수행.
- `apps/web/src/planning.ts` 1–135, 200–300, 376–406: 타입(`RunSnapshot`, `Run`), `requestChanges`, `canonical`, `nextRequestRevision`, `conceptDetailChanges`, `runLineage`(조용히 끊기는 기존 방식 확인).
- `apps/web/src/PlanningViews.tsx` 395–463: 기존 `HistoryView`.
- `apps/web/src/fixtures/planning.fixture.ts` 14–119: 합성 fixture 2실행(RUN-FX-001/002, 문서 1.0, revision_count 1/0). fixture는 합성 예시이며 실제 수요/모델 결과가 아니다.
- `apps/web/src/conceptTextChanges.test.ts` 1–110: 테스트 관례(jsdom, createRoot, act).

## 변경 파일
- 신규 `apps/web/src/RevisionTimeline.tsx`, 신규 `apps/web/src/revisionTimeline.test.ts`, 두 세션 문서. 다른 파일 변경 없음.

## 지지하는 주장
- 코드 정독상, 타임라인은 `previous_run_id`로만 연결하고 불일치는 보류한다(테스트가 이를 기대값으로 고정).
- 사용한 자료 버전(dataset_version·dataset_sha256·문서 버전)은 snapshot 값 그대로 표시하고 이전 실행 대비 차이를 계산한다.

## 지지하지 않는 주장
- 테스트/타입/빌드 통과: 실행하지 않았으므로 주장하지 않는다. 테스트 기대값은 fixture를 손으로 추적해 작성했고 실제 통과는 미확인.
- Agent 판단 품질, 신규성, 효과, 실모델 결과, 실제 고객 수요: 해당 없음·주장 없음.
- 앱 화면 통합, 부모 요구 R21/R25 완료: 아님(컴포넌트가 App에 연결되지 않음).

## 실행 결과
- 이 세션에서 실행한 저장소 명령: 없음.
- 실패·한계: 위 기록 문서 "실패·미완료" 참조. 추가: 테스트의 jsdom 클릭 처리와 타입 엄격성(예: `Object.hasOwn`, JSX data 속성)은 타입체크 전 미확인.

## 인수 항목 증거 표
| 항목 | 증거 위치 |
|---|---|
| 오연결 방지 | `RevisionTimeline.tsx` 내 체인 순회 루프; `revisionTimeline.test.ts` describe 'wrong or inconsistent links…' (누락·타프로젝트·순환·자기참조·중복·회차불일치·시각역전·범위 밖 수정 횟수·not_implemented) |
| 전후 후보·자료 버전 | 같은 파일 `dataChanges`/`conceptDetailChanges` 호출; 테스트 'separates…', 'compares candidates…', DOM 'shows causes, data versions…' |
| 실제 입력 검사(고정 응답 아님) | 모든 출력이 입력 runs로부터 계산됨; 상수 성공 응답 없음 |
| 실/합성 구분 | 컴포넌트에 mode 표시 없음 → 미구현으로 기록 |

## validator 대기 명령
`npm --prefix apps/web ci --offline --ignore-scripts --no-audit --no-fund` → `npm --prefix apps/web run test` → `npm --prefix apps/web run typecheck` → `npm --prefix apps/web run build`
