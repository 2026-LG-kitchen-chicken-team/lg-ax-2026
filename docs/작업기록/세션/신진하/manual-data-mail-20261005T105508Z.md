# manual-data-mail-20261005T105508Z — 수동 복구 작업기록

## 재개 요약

- 담당자: 신진하. 수행 AI: Codex 단일 모델, `/workspace`. 세션 기준 시각: 2026-10-05 19:55:08 KST. 종료 기록: 2026-10-05 20:08 KST.
- 직접 사용자 승인으로 두 자료 API와 합성 테스트를 작성했다. 상태는 **구현 작성·소스 검토, validator 실행 대기**다. 개별 검사 통과/자동 PR 완주/부모 Done/실모델 평가/최종 제출을 선언하지 않는다.
- 다음 행동: 인증 없는 별도 validator가 아래 두 테스트와 기존 계약/문서 회귀를 실행하고 실제 결과를 별도 기록한다. 이 모델 컨테이너는 테스트를 실행하지 않았다. 현재 실행 중인 프로세스나 서버 변경은 없다.
- 근거: [동일 세션 근거](../../../작업근거/세션/신진하/manual-data-mail-20261005T105508Z.md). 기존 blocked Git128·예산·자동 실행 이력은 보존했다. controller lease를 발급받거나 가장하지 않았다.

## 사용자 원 요청과 PM 지시 출처

실행자가 모델에게 전달한 지시 발췌(사용자 실제 발화와 구분):

> 사용자 직접 승인으로 PM 메일의 두 작업을 수동 복구합니다. 자동 controller lease를 가장하지 않으며 이전 blocked 실행/예산/기록은 그대로 보존합니다.
> AGENTS.md/CLAUDE.md와 아래 관련 현재 코드/계약을 먼저 읽고 원 지시를 좁게 구현하세요. GitHub/controller/메일/인증파일에는 접근하지 말고 commit/push/병합/서버 상태 변경을 하지 마세요. 테스트 실행은 auth 없는 별도 validator가 수행하므로 이 모델 컨테이너에서는 테스트를 실행하지 마세요.

사용자가 전달한 PM 원 지시(메일 자체는 접근 금지이므로 직접 대조하지 않았음):

> PM-20261005-AUTO-7f4770dc93e76d05 (Issue13 comment5991958336): review_import 모듈에서 승인된 제품 모델과 실제 새 리뷰 CSV를 크기/행 수 한도 안에서 파싱·정규화한다. 기존36개와 같은 내용만 허용하는 전송 도구와 구분한다. UTF-8/BOM, 따옴표/쉼표/한글 다중행, 중복 ID, 승인하지 않은 모델, 없는 출처, 빈/틀린 필드/손상 encoding/한도초과를 검사한다. 행 위치와 원문 SHA256을 보존하며 원문의 수식/명령문은 데이터로만 보존한다. 기존 review_csv/documents/계약의 실제 필드/타입과 호환되는 재사용 가능한 API를 만든다. 외부 입력을 바꿔도 반환 snapshot/원문 위치가 오염되지 않게 한다.

> PM-20261005-AUTO-1ff99fd83676d52a (Issue13 comment5992248482): source_ranges 모듈에서 인용문이 보존된 원문의 실제 페이지/행/문단 범위에 존재하는지 확인한다. 잘못된 위치, 존재하지 않는 인용, 삭제/변경된 원문, 동일 글의 다른 버전, 한글 다중행을 명시적으로 구분한다. 현재 document_store/documents/계약의 원문 locator/hash/version 의미를 읽고 실제 재사용 가능한 검증 API로 구현한다. 무조건 성공·고정 mock·PDF/OCR 구현 성공 주장을 만들지 않는다.

추가 직접 제약 발췌:

> 허용 편집은 아래 네 파일과 자기 두 세션 문서뿐이다. 다른 파일·공통 schema·AGENTS·설정·의존성은 변경하지 않는다.
> 테스트는 실패/변경 입력과 원문 위치/해시/버전 경계를 실제로 구분하는 의미 있는 검사로 작성한다. 두 모듈의 새 공개 함수 사용 예도 테스트에 포함한다. 필요한 fixture는 테스트 안의 synthetic 값으로 작성하고 실제 고객 자료로 표현하지 않는다. 표준 라이브러리와 이미 잠긴 의존성만 사용한다.
> 제한은 단일 모델 실행·900초이며 하위 에이전트/추가 네트워크 호출을 만들지 않는다.

## 수동 복구 해석과 범위

로컬 재사용 API 구현과 테스트 작성만 승인받았다. 일반 운영 지침의 온라인 status/report·인증 확인·commit/push·하네스 완료 변경보다 이번 직접 금지 지시를 우선했다. PM 메일 ID는 사용자가 제공한 추적 식별자이며 자동 lease/인증된 PM 메일 조회 증거가 아니다. 실제 새 입력을 처리할 API를 만들되 새 실제 고객 자료를 수집하거나 확보했다고 주장하지 않는다.

읽은 근거는 AGENTS.md/CLAUDE.md, README·인수인계·대회요건·진행체크리스트, 개인 기록/근거 요약, 작업기록 규칙, review_csv/documents/document_store/store/errors 및 공통 계약·검증 코드, 기존 문서 등록 테스트다. GitHub/controller/메일/인증파일은 조회하지 않았다.

## 실제 코드 행동

1. `packages/core/src/lgax_core/review_import.py`: `import_review_csv`와 `ReviewImportResult` 추가. 기존 FIELDS 그대로 받아 새 리뷰/근거를 생성하고 현재 Review/Evidence/Product 및 DocumentStore 계약을 사용한다. 등록 승인 제품·출처와 모델/버전/source_kind를 대조한다. 원본 바이트와 SHA256, 물리 시작·끝 행, 리뷰 문자열 SHA256을 보존한다. UTF-8 BOM은 디코딩 단계에서만 제거하고 원본 해시에는 포함한다. CSV 인용 해제 외 텍스트 정규화나 실행을 하지 않는다. 전체 바이트/리뷰 수 한도, 빈 필드·행/열·ID/출처/모델·버전·위치 오류를 구분한다. 반환 JSON snapshot과 입력 메타데이터를 분리하고 store마다 새 복사본을 만든다.
2. `packages/core/src/lgax_core/source_ranges.py`: `capture_source`, `SourceSnapshot`, `verify_source_range` 추가. 현재 원문 바이트를 필수 인자로 받아 삭제(None), SHA 변경, 버전/출처 불일치, 문자 위치/행/문단/절 범위, 인용문 SHA와 원문 부분문자열을 검사한다. 범위 밖 인용을 전체 문서 검색 성공으로 대체하지 않는다. UTF-8 원문은 직접 디코딩하고 외부 추출 페이지는 caller_supplied_extraction으로 구분한다.
3. `tests/test_review_import.py`, `tests/test_source_ranges.py`: 새 공개 함수 예, 현재 계약 호환, 다양한 잘못된 입력, 외부 입력/반환값 변경, 같은 원문의 다른 버전, 한글 다중행과 CRLF, 위치/인용 실패 테스트를 합성 값으로 작성했다. 테스트 실행은 하지 않았다.
4. 허용된 자기 두 세션 문서만 기록했다. 공통 schema·설정·의존성·과거 개인 문서·자동 실행 상태는 수정하지 않았다.

## 자기 소스 검토와 예정 검사

소스 검토에서 기존 DocumentStore의 내부 인덱스가 입력 참조를 사용할 수 있음을 읽고 import snapshot을 JSON으로 분리하고 새 store를 반환하도록 했다. CSV logical record 번호와 실제 물리 행 번호가 다르므로 reader.line_num으로 시작/끝 행을 계산한다. Source Locator에는 end 필드를 넣을 수 없어 별도 origin에만 end_row/문단/문자 범위를 둔다. bool을 위치 정수로 받아들이지 않으며 문자 offset은 Python 문자 단위로 명시했다. 원문 SHA와 인용문 SHA를 혼동하지 않았다.

예정 검사(미실행): 두 새 unittest, 기존 test_document_registration·test_document_plan_history·계약 회귀. 성공/실패/개수/CI 상태는 validator 실제 실행 뒤 판단한다. 본 세션의 파일 읽기·코드 작성·sha256sum은 기능 테스트 성공의 근거가 아니다.

## 실패 이력·한계·다음 행동

- Git128: 사용자 제공 복구 배경과 로컬 기존 기록에 DATA blocked 이력이 있다. 이번 세션에서 Git 명령이나 인증 진단을 실행하지 않았으므로 원인을 특정하거나 복구 성공으로 바꾸지 않았다. 원 실행/예산/원 기록을 수정하지 않았다.
- 두 새 세션 디렉터리는 초기 로컬 목록 조회에서 없다고 나왔고, 허용 세션 파일 생성으로 만들었다. 이 조회 실패는 Git128과 별개다.
- 새 API는 자동 서버/도구 등록이나 원본 영구 저장을 수행하지 않는다. CSV source approval은 호출자의 신뢰 경계이며 같은 자료 버전/source_kind를 가진 승인 제품을 요구한다. 실제 고객 자료/다른 버전 결합은 후속 인수 범위다.
- 외부 PDF 추출 pages는 호출자가 해당 원본에서 신뢰해 추출한 값이어야 한다. 원문 바이트 hash와 위치는 검사하지만 추출 정확도/PDF/OCR 구현 검증은 아니다. section 라벨은 명시적인 범위 등록 없이는 거부한다. source_ranges는 텍스트 페이지용이며 CSV 따옴표 해제된 셀을 원시 CSV 페이지와 동일시하지 않는다.
- 다음 담당은 auth 없는 validator. 실제 검사 결과와 차단 결함을 기록하고 필요하면 허용 범위 수정으로 돌아간다. 이번 세션에서 사용자가 직접 추가 로그인·설치·승인을 할 일은 없다. PM 인수·게시·병합·부모 완료는 별도 절차다.

## 실행자 확인·현재 결과 — 2026-10-05 20:27 KST

사용자 실제 요청: “깃 128오류가 난데 이거 해겨래”, “추가사항: 깃 오류 해결하고 정이량에게 온 메일 작업 실행해”. 아래 모델 기록의 직접 지시 인용은 실행자가 모델에게 전달한 범위 제한 prompt이며 사용자의 실제 발화를 그대로 인용한 것이 아니다. 실행자는 연결된 자기 Gmail에서 PM 배정 알림 메일을 읽었고 Issue13의 [CSV 배정](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/13#issuecomment-5991958336)·[인용 배정](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/13#issuecomment-5992248482)에 연결했다.

Git128은 실제 동일 옵션의 worktree 생성에서 `Filename too long`으로 재현됐다. 원 상태에서 fetch/기본 조회는 PASS였으며 긴 경로가 checkout을 막았다. Worker 전용 Git의 core.longpaths=true와 짧은 state/execution/auth 실제 폴더로 복구했다. 같은 Limited 예약 작업에서 fetch·checkout·최장219자 소스 파일의 Python 읽기 PASS, 새 Pythonw preflight의 계정/컨테이너 로그인/중앙 연결 PASS를 확인했다. Windows 전체 긴 경로 설정 변경은 도구 정책이 차단해 수행하지 않았으며 현재 값0을 유지한다. 원 token/로그/실패 checkpoint와 전용 AI 로그인은 같은 볼륨에서 원본 이동하여 보존했고 인증 복사/재로그인/다른 계정 사용은 없다.

생성은 실제 고정 Docker 모델 컨테이너에서 1회 수행했다. CLI turn.completed와 schema 결과 원본을 보존했다. 도구 반환 단계의 오래된 긴 AI cache 경로 정리 오류로 daemon exit code는 private 결과에 보존되지 않았으므로 그 코드를0이라고 추정하지 않았다. 새 짧은 전용 profile로 원 로그인과 캐시를 옮기고 모델을 재호출하지 않고 같은 생성물을 검증했다. 원 로그 SHA256 `bc0cdb6c02cac3bd9fb4a0201a6586b2891c656001cc317bc99c8f1e6487142b`. 실제 CLI usage: input645006/cache-input566784/output17517/reasoning-output1436(청구액이 아니며 cache/reasoning을 별도 더해 전체 사용량으로 만들지 않음).

검사는 원 AI 프로필도 mount하지 않고 network=none인 별도 validator의 소스 복사본에서 실행했다. 결과: test_review_import.py: 9개 PASS, test_source_ranges.py: 10개 PASS, test_document_registration.py: 10개 PASS, test_document_plan_history.py: 4개 PASS — 총 33개. 검사 후 모델 소스와 validator 기존 파일의 bytes/hash를 대조했고 변경이 없었다. 비밀/링크/허용 경로 검사를 통과한 일반 파일6개만 게시 clone으로 반입했다. 코드 자체는 검증한 bytes를 유지한다. 토큰·private 로그·메일 주소를 공유하지 않는다.

이 결과는 사용자 승인 수동 복구 PR이며 이전 auto28a/auto7f/auto1ff blocked 기록·원 시도/예산·controller lease를 변경하지 않는다. 부모 Done, 자동 무인 개발 완주, PDF/OCR 정확도, 실제 고객 자료 확보·새 API/UI 통합을 주장하지 않는다. 두 API를 실제 등록/검색 경로에 연결하는 별도 단위와 PM 독립 검수·병합·통합 인수는 후속이다. 자기 Worker는 실제 숨김 Limited 프로세스로 다시 가동하고 새 승인 패킷을 기다린다.
