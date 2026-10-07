# R8 CORE — 공유 수정 예산·부분 응답·반대 출처

PM의 [CORE 인계](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/4#issuecomment-6039619224)와 main `ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f` 이후 담당 C2/C3 잔여를 보완했다. 이전 [PR247](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/247)의 e04/5fdb 실패 근거는 수정하지 않는다.

- 생성 경로의 항목 간 수정, 같은 저장 run의 후속 피드백 수정이 기존 `CorrectionBudget` 최대2를 공유한다. 실패도 한 번으로 기록하고 후속 수리에서 초기화하지 않는다. 새로운 사용자 조건 변경 요청의 생성 run과 기존 run의 수리를 구분한다. 중앙 비용·STOP 설정은 변경하지 않는다.
- 호출자에게는 기존 전체 JSON Schema를 전달한다. CORE에 반환된 응답은 봉투 구조·최대 항목 수를 검사한 뒤 각 항목의 전체 스키마·출처·기존 주장 검사를 수행한다. 잘못된 항목만 보류하거나 허용된 필드를 한 번 수리한다. 정상 이웃·원 응답·facts를 보존하며 ID와 문제 연결을 수리하지 않는다.
- 기획의 기존 고객 출처 슬롯2개에 지지 출처와 제공된 반대 출처를 각각 하나씩 남긴다. 출처 역할은 자동 감정 판정이나 문제의 의미 승인이 아니다.

[검사 수신](verification.json): 소스만 읽는 고정 Docker, UID65534, network=none, read-only, 무인증에서 관련 코어·API·MCP58검사 PASS, Ruff PASS. [경계 결과](boundaries.json)는 기존 실제 후기837305/M11과 실제 오류 문장을 재사용했다. 세 오류 항목에서 수리2회, 정상 원문 복사와 title 누락 이웃에서 정상 항목 보존을 확인했다. 새 후기·콘셉트·실모델 호출·독립 AI 채점은0이다. 검사 전 실패 수신과 원 결과는 비공개 기록에 보존했다.

## 남은 실제 클라이언트 경계

`StructuredModelClient.generate()`는 모델 응답 전체를 검증하고 `schema_mismatch`를 던진다. 이때 `PublicPlanner`는 원 data/usage를 받지 못한다. 실제 OllamaAdapter를 HTTP MockTransport로 실행한 회귀 검사는 이 경계를 그대로 확인한다. **native 경로의 정상 이웃 복구는 아직 미구현이다.** 실제 모델 실행·품질·PM 인수·legacy exact-model 전체 후보 삭제 해결을 완료로 보고하지 않는다.

PM에는 동일 pin/native schema/전송 보호를 유지하면서 구조화된 후보 응답과 항목별 거절을 CORE가 검수할 수 있는 명시적 전달 경계를 요청한다. PM 소유 `model_client.py`·`prompt_context.py`, 공통 계약/API/MCP는 편집하지 않았다. C1 기존 실제 run의 원 응답·usage·HTTP/MCP 동일 버전 인계, C3/C4 실제 의미 검수, X1 실제 기획 설명서는 계속 필요하다.

재현기는 [verify_boundaries.py](verify_boundaries.py)다. 저장소 코드를 게시 인증 호스트에서 실행하지 않고 위 고정 무인증 Docker에서 `/src` 소스 mount와 `PYTHONPATH=/src/packages/core/src:/src/packages/contracts/src:/src/tests`로 실행한다. 산출 JSON의 소스·스키마 해시를 확인한다.
