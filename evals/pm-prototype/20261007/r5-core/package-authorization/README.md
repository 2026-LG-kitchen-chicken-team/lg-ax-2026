# 역사 승인 설명의 제출 초안 검사

기록 ID는 `PM-R5-PACKAGE-AUTH-NOTES-20261007`이며 PM 정이량의 보조 AI가 사용자 승인 아래 수행한 한정 수정이다. 다른 담당자의 수행이나 완료 상태를 기록하지 않는다.

`e1a6ec794039aca6278f415bd5aaef901cf3f920`의 Git 추적 JSON 1,700개, 62,457,306바이트를 저장소 코드를 import하지 않는 stdlib 메타데이터 검사로 읽었다. 기존 패키저와 같은 credential-field predicate에서 세 `authorization` 설명 필드가 걸렸다. 수행 승인·PM 검수·원본 보존 문맥으로 확인한 세 원본만 정확한 경로, 전체 파일 SHA256, JSON pointer, UTF-8 compact JSON scalar SHA256으로 고정한다. 경로 전체나 `authorization` 필드를 전역 허용하지 않는다. 원 역사 JSON·manifest 바이트는 바꾸지 않는다.

[source-scan.json](source-scan.json)은 필드 위치·값 유형·SHA와 고정 비민감 단어 분류만 보존하며 원값·키·주소·비밀번호를 포함하지 않는다. pattern match 0은 포괄적인 개인정보 안전 보증이 아니다. 전체 원문 검토를 자동 판정으로 대체하지 않는다.

검증한 코드 commit은 `501734ef1a0639363243e1b1fe31309c875cf46a`다. `scripts/package_submission.py`의 세 예외는 비밀 패턴·DB 내용 검사와 JSON 개인정보 전체 검사를 거친 뒤에만 적용된다. 파일 바이트나 승인 값이 바뀌면, 다른 경로에 복사하면, pointer/value SHA가 다르면 원 credential 검사가 그대로 거절한다.

[validation-receipt.json](validation-receipt.json)의 고정 Docker image `5a234dd…`에서 기존 13개와 새 5개, 총 18개 검사가 0.520초에 통과했고 두 파일 ruff도 통과했다. validator UID1000, network none, credential/profile mount 없음, readonly root/workspace, source_changed 없음, model/network calls 0이다. 회귀는 원본 세 기록 통과와 원문 불변, 다른 경로·파일 변조, 승인문 교체·같은 문서를 유지한 별도 credential, 잘못된 pointer/value SHA, 비밀 패턴·DB·학번·연락처 우선 거절을 확인한다.

초기 `7da905038eb5e7dacc12340e45256801e68f4d3c`도 18개 검사는 통과했으나 ruff SIM117 한 건이 실패했다. [원 실패 수신증](initial-lint-failure-receipt.json)을 보존하고 test의 중첩 `with`만 합쳤다. 제품 script는 두 commit 사이에서 동일하다. 상세 SHA와 범위는 [proof.json](proof.json)을 따른다.

이 인수는 패키저의 한정 회귀다. 실제 최신 통합 소스의 ZIP 생성·검증은 PM의 별도 최종 source pin에서 수행해야 한다. 모델 품질, 기획 accept, 프로젝트 Done, 외부 게시나 운영 배포 완료를 주장하지 않는다.
