# 10/6 — 자동화 OFF·수동 개발 배정

사용자 지시: “자동화 off하고, 이전처럼 하던 방식으로 해서 남은 작업들 배정하고 내가해야할것들 진행하자”. 이전 ON 지시와 자동 배정·무인 개발·무인 검수/병합은 이 지시로 중단한다. 이 문서 위에 더 최신 사용자 지시와 실제 관측이 없으면 OFF를 유지한다.

## 실제 적용

- 중앙 팀 모드 OFF, 정이량·황대겸·신진하·최길웅 개인 모드 모두 false를 정상 mode API로 적용하고 재조회했다.
- 정이량의 고정 PM은 실제 tick 잠금·미해결 게시/메일 없음 확인 뒤 중지했다. 본인 PM·Worker 예약 실행 두 개를 비활성화했다. 다른 PC의 프로세스 중지 여부는 별도 확인이며 중앙 OFF로 새 자동 claim·게시를 막는다.
- jobs·attempt·예약·실패·비용·사용량 한도·원 승인 스냅샷을 보존했다. 기존 pending 자료/웹 두 작업은 역사 대기 상태로 남으며 수동 결과를 자동 결과의 성공으로 바꾸지 않는다.
- GitHub Issue·Project·팀원 자기 상태 보고·수동 배정 메일·공통 API/MCP·자료/모델 서비스는 계속 사용한다. 개발 도구/로그인을 다시 설치할 필요는 없다.
- 향후 ON은 새 사용자 지시 뒤 수동 PR·예약·미완료 자동 job의 중복/버전/실행 경계를 먼저 확인해야 한다. OFF는 기록 삭제나 예산 초기화가 아니다.

## 이번 수동 배정

세 배정은 담당 Issue와 Project에 반영했고 PM 계정의 Gmail 실제 Sent 및 발신·수신·제목을 대조했다. 메일 열람이나 착수는 아직 확인하지 않았다. **10/6 18:00 KST 첫 부분 결과 또는 막힘 보고**는 PM이 선택한 운영 목표이며 대회 공식 마감이 아니다.

| 담당 | 먼저 끝낼 작업 | 배정 원문·후속 |
|---|---|---|
| 황대겸 | 실제 판단 품질. 신청 사례에 맞춘 식기세척기 입력, 냉장고의 기존 기능과 잔여 불편 분리, 전자레인지 피드백, PR97/136의 리뷰+설명서 쌍 근거 보호 규칙을 현재 코드에서 검증/보완. 실패를 숨기지 않고 세 제품·수정 한도를 실제 모델로 검사 | [Issue11 배정](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/11#issuecomment-6007498748), [품질 Issue150](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/150), [배정 JSON](assignments/PM-20261006-CORE-MANUAL-QUALITY-R1.json) |
| 신진하 | 현재 자료/검색 코드의 원문·제품/모델·버전 연결, 다른 제품 출처 거부, Unicode 원문/해시 보존, 새 자료의 실제 검색 비교. 과거 출력 보존 패치가 현재 소비 경로에 적용되는지 확인 | [Issue13 배정](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/13#issuecomment-6007500888), 이후 [동향 자료148](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/148), [배정 JSON](assignments/PM-20261006-DATA-MANUAL-VALIDATION-R1.json) |
| 최길웅 | 최신 웹의 요청·질문·보류/실패·후보 비교·사용자 변경/Agent 내부 수정 분리·인용·수정 이력·JSON/Markdown 내보내기. 실제 같은 기록으로 세 제품 흐름을 확인하고 코어 실패를 성공 화면으로 바꾸지 않음 | [Issue25 배정](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/25#issuecomment-6007502640), 이후 [동향 화면149](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/149), [배정 JSON](assignments/PM-20261006-WEB-MANUAL-FLOW-R1.json) |
| 정이량 PM | 과거 열린 PR의 원본/의도/실패 보존, 선택 인수·후속·중복 PR 정리, 최신 main 통합 검수·Project 승인. 동향 공통 집계/API/MCP 계약, 실제 두 AI 연결, 독립 평가와 발표·영상·재실행 ZIP 인수 | [운영28](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/28), [공통 동향152](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/152), [평가21](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/21), [제출22](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/22) |

각 AI는 직접 사용자의 지시를 받아 자기 브랜치/작업 공간에서 진행한다. 자신의 `docs/작업기록/`·`docs/작업근거/`에 지시 원문, 별도의 의도 해석, 실제 수행·실패·검사·남은 일·재개 위치를 기록하고 PR과 인증된 자기 상태 보고를 제출한다. 공통 계약/다른 담당 영역 변경은 PM과 먼저 조율한다. 기존 인증정보 분리·격리 검사 조건을 유지한다.

## PM 인수 기준과 남은 참가작

이미 선택 통합된 제품 소스는 PR151/main96c6d949다. PR153의 종료 근거는 실제 main5335c470에 병합했다. 역사 PR을 닫는 것은 원 PR 전체 병합이나 부모 작업 Done을 뜻하지 않는다. [PR 정리 근거](../../evals/pr-queue/20261006/README.md)의 고정 head·원본 SHA·개별 잔여와 현재 담당 배정을 함께 읽는다. PR136의 누락 근거 보호 규칙은 보완 요청으로 유지하고, PR140의 무인 Worker 개선은 OFF 동안 배포하지 않는다.

실모델 8건의 완료 결과는 0건이다. 먼저 판단 품질을 보완하고 같은 자료/실행 기록으로 웹·MCP·다섯 Skill·세 제품·조건 변경을 완주해야 한다. 저장된 출력의 HTTP/MCP 재생과 브라우저 검사 통과는 새로운 판단 성공을 입증하지 않는다. 독립 강한 LLM 기준선·전체 호출/재시도 비용·효율 측정·발표/영상/실행 ZIP도 남았다.

월별·계절별 동향은 필수 품질/연결 보완 뒤 진행한다. 자료 담당은 날짜·중복·분모·제품/기간 범위와 원문을, PM은 웹/MCP의 동일 집계 ID·계약을, 웹 담당은 그래프·드릴다운을, 코어 담당은 근거 있는 패턴/기획 가설을 맡는다. 현재 날짜 없는 리뷰36개로 실제 월별/계절별 수치나 판매량을 만들지 않는다. 합성 날짜를 쓸 때는 새 자료 버전으로 분리한다.

10/6 컨설팅 확정 안내는 팀장 수신 내용 확인이 남았다. 10/20 발표·영상·소스코드 ZIP의 정확한 제출 시각/경로/용량도 후속 확인한다. 부모 Done5·신청서31요구 verified0 상태는 이번 운영 정리로 바꾸지 않는다.
