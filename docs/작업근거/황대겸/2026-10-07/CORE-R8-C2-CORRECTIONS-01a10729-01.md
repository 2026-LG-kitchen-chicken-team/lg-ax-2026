# CORE-R8-C2-CORRECTIONS-01a10729-01 — 검증 근거

담당 황대겸 / unknownamed, 2026-10-07. [같은 ID 상세](../../../작업기록/황대겸/2026-10-07/CORE-R8-C2-CORRECTIONS-01a10729-01.md).

- [PM CORE 인계 원 댓글](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/4#issuecomment-6039619224), main `ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f`를 기준으로 담당 경계를 확인했다.
- [58검사·Ruff·소스 해시](../../../../evals/core-manual-quality/20261007/r8-c2-corrections/verification.json), [재현기](../../../../evals/core-manual-quality/20261007/r8-c2-corrections/verify_boundaries.py), [실제 수신 요약](../../../../evals/core-manual-quality/20261007/r8-c2-corrections/boundaries.json)을 보존한다.
- 기존 실제 공개 후기837305와 M11, 실제 Qwen 오류 문장을 재사용했다. 테스트 전용 ID·역할 연결은 고객 데이터/콘셉트 생성이나 의미 채점이 아니다. shared2·원 응답/facts·정상 이웃·스키마·반대 출처 슬롯 보존을 검사했다.
- 실제 adapter/client HTTP MockTransport에서도 공유2가 적용된다. 같은 경로의 전체 schema mismatch 시 정상 이웃 복구/data 전달은 아직 실패한다. 이 미완료를 통과 검사로 숨기지 않고 PM 경계 후속으로 남겼다.
- 소스-only Docker image `sha256:36ad082dbccf05bc9cff7c4dc5766e9ab7ed8c42198b0b731cf3831c546aaaf0`, UID65534, network=none, read-only, cap-drop ALL, no-new-privileges, 무인증을 사용했다. 호스트는 native Git/게시/원 파일 해시 orchestration만 수행했다.
- 변경은 CORE2파일·관련 tests3파일·이번 개인 문서/근거다. `model_client.py`/`prompt_context.py`·공통 계약/API/MCP·DATA/WEB·운영 설정은 변경하지 않았다. 새 실모델·합성 리뷰·forced accept·자동 의미 치환·여섯 사례 재채점0이다.

[PR247 원 실패 근거](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/247)와 PR248 인쇄 근거·과거 usage는 유지한다. 현재 구현/58검사 PASS는 실제27B 품질·PM 인수·전체 Done을 뜻하지 않는다. PM native 전달과 기존 실제 응답/usage 인계 후 해당 필수 작업을 이어간다. 사용자 추가 판단 대기는 없다.
