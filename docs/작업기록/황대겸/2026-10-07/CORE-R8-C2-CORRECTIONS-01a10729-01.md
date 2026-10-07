# CORE-R8-C2-CORRECTIONS-01a10729-01 — 담당 잔여 수정

- 2026-10-07 KST, 황대겸 / unknownamed / Codex. 대화 `01a10729-83bc-7b13-a7cc-4e2f92d8f69d`.
- 배정: [#234 C2/C3](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/234), [#9](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/9), [#4 PM 수동 CORE 인계](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/4#issuecomment-6039619224).
- branch `codex/hwang-r8-c2-isolation-20261007`, base `ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f`. 구현·관련 검사 완료, PM 인수 미완료.

## 지시·해석·실제 행동

사용자는 필수 작업을 계속하고 인간 판단이 필요한 항목의 의존만 보류하도록 직접 지시했다. 최신10분 예약은 실행 시간 제한이 아니며 이번 작업을 예약 시각 때문에 끊지 않았다. 새 메일5개와 최신 main/본인 Issue/연결 PR의 본문·댓글·리뷰·줄별·CI·head/base를 대조했다. PM245 병합과 CORE 구현 인계 완료 댓글을 수신하여, 이전의 포괄적인 PM 활성 파일 대기에서 담당 파일 수정으로 이어갔다. 같은 CORE 파일의 경쟁 열린 PR/실행은 확인되지 않았다. WEB249 화면 수정은 별도 담당 범위로 보존했다.

기존 C2 반례를 수리하고 C3의 반대 자료가 문맥에서 빠지는 소비 경계를 보완했다. 공유 내부 수정2회는 기존 primitive를 재사용하고 실패·후속 피드백도 누적했다. 전체 호출자 스키마와 최종 항목 검사를 유지하며 반환된 후보를 항목별로 검사했다. 정상 필드·facts·원 응답·기존 평가를 보존했다. 지지 출처2개가 반대 출처를 밀어내던 기존 슬롯2개는 지지1/반대1로 선택한다. 원 감정·새 고객 문제·효과를 자동 생성하지 않는다.

## 검증·실패·한계

[고정 소스 검사·경계 결과](../../../../evals/core-manual-quality/20261007/r8-c2-corrections/README.md)에 관련58검사 PASS, Ruff PASS 및 원 입력/소스·스키마 해시를 연결했다. 첫 정적 검사에는 import/불필요 return 지적과 Windows bind의 실행 비트 문제(EXE002)가 있었다. 코드를 정리하고 무인증 Docker의 SHA 동일 shadow에 Git100644 모드를 적용해 재검사했다. 규칙 제외·shebang 위장·검사 완화 없이 통과했고 최초 실패 수신은 private에 보존했다.

실제 `StructuredModelClient`는 전체 응답을 먼저 거절해 data/usage를 CORE에 반환하지 않는다. HTTP MockTransport를 통한 실제 adapter/client 검사로 이를 확인했다. 반환된 응답의 정상 항목 보존과 native 경로의 정상 항목 복구를 구분한다. 후자는 PM 전달 경계의 미완료이며 직접 우회하거나 PM 파일을 편집하지 않았다. source-type 수와 반대 출처 전달을 실제 감정/빈도/기획 품질 승인으로 바꾸지 않는다. 새 실제 모델·설치·추가 비용·여섯 사례 재채점0이다.

## 미완료·다음 행동·사용자 판단

PM의 native 후보/항목 거절 전달 경계와 기존 실제27B run의 원 응답·usage·설정·동일 HTTP/MCP 저장 결과가 필요하다. 그 후 본인이 C1~C4의 원문 의미·설치 제약/순서·미확인 원인·구체 개선 장면을 대조하고 X1 실제 기획 안내를 생성한다. legacy exact-model 전체 삭제, noGold/input-only/graph 연결 잔여도 유지한다. PR247/248의 기존 검사·인쇄 근거는 재사용한다. PM 승인·병합·통합·Done을 대신하지 않는다.

현재 새 인간 판단 질문은 없다. PM의 준비된 LG27B 인계라는 사용자의 기존 선택을 유지한다. Worker/자동PM OFF, PR142 예약 취소, 연구실·타 서비스·원 파일 보존 및 중앙 잔여/STOP 미정 상태를 변경하지 않았다. 필수 PM 인수 완료 전이므로 대화10분 예약을 유지한다.

[같은 ID 근거](../../../작업근거/황대겸/2026-10-07/CORE-R8-C2-CORRECTIONS-01a10729-01.md).
