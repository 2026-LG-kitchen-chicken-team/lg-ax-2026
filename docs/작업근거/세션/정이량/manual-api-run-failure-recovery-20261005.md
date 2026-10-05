# PM-MANUAL-API-RECOVERY-EVIDENCE-20261005

확인일: 2026-10-05 KST. 관련 작업은 Issue #121 / `dev-pm-api-run-failure-contract`이며, 이 문서는 별도 PM 수동 회수 근거다.

## 고정 원본과 사용량

- 원 base commit: `7652048327d8bf20410af14e6f78979b8f721d63`
- 원 소스 snapshot digest: `823fd8a9b243276175b8bdc79451902252d5c43c06b15061aa42437bbc1808c7`
- 원 base snapshot digest: `e913917bd9cca3ed3283adec73c17d2f96fa158c19dbe703314e87eb295ce794`
- 원 테스트 파일 SHA256: `d1e478a80e96a85f28d8367a4dfb5bdccb1ea43f715253b1ca8441d1ffb55ca2`
- 원 모델 사용량: 입력 1,185,931 / 캐시 입력 1,079,552 / 출력 15,027 / 총 1,200,958 토큰.
- 추가 모델 호출: 0. 원 job/run/출력·개인 OFF·blocked·halt·사용량은 변경하지 않았다.

원 checkpoint와 agent usage, 고정 검사 로그를 읽었다. 모델과 두 검사 모두 exit 0이며, 검사들은 각각 6개 테스트를 통과했다. 이후 게시 전 소스 탐지가 새 합성 Bearer fixture를 거부했다. 원 controller 결과는 blocked 수락, publication 수신증은 없음이다. 이 기록은 실제 게시·인수·부모 완료를 입증하지 않는다.

## 최소 수정과 무결성 검사

게시 규칙은 변경하지 않았다. 테스트의 module-level `SECRET` 문자열을 실행 시 조합하는 표현으로만 바꾸었다. 합성 입력의 실제 값은 공개 기록에 넣지 않았다.

- AST에서 원 할당 한 곳과 새 join 표현을 검사했다.
- 수정 전후 합성 입력의 실행 시 바이트가 동일하다.
- 그 외 생성 소스 파일의 바이트는 동일하다.
- 해당 원 생성 변경은 API 서버, 새 실패 계약 테스트, 담당자 의도 기록, 담당자 근거 기록의 4개 파일이다.
- 이 별도 회수 의도·근거 문서 2개를 추가했다.
- 변경 소스에 게시 거부 패턴이 남지 않는 것을 확인했다.

## 고정 재검사

명령은 고정 개발 capability와 원 checkpoint의 argv가 일치하는 것을 확인했다.

1. `uv run --offline --no-sync python -m unittest tests.test_api_run_failure_contract -v`
2. `uv run --offline --no-sync python -m unittest tests.test_workspace_api -v`

실제 수동 재검사는 두 명령 모두 exit 0·stopped_reason 없음으로 통과했다. 각 명령은 6개 테스트를 실행했다. `validator` 역할·네트워크 `none`·인증 마운트 없음·불변 이미지·고정 자원 제한으로 검사했으며, 실행 후 검사 소스 바이트가 동일한 것을 확인했다.

- 실제 검사 snapshot digest: `cd8743d64c5e7f40f8180eea7fcd1738a8c09db50f65cae2f69d25b3b7df1ade`
- 검사한 API 서버 파일 SHA256: `50d33c6ebee44f0b8d611a4cb15a537a3561fec0004d92cfd9a0922b6cdce71d`
- 검사한 테스트 파일 SHA256: `e42588beb010ea9b4eb5e210809cc05a9943e949052a7cc0239be70b0de01d28`
- 실제 고정 검사 수신증: PM 비공개 `private/runtime/manual-pm-api-recovery-20261005/validation-proof.json`
- 추가 모델 호출: 0. 원 자동 실행의 결과·상태·사용량을 다시 작성하지 않았다.

검사 snapshot에는 검사 전 수동 기록이 포함된다. 검사 후 이 결과 문단을 덧붙였으며, 위 두 구현 파일의 바이트는 검사 당시와 같다. 초기 검수 보조 스크립트의 중복 snapshot 읽기를 고쳐 최종 수신증은 각 검사 직후 저장했다. 이 로컬 보조 절차는 원 Worker나 PM 서비스를 변경하지 않았다. PR 게시·실제 CI·독립 PM 검수·병합 후 통합은 남아 있다.
