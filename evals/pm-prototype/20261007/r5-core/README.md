# R5 CORE 근거 연결·누락 주장 회귀

수행자는 PM 정이량의 보조 AI다. 황대겸의 개발·검수 수행이나 그의 개인 기록으로 대체하지 않는다. 사용자 2026-10-07 후속 '모두 진행해' 지시와 PM의 좁은 R5 분할에 따라 base `1f3f4ecb93fdd945850a1e9f790bc37766b2355c`에서 판단 코드·관련 Skill·회귀만 보완한다.

`counterexamples.json`은 원 3실행의 선택 필드를 그대로 복사한 회귀 입력이다. 새로운 모델 실행·수정 출력·품질 통과 기록이 아니다. 원 전체 JSON의 정본은 PM 인계 commit `814fe2fbcd3b752ff6400d8a08671dce7bdd2d80`의 `evals/pm-integration/20261007/live-originals/`에 있으며 `.gitattributes -text`로 원바이트를 유지한다. 선택 필드의 추출 manifest가 포함하는 원 SHA는 정상 `5625c0ff13d7e4282cbe7e6eb3ea0aa43d848cec8bf3d47c45845cf32d670f3d`, 변경 `95833e754b034d7f0ec6749c549fb3f2f80ca3fa240d5bc1c98d80b49c8046e5`, 부족 `d4a7af4f3a881256e0af779174518c1e3e0176ed86a0b9e923bcf6f833ebb688`다. 원 실행 source는 `de09b64ca72d5ae918cc0a95f244b0e0562761b0`이며 synthetic 10-review 개발 사례다.

회귀는 변경 후보 2회에서 MANUAL001 누락과 정확한 Gap/Need 피드백, 정상 semantic reviewer의 REVIEW008 누락, 정상 review_revision의 질문 없는 hold, 부족 사례의 NEED006 존재와 모순되는 구조화된 누락 주장을 검사한다. 원 no-candidate 선언은 신규 내부 검수 선언 shape를 충족하지 않는다. 같은 원 질문에 누락 주장 ID를 명시한 파생 반례와, 작성자가 직접 만든 바른 자료 부족 선언을 각각 구분한다. 자유문장 전체의 의미 정확성을 코드로 증명하지 않으며, 잘못된 질문 유형으로 허위 주장을 숨기는 모델 오류는 별도 독립 의미 검수 대상이다.

후보별 요구표는 선택한 Gap의 근거만 요구한다. 차이 판정의 인용 그룹은 기존 canonical 의미 검수와 같은 각 Gap 리뷰·설명서·연결 기능 설명서 대조를 요구한다. 신규성·극성·작동 방식·지원/해결·불확실성은 모델 판단으로 남으며 자동 인용, forced accept, 검사 완화는 없다. 실행 순서·공유 최대 2수정·모델 설정·공유 계약·API/MCP·운영은 변경하지 않는다.

검사는 고정 source proof를 대조한 `DockerExecutor`, image `sha256:5a234dd63a42d34e8ea3d47b93174be88d33635c34d07d048c66ce486ac831e5`, validator 역할, auth/profile 없음, network none, readonly source에서 수행한다. 실행 wrapper는 저장소 밖의 PM metadata wrapper다. host에서 저장소 코드·테스트·빌드·설치를 실행하지 않는다. 검사 결과는 이후 고정 commit/receipt로 기록한다. Ollama native 조건 스키마 지원과 실모델 원3 품질 인수는 아직 검증 전이며 새 모델 호출은 0이다.
