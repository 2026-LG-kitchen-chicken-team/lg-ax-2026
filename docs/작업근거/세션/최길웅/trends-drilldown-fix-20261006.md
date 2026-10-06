# 최길웅-E024 — PR #158 동향 드릴다운 지난 응답 차단 근거

- 연결 기록: [최길웅-20261006-029](../../../작업기록/세션/최길웅/trends-drilldown-fix-20261006.md). 확인일 2026-10-06 KST.
- 대상: PR #158. 원 head `700cac9e0ef039e13a99da438985bbd434099e58`. 검수 지적 행: `ReviewTrendsPanel.tsx` 75~83, 152.
- main 반영: `git merge origin/main`(`d0b8e3e`) → `1e2913d`. 충돌 없음. 원 커밋은 이력에 그대로 있다.

## 실행 결과(작업 위치 `Desktop/lgax/apps/web`, 사용자 개발 서버 폴더. 설치·E2E는 하지 않음)

| 명령 | 결과 |
|---|---|
| `npx vitest run src/reviewTrendsPanel.test.ts`(수정 후) | 7 passed |
| 같은 명령, `ReviewTrendsPanel.tsx`만 `HEAD`(수정 전) 내용으로 잠시 바꿈 | 6 failed / 1 passed. 실패: 역순 응답, A 원문 잔존, 실패 뒤 늦은 응답, 다른 키 응답, 로그인 범위 변경, 더 보기 중 잠금. 이후 수정본으로 복구 |
| `npm run test` | Test Files 28 passed / 3 skipped, Tests 459 passed / 5 skipped, safe-ci check pass 4 / fail 0 |
| `npm run build`(1차) | 실패: `src/reviewTrendsPanel.test.ts(50,127) TS2769`, `Mock<Procedure \| Constructable>`를 `(note, modelId) => void`에 넣을 수 없음 |
| `npm run build`(콜백 타입 지정 후) | `tsc -b` 통과, `built in 3.20s` |

## 앱 내 브라우저(사용자 개발 서버 `http://localhost:5173`, 합성 fixture)

- 메뉴 "리뷰 동향" → 값 막대 1번째 클릭: 제목 "2026년 1월 · 청소 불편 (cleaning) 원문", 원문 `EV-TREND-MONTH-2026-01-cleaning-01…`, 기획 추가 버튼 있음.
- 값 막대 3번째 클릭: 제목 "2026년 4월 · 청소 불편 (cleaning) 원문", 원문 `EV-TREND-MONTH-2026-04-cleaning-01…`(1월 원문 없음).
- 주제 select를 `odor`로 변경: `.trend-drilldown` 없음, 눌린 막대 0개. 이후 막대 클릭 시 "2026년 3월 · 냄새 (odor) 원문".
- `read_console_messages(onlyErrors)`: 없음.
- 스크린샷: "Screenshot timed out after 5s"로 실패. 위 결과는 DOM 조회 값이다.

## 지지하는 주장 / 지지하지 않는 주장

- 지지:
  - 화면에 보이는 원문, "원문 더 보기", 기획 전송 근거가 모두 현재 선택한 집계·구간·주제의 최신 응답에서만 나온다.
  - 늦은 응답, 실패, 로그인 범위 변경 때 이전 원문이 남거나 전송되지 않는다(모의 응답 순서 DOM 검사, 합성 fixture 화면).
- 지지하지 않음:
  - 실제 collector나 실서버의 원문 드릴다운 성공. 서버 집계기 미연결 501, DATA #148 대기.
  - 네트워크 지연이 실제 서버에서 같은 순서로 재현된다는 것.
  - PM 재검수, 병합, WEB005 승인.
