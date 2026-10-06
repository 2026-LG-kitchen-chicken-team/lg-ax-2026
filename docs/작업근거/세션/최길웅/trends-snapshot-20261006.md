# 최길웅-E025 — 리뷰 동향 집계 스냅샷 내보내기 근거

- 연결 기록: [최길웅-20261006-030](../../../작업기록/세션/최길웅/trends-snapshot-20261006.md). 확인일 2026-10-06 KST.
- 기준: PR #158 head `f393a54a872d5a8ed28e20b0f559373d7b7b9fd0`(main `84844b8`과 웹 lock 동일).

## 실행 결과(작업 위치 `Desktop/lgax-wt-live/apps/web`)

| 명령 | 결과 |
|---|---|
| `npx vitest run src/reviewTrendsSnapshot.test.ts`(1차) | 1 failed / 4 passed: `TypeError: blob.text is not a function`(jsdom Blob) |
| 같은 명령(시험용 Blob 대체 후) | 5 passed |
| `npm run test` | Test Files 29 passed / 3 skipped, Tests 466 passed / 5 skipped, safe-ci pass 4 / fail 0 |
| `npm run build` | `tsc -b` 통과, built 3.36s |
| 앱 내 브라우저 `http://127.0.0.1:5183/`(이 브랜치, fixture) | `.trend-export` 문구 "집계 스냅샷 내보내기 (합성 fixture로 표시됨)", 버튼 JSON·문서(Markdown) 높이 34px, 그래프 아래 배치. 확인 뒤 5183 프로세스 종료, 포트 닫힘 확인 |

## 지지하는 주장 / 지지하지 않는 주장

- 지지:
  - 내보낸 JSON의 aggregate는 화면에 그린 집계와 같다(바꾸거나 다시 계산하지 않음).
  - 원문 기록은 현재 선택 구간의 완료된 page만 담는다.
  - fixture 출처와 읽을 때 주의(판매량 아님, 자료 없음 ≠ 0%, 작은 표본)가 함께 나간다.
- 지지하지 않음:
  - 실제 collector 집계의 내보내기
  - MCP 같은 ID 연결
  - 이 형식이 PM이 기대한 스냅샷 형식과 같다는 것(공통 계약 없음, PM 확인 필요)
  - PM 검수·병합
