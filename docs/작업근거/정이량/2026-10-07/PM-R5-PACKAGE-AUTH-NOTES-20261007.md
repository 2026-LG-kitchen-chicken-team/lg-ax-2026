# PM-R5-PACKAGE-AUTH-NOTES-20261007 근거

[원 source 스캔](../../../../evals/pm-prototype/20261007/r5-core/package-authorization/source-scan.json) SHA256은 `7190763b4fad00f28c015ceff8952ec8f881ba190fc8c5dfd275923154ee3df0`이다. 정확한 source는 `e1a6ec794039aca6278f415bd5aaef901cf3f920`, 1,700 JSON·62,457,306바이트, parse 실패·고정 secret pattern 일치 0, generic credential-field 일치 3이다. 원값은 출력하지 않고 값 유형·pointer·SHA와 비민감 문맥 단서만 저장했다. 이 숫자를 포괄적인 개인정보 검사 통과로 확대하지 않는다.

[성공 수신증](../../../../evals/pm-prototype/20261007/r5-core/package-authorization/validation-receipt.json) SHA256은 `20812599f9240c167a55761a32dca86bfee4afc0e6a30f193f69880d1522e0d6`, 검증 source는 `501734ef1a0639363243e1b1fe31309c875cf46a`, archive SHA256은 `a939484c0972beab1539202ea4d38f5c81b47830d475a29f01f8da3432cff268`이다. Docker image `sha256:5a234dd63a42d34e8ea3d47b93174be88d33635c34d07d048c66ce486ac831e5`, validator UID1000, network none, readonly root/workspace, cap drop, no-new-privileges, 인증/profile mount 0, source 변경 0, 모델/네트워크 호출 0을 기록했다. 18검사 PASS와 두 파일 ruff PASS다.

[초기 실패 수신증](../../../../evals/pm-prototype/20261007/r5-core/package-authorization/initial-lint-failure-receipt.json) SHA256은 `fc04ede878e2353883392a3fe046540f3ad2d8d21bdab3520375fc0b82edc54e`다. 당시 source `7da9050`에서 18검사는 통과했고 test의 SIM117 lint 한 건만 실패했다. 후속은 그 test formatting만 수정했으며 제품 script·원 역사 JSON은 그대로다.

[proof.json](../../../../evals/pm-prototype/20261007/r5-core/package-authorization/proof.json)은 code paths, 원 스캔/검증 source 구분, wrapper SHA, 원본 보존과 인수 한계를 묶는다. 실제 최신 source ZIP, PM 독립 검수·게시·병합·운영 통합과 의미 품질 판정은 이 한정 수신증으로 완료하지 않는다.
