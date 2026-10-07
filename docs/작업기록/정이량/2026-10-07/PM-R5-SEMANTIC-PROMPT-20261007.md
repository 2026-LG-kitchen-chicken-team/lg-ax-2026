# PM-R5-SEMANTIC-PROMPT-20261007

수행자는 PM 정이량 보조 AI다. root의 실제 원3 재검증에서 발견된 `prompt_too_large` 회귀 수정만 수행하며 황대겸의 작업이나 검수 수행으로 기록하지 않는다. 다른 팀원의 기록·공유 계약·API/MCP·운영·model_client·prompt_context 모듈을 편집하지 않는다.

고정 Qwen3.5 122B/원10후기/Need9·Gap9·후보3의 정상 사례는 모델 응답4개 뒤 semantic_review의 요청 준비에서 기존24,000자 상한을 넘었다. 의미 검수 응답이 없으므로 의미 판단이 틀렸다고 판정하거나 정상 품질 통과로 바꾸지 않는다. 변경 사례는 다섯 응답 뒤 의미 검수 응답 유실로 비용이 불명이고, 부족 사례는 한 응답 뒤 두 번째 호출이 전송 전에 취소됐다. root의 원 대장과 중단 비용은 그대로 둔다.

semantic_review 전용 문맥에서 후보별 links의 동일19필드를 `columns`와 `values`로 무손실 표현한다. 각 행의 gap_id와 읽는 순서·정확 복원 방법을 전달하며 원문·필수 인용 그룹·Need/Gap/Concept 선언·지원/해결/불확실성 정보를 모두 보존한다. 실제 제출한 투영을 model_calls.prompt_context에 기록하고 full request_context와 trace는 유지한다. 기존 의미 검수 규칙·원 실패의 거절·스키마·실행 순서·최대2수정·모델·요청 상한을 바꾸지 않는다.

local code source `0df1f384ebb1f44d13744b8f3b35df821bcfd00e`에서 기존 원 실패 회귀와 새 준비 회귀를 포함한197건이 고정 zero-auth/network-none/readonly Docker에서 통과했다. 실제 StructuredModelClient의 formatter와 같은 ModelConfig16384/8192·seed42를 거친 요청은23,793자/33,142UTF8바이트로 동일24,000자/45,000바이트 상한을 통과했다. capturing adapter가 전송 직전에 중단하므로 모델 생성0이며 의미 판정을 생성하거나 승인하지 않았다. 문자 여유207이므로 더 큰 문맥·실제 모델의 표 해석·의미 품질은 별도 검증 대상이다.

근거는 [동일 ID의 작업근거](../../../작업근거/정이량/2026-10-07/PM-R5-SEMANTIC-PROMPT-20261007.md)와 `evals/pm-prototype/20261007/r5-core/semantic-prompt-*`다. 새 모델 호출·원 출력 변형·ledger 초기화·게시·push·병합·서비스 배포는 하지 않았으며 root의 독립 인수로 넘긴다.
