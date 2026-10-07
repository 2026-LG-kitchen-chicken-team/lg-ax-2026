# 실제 자료 기반 시각 기획 화면 W1

2026-10-07 현재 채팅의 수동 지원 구현이다. 실제 팀원 최길웅의 직접 작업 성과로 기록하지 않는다. 자동화·원격 작업자·운영 서비스는 변경하지 않았다.

## 연결한 흐름

앱 첫 진입과 왼쪽 `실제 자료 기획` 메뉴에서 시작한다. 실제 공개 자료 묶음 → 목적·제약 → 문제·반대 근거 → 기존·경쟁 대조 → 개선 전후 사용 단계·장면 카드 → 조건 변경과 수정 이력 → JSON/Markdown 내보내기를 연결했다. 불편의 사전 입력을 요구하지 않는다.

새 흐름은 공통 `research-planning.schema.json` 1.0의 ResearchBundle/PlanningBrief를 소비한다. 계약·CORE·API 구현은 수정하지 않았다. 기존 다운로드 함수를 재사용하며, 기존 근거 대조·콘셉트·수정 이력 화면은 각 기존 계약을 유지한다. 연구 자료를 기존 정확 SKU 판단 입력으로 임의 변환하지 않는다.

## API와 인증

- `GET /api/research/bundles` → `{bundles:[{bundle_id,product_group,analysis_scope,source_count?,review_count?,title?,...}]}`
- `GET /api/research/bundles/{bundle_id}` → ResearchBundle
- `POST /api/research/planning-runs` → PlanningBrief 직접 응답. 입력 `{bundle_id,goal,constraints,previous_run_id:null|string}`
- `GET /api/research/planning-runs/{run_id}` → PlanningBrief

ResearchClient는 토큰을 화면 생명주기에만 존재하는 메모리 클로저에 보관하고 Bearer로 전송한다. 토큰을 localStorage·파일·내보내기에 저장하지 않는다. 새 연결은 bundles부터 검증하며 기존 bootstrap/합성 예시 자료에 의존하지 않는다. `/api/research`는 기존 `LGAX_WORKSPACE_PROXY`로 프록시한다. 통합 검사 예정 주소는 workspace `http://127.0.0.1:18969`, 웹 `http://127.0.0.1:5175`이며 해당 웹 Origin은 서버가 허용해야 한다.

API 미구현·연결 실패·인증/권한 오류는 명시적으로 표시한다. 정상 기획 결과를 하드코딩하지 않는다. POST는 자동 재시도하지 않으며 중복 클릭도 동일 실행을 다시 보내지 않는다. 연결 해제·화면 이동 후 지연 응답은 표시하지 않는다. 이미 서버에서 시작한 요청의 취소까지 보장하지는 않는다.

## 표시 범위

원문 링크·자료 유형·페이지 모델과 구매 모델·날짜 기준·발췌/전체 범위·문서판을 구분한다. 알려지지 않은 SKU·게시일·건수는 미확인으로 남긴다. 원문 키워드 필터는 공백으로 나눈 단어가 모두 포함된 원문을 찾는다. 긍정·불편/부정·혼합 요약과 각 source_ids를 표시하며, 해당 요약이 없으면 없다고 표시한다. 수집 manifest는 접어서 원래 한계를 확인할 수 있다.

기획 결과의 자료/제품군/분석 범위와 source_ids 연결을 검증한다. 목록에서 제공한 bundle_sha256도 결과 runtime의 지문과 대조한다. 조건 변경은 현재 선택한 run_id와 previous_brief_id/revision에 연결하며 목적·조건이 변경되지 않았으면 다시 보내지 않는다. 이력은 현재 연결에서 확인한 기록이며, 저장된 실행 ID로 서버 기록을 다시 열 수 있다. JSON은 선택된 bundle/brief 원문을 보존하고 Markdown은 같은 수정의 근거·대조·단계·장면·가정·검증 질문을 내보낸다.

`visual_scenes`는 개선 전후 장면을 비교하는 카드와 단계 목록이다. 실제 제품 영상·렌더링 이미지를 생성하지 않으며, 제안 장면을 검증된 성능으로 표시하지 않는다. 그래프·설명서 작성·영상 생성은 후속이다.

## 검사와 남은 인수

추가 검사는 실제 LG 공개 DOM 후기 원문을 기존 커밋 자료에서 읽어 사용한다. 테스트 응답은 명시된 보류/추가 자료 상태의 transport·rendering 검사이며 실모델 성능 검증이 아니다. 합성 리뷰를 만들지 않았다.

검사: TypeScript/production build 통과. 신규 계약·클라이언트·DOM 상태 10개와 실제 DATA bundle 3개의 읽기 전용 intake 검사를 포함한 13개 검사 통과. 실제 intake 경로는 DATA 작업트리의 `data/research/r8-public-research-20261007/bundles`였다. `LGAX_RESEARCH_INTAKE_DIR` 환경변수를 이 폴더로 설정해 `npx vitest run src/research.test.ts src/researchFlow.test.ts src/researchIntake.test.ts`로 실행했다. 환경변수가 없으면 외부 DATA 인수 검사 3개만 건너뛴다.

Qwen API의 실제 브라우저 전 과정은 통합 서버 준비 후 별도로 확인해야 한다. 초기 화면을 실제 자료 기획으로 바꿨으므로 기존 화면 검사의 진입 단계에 `근거 대조` 메뉴 선택을 추가했다. 기존 5개 App 검사 파일의 진입 helper와 9개 브라우저 시나리오 파일의 첫 메뉴 단계만 수정했으며 기존 기능·합성 예시 본문은 변경하지 않았다. 영향을 받은 UI 검사와 새 첫 화면 검사만 이름으로 선택해 31개 통과했고 관련 없는 37개는 건너뛰었다. TypeScript 검사와 Playwright 11개 시나리오의 `--list` 수집 검사도 통과했다. 이 목록 검사는 브라우저 실행을 뜻하지 않는다.

기존 전체 530 검사 반복 실행은 하지 않았다. 번들 500kB 경고는 빌드 실패가 아니며 후속 화면 분할 대상으로 남겼다.
