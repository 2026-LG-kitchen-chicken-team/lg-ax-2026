# 설치된 상품기획 하네스 연결

## 버전 고정 해제 (2026-10-16)

읽기 서버와 화면은 더 이상 특정 릴리즈를 고정하지 않습니다. 선택한 폴더의 `product-install.json` 형식(`codex-product-install-v1` 또는 `portable-product-install-v1` + `engine`)으로 실행기를 정하고, 그 기록이 선언한 제품 파일 SHA가 맞는지 확인합니다. 관찰 장치(`web/prototypes/agent-office/*`)는 `office.py install`이 새로 복사할 수 있으므로 SHA 비교에서 뺍니다. 릴리즈 이름은 심사 ZIP 준비 기록 `runtime-data/judge-setup.json`의 `release`를 따르고, 없으면 `null`(화면: 설치 버전 미확인)입니다. 아래 v0.15.0 값은 처음 연결했을 때의 기록입니다.

서버 없이 보는 파일 보기(`runtime-data/agent-office/factory.html`)는 [README](../README.md)의 ‘하네스 실행 대시보드’를 참고하세요.

## 연결 대상

이 연결은 정이량이 배포한 `2026-LG-kitchen-chicken-team/lg-ax-harness` 제품의 설치 기록을 확인합니다. 아래 **product-v0.15.0**은 최초 연결 시 검증한 보존 사례입니다. 현재 지원 형식은 위 ‘버전 고정 해제’를 따릅니다. 기존 `lg-ax-2026` 팀 개발 Controller·작업 대기열 DB와 다른 제품입니다. `backend/harness_reader.py`의 개발 대기열 연결을 이 제품의 업무 상태로 사용하지 않습니다.

공식 심사용 ZIP은 `lg-ax-judge-product-v0.15.0.zip`, 원본 SHA-256은 다음과 같습니다.

```text
ccf2386fb70f6f73692eb3b9f1cffd2ac7bba9e50c9276b9729513b30b16deb8
```

제품 소스 commit은 `3cf62939689aa21564b162ab8d2f855c30d32a66`입니다. 브리지는 선택한 폴더의 `product-install.json` SHA와 그 manifest가 선언한 제품 파일 SHA를 읽어 선택된 설치 사본을 확인합니다. 설치·실행 준비와 실제 AI 업무 완료는 별개입니다. 배포본 확인만으로 로그인·모델 이용권·권한·native 실행 성공을 주장하지 않습니다.

## 조회 서버 인터페이스

Python 표준 라이브러리만 사용합니다. 대시보드 소스 폴더에서 실행하며 환경 변수로 **설치된 codex 또는 claude 제품 폴더 하나**만 명시합니다.

```powershell
$env:AX_RELEASE_WORKSPACE = '<운영자가 선택한 제품 codex 또는 claude 폴더의 절대 경로>'
# Controller/LLM 토큰과 다른 별도 조회 전용 토큰을 현재 프로세스 환경에 준비합니다.
# 실제 토큰을 채팅·소스·Git·URL·로그·브라우저 저장소에 넣지 않습니다.
$axReleaseSecret = Read-Host '조회 전용 토큰' -AsSecureString
$env:AX_HARNESS_VIEW_TOKEN = [System.Net.NetworkCredential]::new('', $axReleaseSecret).Password

# 같은 공장 화면을 로컬에서 제공할 때만, 빌드된 dist 폴더를 명시합니다.
$env:AX_RELEASE_UI_DIST = '<이 대시보드의 dist 폴더 절대 경로>'

python -m backend.release_server
```

기본 주소는 `http://127.0.0.1:8033`입니다. 필요하면 `--port`로 명시합니다. `AX_RELEASE_UI_DIST`가 있으면 같은 공장 UI를 로컬에서 열고 메모리의 조회 토큰으로 자동 연결할 수 있습니다. 토큰은 HTTP 응답 메모리의 `application/json` bootstrap에만 삽입합니다. HTML 파일·정적 사이트·소스 ZIP에 실제 토큰을 저장하지 않습니다. 프런트엔드는 bootstrap을 읽은 즉시 DOM에서 지우고 조회 store의 메모리에만 보관해야 합니다.

로컬 화면은 `/` 또는 `/?view=harness`, `/?view=team`의 알려진 보기만 지원합니다. `AX_RELEASE_UI_DIST`가 없으면 화면을 제공하지 않고 조회 API만 제공합니다. 공개 사이트에서 수동 연결할 경우 그 사이트의 정확한 Origin만 `AX_HARNESS_ALLOWED_ORIGINS`에 추가해야 합니다. 이것은 제품 업무 자료를 모두에게 공개하는 설정이 아닙니다.

```powershell
$env:AX_HARNESS_ALLOWED_ORIGINS = 'https://<정확한 대시보드 호스트>.chatgpt.site'
```

브라우저가 공개 HTTPS 페이지의 로컬 네트워크 접근을 막으면 PM PC의 로컬 화면을 사용합니다. 이 구현은 HTTPS 원격 서버·포트 포워딩·전체 네트워크 바인딩을 제공하지 않습니다. 다른 PC의 localhost는 그 PC 자신이며 PM PC로 연결되는 주소가 아닙니다.

## 허용 동작과 보안 경계

- `GET /api/harness/snapshot`: Bearer 조회 토큰 필수. Origin 없는 네이티브 요청도 인증합니다.
- `GET /health`: 최소 서비스 상태만 반환합니다. 제품 자료·경로·토큰은 포함하지 않습니다.
- `OPTIONS`: 허용 출처의 GET·Authorization 사전 요청만 허용합니다.
- POST 등 변경 요청은 405입니다. 제품 Tool·모델·작업 중단·설치·Observer 실행 명령을 받지 않습니다.
- 경로·엔진·DB·멤버·토큰을 HTTP 쿼리로 받지 않습니다. API의 추가 쿼리는 거부합니다.
- Host는 현재 포트의 `127.0.0.1` 또는 `localhost`만 허용합니다. DNS 재결합으로 다른 Host를 사용하면 거부합니다.
- 로컬 HTML·정적 자산은 같은 출처만 허용하며, 공개 사이트 Origin이 API 허용 목록에 있어도 HTML bootstrap에는 접근할 수 없습니다. 정적 응답에 CORS를 붙이지 않습니다.
- 정적 응답에는 `no-store`, `nosniff`, CORP `same-origin`, CSP `frame-ancestors 'none'`·`base-uri 'none'` 및 프레임 금지를 적용합니다. 정적 파일은 명시된 dist의 index·assets·favicon만 제공하고 상위 경로·링크·reparse point·source map을 거부합니다.

이 서버는 제품 폴더를 검색하지 않습니다. 인증·SQLite 원본·API 키·개인 문서를 읽지 않습니다. 제품 manifest의 고정 파일과 아래 Observer 산출물을 읽습니다. Reader는 파일·DB·훅·전역 설정에 쓰지 않습니다.

Codex 로컬 런처는 `AX_RELEASE_NATIVE_SESSIONS`에 세션 디렉터리를 명시합니다. 이 선택 기능은 Observer의 `codex-follow.json`이 이미 선택한 **현재 메인 세션 파일 한 개**만 읽고, 첫 메타데이터의 세션·작업 폴더와 현재 native turn을 재검증합니다. 다른 세션 내용이나 인증 파일을 탐색하지 않습니다. 공개 진행 메시지는 고정 작업 분류로만 변환하며, 명령 결과에서는 검사 bool·Skill frontmatter·처리 횟수만 투영합니다. 질문·대화·명령·출력 원문과 reasoning은 HTTP 응답·저장·공개 배포에 포함하지 않습니다.

`activity`는 `codex_native_activity` 계약입니다. 준비 점검은 메인 기획자에서 표시하고, 지침 조회는 Skill 명령 실행과 구분합니다. CLI 공개 메시지로만 파악한 단계에는 ‘CLI 진행 보고’를 표시합니다. 이 보고를 실제 Skill 호출이나 서브에이전트 위임으로 바꾸지 않습니다. 실제 Skill 호출은 원 Observer의 command 기록을 계속 사용하며, 개별 명령의 시작 시각을 완료 후 받는 경우를 실시간 실행으로 재생하지 않습니다. 과거의 열린 native 요청은 120초 이후 활성 연출을 해제합니다.

## 실제 읽는 자료

선택한 제품 폴더의 다음 경로만 업무 관측 입력입니다.

```text
runtime-data/agent-office/events.jsonl
runtime-data/agent-office/snapshot.json
runtime-data/agent-office/live.js
```

`live.js`는 정해진 `window.LGAX_OFFICE_LIVE = <JSON>;` 할당문만 엄격하게 파싱합니다. JavaScript로 실행하지 않으며 앞뒤의 추가 코드를 거부합니다. JSON 중복 키·잘못된 형식·과도한 크기를 거부합니다. JSONL은 줄바꿈으로 끝난 완전한 행만 읽고 작성 중인 마지막 행은 보류합니다.

동일 ID 사건은 중복 표시하지 않습니다. 시각은 UTC ISO를 실제 시각으로 비교하므로 같은 초의 소수점 유무로 순서가 뒤집히지 않습니다. 사건 ID·세션 ID·native prompt ID·호출 ID와 허용된 역할·Skill·작업·시간·종료 상태를 유지하며 원문 질문·명령·출력·토큰·파일 경로는 응답에서 제외합니다.

제품에는 메인 기획자와 선택 연구 역할 세 개가 있습니다.

```text
product_official_researcher
product_review_researcher
product_evidence_reviewer
```

Skill은 다음 여섯 개입니다. 기존 데모의 다섯 단계와 임의로 같은 것으로 간주하지 않습니다.

```text
evidence-retrieval
web-evidence-collection
needs-structuring
feature-comparison
concept-writing
review-and-revise
```

`skill_load / instruction_loaded`는 지침 읽기, `skill_op / command_based_mapping`은 명령 경로를 통한 작업 분류입니다. 모두 의미 판단·실행 성공을 독립 인증하지 않습니다. 연구 역할은 실제 native 사건이 있을 때만 실행으로 표시합니다.

## 응답 계약과 현재 업무 결속

최상위는 `schema_version`, `source`, `events`, `db`, `notices`입니다.

`source`는 다음 필드를 포함합니다.

```json
{
  "kind": "lgax_release_observer",
  "release": "product-v0.15.0",
  "engine": "codex",
  "observed_at": "이번 조회의 UTC 시각",
  "source_updated_at": null,
  "observer_status": "waiting_for_session",
  "asset_sha256": "공식 ZIP SHA-256",
  "product_install_sha256": "확인한 제품 설치 manifest SHA-256",
  "source_commit": "공식 제품 소스 commit"
}
```

배포본은 확인됐지만 사건이 없으면 연결은 성공하고 `waiting_for_session`, `events: []`를 반환합니다. 화면을 움직이기 위해 가짜 사건·진행률을 만들지 않습니다. 설치 기록이 없거나 다른 배포본이면 성공한 연결로 표시하지 않고 고정 오류를 반환합니다.

`source_updated_at`은 원 관측 파일에 기록된 갱신·사건·DB 요약 읽기 시각의 최댓값입니다. 이번 조회 시각으로 덮어쓰지 않습니다. `observing`은 현재 native 요청에 최근 120초 이내 열린 사건이 있다는 뜻이며 Observer 프로세스 생존 확인이나 모델 성공이 아닙니다. 종료·취소됐거나 오래된 사건은 `recorded`입니다. 프런트엔드도 연결이 끊기거나 원 사건이 오래되면 활성 연출을 해제해야 합니다.

현재 native 문맥은 최신 main의 request/session-start로 고정합니다. 후속 prompt는 현재 요청에 기록된 launched_agent_id 또는 같은 prompt의 SubagentStart ID와 from_agent_id가 맞을 때만 합칩니다. 출처가 확인되지 않은 알림이나 이전 요청의 늦은 하위 역할 결과는 제외합니다. 같은 세션의 앞선 요청 A가 늦게 종료·취소돼도 현재 요청 B로 돌아가거나 B의 열린 작업을 닫지 않습니다. native prompt가 null이어도 다른 prompt 전체를 허용하는 와일드카드로 쓰지 않습니다.

DB 요약을 native 업무와 합치려면 현재 선택 native 세션·prompt의 사건에 기록된 `detail.business_binding`의 **session_id·turn_id·request_key 세 값이 모두** DB `binding`과 일치해야 합니다. 결속되면 `db.binding_status: matched`와 허용된 상태·개수·검사 flag만 반환합니다. 불일치하면 `unmatched`와 최소 메타데이터만 반환하고 다른 세션의 후보 수·결과·상태를 현재 업무에 섞지 않습니다. 단순 최신 파일·시간 겹침·전역 최신 DB라는 이유로 합치지 않습니다.

export 파일명·개인 경로·본문은 전달하지 않습니다. 실제 결과 웹 전달은 제품의 `web_binding`과 불변 파일 SHA를 대조하는 별도 계약이며 이 상태 Reader의 관측 성공만으로 인증하지 않습니다.

## 제품 실행과 Reader의 차이

제품 ZIP의 `judge.py setup`은 별도 선택 제품 사본의 `.venv`, 로컬 SQLite 준비, 프로젝트 훅을 설치합니다. 사용자 전역 계정·모델·권한 승인을 자동 처리하지 않으며 uv/Python 캐시는 사용자 캐시에 생길 수 있습니다. 원본 ZIP을 보존하고 새 사본에서 준비하는 작업은 운영자가 별도로 수행합니다.

제품 `judge.py observe --engine codex`는 해당 제품에서 시작한 native 세션을 따라 관측 산출물을 만듭니다. 모델 호출은 하지 않지만 관측 파일에는 씁니다. Claude의 observe는 이미 설치된 훅의 사건 파일을 watch로 읽습니다. 새 대시보드 Reader는 이 두 Observer를 시작하지 않으며 이미 만들어진 산출물만 읽습니다. 로그인·폴더 신뢰·훅 신뢰·모델 이용권은 제품 안내의 정상 절차가 필요합니다.

## 검증

```powershell
python -m unittest backend.tests.test_release_reader -v
```

합성 관측 자료와 임시 loopback HTTP로 누락·대기·명령 주입·작성 중인 행·범위 이탈·민감 필드 제외·문맥 A/B의 지연 종료·소수점 시각·파일 바이트 불변·GET 인증·Host/Origin·정적 bootstrap의 메모리 전용 처리를 검사합니다. 별도 공식 배포본이 work에 있을 때만 원본 설치 SHA와 선언 파일을 읽어 확인합니다. 실제 사용자 세션·원본 DB·모델 호출은 테스트하지 않습니다. Windows 계정이 symlink 생성을 허용하지 않으면 그 생성 검사는 skip하며, manifest 상위 경로와 URL 인코딩 경로 이탈 검사는 항상 수행합니다.
