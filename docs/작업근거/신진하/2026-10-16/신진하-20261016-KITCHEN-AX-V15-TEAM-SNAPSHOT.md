# KITCHEN AX 버전 15 보존 근거

- 기록 ID: 신진하-20261016-KITCHEN-AX-V15-TEAM-SNAPSHOT / 2026-10-16 KST
- 원본: `2026-LG-kitchen-chicken-team/lg-ax-harness` 커밋 `1c63408e4f7d5d5aa72fc4ffb227e5689b2e1923`, 추적 파일 74개
- 공개 배포: Site 버전 15, source `95ac63c4ddb13ff06591bbadce2551a984097a25`
- 대상: `2026-LG-kitchen-chicken-team/lg-ax-2026`, 기존 보존 커밋 `ad0d9d02f73ef85ecd669e66b67da2c998ff4c6b`에서 새 브랜치
- 현재 원격 main 조회: `eab85d48385f965eef48c07a6cdd8f6fd9851c62`; main에 쓰지 않는다.

## 권한 조회

기존 Git 인증으로 GitHub REST `GET /repos/{owner}/{repo}/collaborators/choigilung/permission` 실제 HTTP 200, permission `write`를 확인했다. 두 저장소의 collaborator 목록도 HTTP 200이었다. 팀 저장소의 정이량 Admin, 황대겸/최길웅/신진하 Write를 확인했다. 권한 변경은 없으며, 이 값은 조회 시점의 GitHub 응답이다. 단순 문서상의 역할 이름을 실제 권한으로 간주하지 않았다.

## 이번 검사

`git archive`로 고정 커밋의 app prefix만 ZIP으로 읽고 안전한 대상 하위 경로에 추출한다. 각 파일의 길이와 SHA-256을 [manifest](../../../../대시보드%20신진하/versions/v15-20261016.manifest.json)에 기록했다. 검증 도구에서 ZIP 원바이트/추출 파일/manifest의 74개 지문 일치와 기존 v5 파일 불변, 허용된 개인 기록·새 보존 폴더 밖 변경 0을 확인한다. Git 메타데이터·Site identity·의존성·빌드 출력·인증·개인 실행 DB/로그는 포함하지 않는다.

원본의 회귀 102/102·Vite build·독립 재검토는 [원본 검증 기록](../../../../대시보드%20신진하/versions/v15-20261016/docs/factory-motion-validation.md)에 있는 선행 결과이며 새 모델 호출이나 이번 팀 제품 인수 검사로 세지 않는다. 파일 저장은 개인 브라우저 저장 기록을 이관하거나 실제 CLI 작업을 실행하지 않는다.

## 실제 최종 검사 결과

- 고정 원본 ZIP 대조 도구 exit 0: 소스 74/74 원바이트·길이·SHA-256 일치, 기존 v5 파일 35/35 불변, 신규 안내 링크 7개 유효, 개인 README 원문 보존 2개, 범위 밖 변경 0.
- `python scripts/check_document_navigation.py` exit 0: 원바이트 archive 5개/161,753바이트, heading 104개, 원문 기준 링크169개, 현재 입구6개 검사. 보호파일 일회성 대조·원 commit 직접 대조 옵션은 실행하지 않았다. 모델/네트워크 호출0.
- `git diff --check` exit 0. 검사 과정의 누락 blob 읽기는 같은 대상 팀 저장소로 한정했으며 다른 저장소의 원격 쓰기는 없었다.

스테이징 후 기본 공백 검사에서는 snapshot의 보존된 CRLF를 공백으로 판정해 실패했다. 원본 바이트를 바꾸지 않고 `git -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --cached --check`로 줄바꿈을 명시한 재검사는 exit 0이다. 저장소 전역 설정은 변경하지 않았다. Git index blob도 원본 74개와 일치하는지 대조한다.
