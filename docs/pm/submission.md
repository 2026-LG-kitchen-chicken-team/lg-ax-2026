# 소스코드 제출 초안 패키지

P2-PM-006의 준비 도구이며 최종 제출 완료가 아니다. 특정 Git commit에 추적된 **전체 원본 파일**을 동일한 바이트로 포장하고 commit·Git blob·파일 SHA256·ZIP SHA256을 연결한다. 수정 중인 작업 공간과 추적하지 않은 파일은 포함하지 않는다. 현재 31요구 verified 0과 네 판단 Skill의 `NOT_IMPLEMENTED`는 이 도구로 바뀌지 않는다.

## 생성·검증·압축 해제

저장소 루트와 실제 고정한 commit을 사용한다. 아래 `COMMIT_SHA`는 실제 값으로 바꾼다.

```powershell
uv run python scripts/package_submission.py build --repo . --commit COMMIT_SHA --output private/제출준비/source-draft.zip
uv run python scripts/package_submission.py verify --repo . --archive private/제출준비/source-draft.zip
uv run python scripts/package_submission.py unpack --repo . --archive private/제출준비/source-draft.zip --destination private/제출준비/clean-source-draft
```

출력 ZIP·sidecar·해제 폴더는 해당 저장소 `private/` 안에만 만든다. 기존 파일·폴더를 덮어 쓰지 않으므로 다음 초안은 새 이름을 사용한다. 경로의 `..`·심볼릭 링크가 private 밖을 가리키면 중단한다. 도구 자체는 코드·설치·모델·네트워크를 실행하지 않으며 Git object의 자동 lazy fetch와 인증 프롬프트를 비활성화한다.

ZIP에는 전체 추적 소스와 `__submission__/manifest.json`, `__submission__/DRAFT_README.md`가 들어간다. 원본 README·공식 원본·문서·자료·모델 코드·다섯 SKILL.md·uv.lock·웹 package-lock은 필수다. 고정 정렬·1980년 메타데이터·Git 실행 비트·ZIP_STORED를 사용하므로 같은 commit과 도구에서 ZIP 바이트가 같다. ZIP 옆 `source-draft.zip.provenance.json`에는 ZIP SHA256과 내부 manifest SHA256·commit을 기록한다. 다른 파일명으로 생성한 sidecar의 파일명은 달라도 ZIP 내용은 같다.

`verify`는 ZIP SHA·원본 commit·전체 파일명·모든 내용·파일 SHA·Git mode를 대조한다. 단순히 manifest가 자기 내용과 맞는지만 확인하지 않는다. provenance를 위조하여 새 SHA로 바꾸어도 실제 Git commit과 파일이 다르면 실패한다. `unpack`은 검증을 먼저 수행한 뒤 새 폴더에만 쓴다. 입력 저장소의 Git history가 있어야 commit 원본과 대조할 수 있다.

## 중단 정책

추적된 위험 파일을 몰래 제외하지 않는다. 발견하면 초안 생성 전체를 실패시킨다. `private/`, `.git/`, `node_modules/`, `.venv/`, credentials·서명·접수증빙·제출준비 경로, 실제 환경 파일, 인증서 개인 키, DB, 추적된 심볼릭 링크·submodule을 거절한다. 실제 공동 작업실의 editor/viewer/admin-client.json·server-credentials.json도 차단한다. SQLite 내용과 인식 가능한 개인 키·서비스 토큰, JSON의 재귀적 token/access_token/bearer/password/api_key 등 실제 값도 검사한다. 빈 값·명시적 가림/placeholder·환경 변수 참조와 JSON Schema의 필드 정의는 실제 비밀 값으로 취급하지 않는다. 서명·동의서·작성 신청서의 복사본, 학번_이름 형식의 개인 PDF/HWP, 알려진 팀장 재신청·서명 보완본도 private 밖이라고 허용하지 않는다. 빈 공식 참가신청서 원본은 정확한 `자료/공식/` 원본 경로만 허용한다.

`.env.example`은 UTF-8 주석과 `NAME=`만 허용하며 값은 빈 값, `<PLACEHOLDER>`, `YOUR_NAME`, `REPLACE_ME`, `CHANGEME`여야 한다. 따옴표로 감싼 같은 placeholder도 가능하다. 실제 토큰, 비밀번호, 명령문·임의 설정 값은 거절한다. JSON의 학번 필드 8자리 숫자·연락처 필드 한국 휴대전화 번호도 차단하지만 임의 텍스트·이미지·PDF의 모든 개인정보를 자동 인식하지는 않으므로 PM의 최종 내용 검토를 대신하지 않는다. Git replace object도 비활성화하여 원래 commit 대신 로컬 대체 객체를 포장하지 않는다.

파일명은 UTF-8이며 상대 POSIX 경로를 사용한다. traversal·중복·대소문자/Unicode 충돌·Windows 예약 이름·비정규 ZIP 파일을 거절한다. 소스의 상한은 파일 10,000개·각 128MiB·합계 512MiB다. 넘으면 명시적으로 실패하며 일부 파일을 누락하지 않는다.

## 깨끗한 환경 재실행과 남은 제출 요건

압축 해제 폴더의 원본 `README.md`와 초안 안내를 먼저 읽는다. PM은 별도로 `uv sync --locked --dev`, 공통 계약·Skill 실제 검사·stdio MCP 호출, 웹 `npm ci`·테스트·빌드를 실행하고 입력/출력/해시와 한계를 남긴다. `.git`이 없으므로 과거 Git commit을 요구하는 하네스 증거 감사에는 원격 저장소 history가 필요할 수 있다. 이를 숨기거나 현재 파일로 과거 검증을 대체하지 않는다.

이 도구에는 `--final`이나 최종 제출 모드가 없다. 모든 산출물은 `draft=true`, `submission_ready=false`이며 설치/재현 성공도 자동 주장하지 않는다. 발표자료·영상·촬영 commit 일치·31요구 검증·독립 평가·최종 ZIP 검수·실제 제출과 접수 증빙은 별도 완료 조건이다. 따라서 이 도구를 만들었다는 이유로 P2-PM-006이나 R28을 완료 처리하지 않는다.

검사는 `uv run python -m unittest discover -s tests -p test_package_submission.py -v`로 실행한다. 시험의 위험 경로·키·DB·심볼릭 링크·악성 ZIP은 임시 Git 저장소의 합성 자료이며 실제 팀 개인정보·비밀키를 사용하지 않는다.
