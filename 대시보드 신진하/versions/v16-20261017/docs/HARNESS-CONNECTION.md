# 팀 하네스 읽기 연결

## 현재 상태

이 대시보드에는 팀 Controller의 상태를 바꾸지 않는 조회 브리지를 준비했습니다. **현재 실제 팀 DB와 연결하지 않았으며 연결 대기 상태입니다.** 합성 SQLite 자료로 조회·인증·범위·부작용 없는 읽기를 검사했습니다. 실제 DB 경로·조회 토큰·운영자 PC 연결은 운영자가 직접 설정해야 합니다.

`harness/phase2/tasks`의 개발 기록, 자동화 Worker 상태, 상품기획 다섯 Skill 실행은 서로 다른 근거입니다. 개발 작업은 전체 현황에 표시하고 제품 Skill에 임의 배치하지 않습니다. Worker의 `model` 단계는 고정 코딩 Worker가 보낸 자기보고이며 제품기획 LLM 호출 성공을 의미하지 않습니다.

## PM PC에서 실행

팀 Controller DB가 있는 PC에서 대시보드 소스 폴더를 열고 Python 3.10 이상으로 실행합니다. 팀 저장소·서비스·Controller 코드는 수정하지 않습니다. 운영자는 기존 설정에서 이미 확인한 DB 파일 하나를 직접 지정해야 합니다. 이 도구는 경로·토큰을 찾거나 요청하지 않으며 폴더를 탐색하지 않습니다.

PowerShell에서 아래 값을 실제 운영자가 확인한 값으로 바꿉니다. 토큰은 Controller 운영 토큰이 아닌 **별도로 만든 조회 전용 임의 토큰**입니다. 토큰을 채팅·Git·스크린샷·URL·브라우저 저장소에 남기지 마세요.

```powershell
$env:AX_HARNESS_DB = '<운영자가 확인한 Controller SQLite 파일의 절대 경로>'
$env:AX_HARNESS_PROFILE = 'lg-ax-2026'
$env:AX_HARNESS_MEMBERS = 'jeongiryang,unknownamed,ginaginaring,choigilung'

# 32~256자의 임의 조회 토큰을 화면에 표시하지 않고 입력합니다.
$axHarnessSecret = Read-Host '조회 전용 토큰' -AsSecureString
$axHarnessPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($axHarnessSecret)
try {
  $env:AX_HARNESS_VIEW_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($axHarnessPointer)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($axHarnessPointer)
}

# 로컬 대시보드는 기본 허용됩니다. 공개 사이트를 쓸 경우 정확한 Origin만 추가합니다.
# 마지막 / 없이 실제 공개 사이트 Origin을 입력합니다.
$env:AX_HARNESS_ALLOWED_ORIGINS = 'https://kitchen-ax-factory-20261015.tlswlsgk7174.chatgpt.site'

python -m backend.harness_server
```

기본 표시 주소는 `http://127.0.0.1:8033`입니다. 필요하면 `--port`로 다른 로컬 포트를 명시할 수 있습니다. 원격 HTTPS 주소로 연결하거나 외부 네트워크에 이 서버를 공개하지 않습니다. `0.0.0.0` 바인딩·포트 포워딩·인증 우회·HTTPS 원격 서버 배포는 이번 구현 범위가 아닙니다. 다른 PC에서는 이 주소가 그 PC 자신을 뜻하므로 PM PC의 데이터가 자동 공유되지 않습니다. 공개 페이지에서 loopback 접근은 브라우저의 로컬 네트워크 권한·보안 정책에 따라 차단될 수 있습니다. 이 경우 PM PC의 로컬 대시보드로 확인합니다.

대시보드 연결 화면에서 같은 주소와 조회 토큰을 입력합니다. 토큰은 열린 화면의 메모리에만 유지하며 새로고침·연결 해제 시 다시 입력합니다. JSON 내보내기·브라우저 저장·팀 스냅샷에는 토큰을 포함하지 않습니다. 공개 사이트의 JavaScript 파일에 실제 토큰을 넣으면 안 됩니다.

## 허용 API와 권한

- `GET /health`: `{service,ok}`만 반환합니다. 실제 DB 연결·Worker 상태를 공개하지 않습니다.
- `GET /api/harness/snapshot`: `Authorization: Bearer <조회 토큰>`이 필수입니다. Origin 없는 CLI·네이티브 요청도 인증이 필요합니다.
- `OPTIONS`: 허용 출처의 GET·Authorization 사전 요청만 처리합니다.
- POST·PUT·PATCH·DELETE 등은 405입니다. 모드 ON/OFF·배정·중단·lease 갱신·Worker 실행·PM 승인 API가 없습니다.
- DB 경로·멤버 범위·프로젝트는 HTTP 인자에서 받지 않습니다. 추가 쿼리도 거부합니다.

기본 브라우저 출처는 HTTP localhost·127.0.0.1·IPv6 loopback입니다. 추가 출처는 `AX_HARNESS_ALLOWED_ORIGINS`에 정확한 Origin을 쉼표로 구분해 명시합니다. 와일드카드와 쿠키 인증은 사용하지 않습니다. Origin은 보조 경계이며 조회 토큰을 대신하지 않습니다.

허용 팀 계정은 네 개로 고정되어 있습니다. `AX_HARNESS_MEMBERS`는 그 안의 일부로만 줄일 수 있습니다. Controller DB에는 repo 컬럼이 없으므로 고정 `lg-ax-2026` 프로필과 운영자가 선택한 정확한 DB를 전제로 합니다. 프로필 문자열만으로 잘못 선택한 DB의 출처가 독립 검증되었다고 주장하지 않습니다.

## 읽기 방식과 정보 범위

`sqlite3` URI의 `mode=ro`, `PRAGMA query_only=ON`, 하나의 읽기 transaction으로 필요한 행만 SELECT하고 연결을 닫습니다. 라이브 WAL에 커밋된 변경을 읽기 위해 `immutable=1`은 쓰지 않습니다. DB 파일이 없으면 생성하지 않습니다. Controller의 `Store`, `status`, `_expire`, 운영 API는 사용하지 않습니다. 기존 Controller의 GET `/v1/status`에는 만료 처리 부작용이 있으므로 이 브리지는 그 경로를 호출하지 않습니다.

허용 테이블은 `settings(mode/formal_snapshot)`, `members`, `jobs`, `worker_presence`, `events`입니다. `identities`, 인증 설정, 개인 경로, 토큰 파일을 읽지 않습니다. `formal_snapshot.tasks`에 존재하고 서버 멤버 범위에 들어오는 작업만 표시합니다. 이름은 승인 작업의 `title`만 사용하며 packet의 자유 제목으로 대체하지 않습니다. 미제공·민감한 제목은 고정 문구로 표시합니다.

raw packet·프롬프트·결과·오류 이유·경로·검사 명령·lease 토큰·인증 digest·Worker instance·원 이벤트 details·승인 문서 원문은 응답에 넣지 않습니다. 최근 이벤트와 작업 이유는 허용 enum에 대응하는 고정 문장으로 만듭니다. 합법적인 작업 이름에도 개인정보가 들어갈 수 있으므로 정식 task 제목에는 처음부터 민감한 내용을 넣지 않아야 합니다. 화면을 공개 공유하기 전에는 별도 익명화·공개 범위 검토가 필요합니다.

## 응답 해석

최상위 필드는 `schema_version`, `source`, `global_mode`, `members`, `jobs`, `workers`, `events`, `formal_tasks`, `notices`입니다. 시간은 UTC ISO 문자열, Worker `age_seconds`는 숫자입니다.

- `source.observed_at`: 이번 읽기 시각입니다.
- `source.source_updated_at`: 노출 범위 안 작업 생성·Worker 수신·이벤트의 실제 기록 시각 중 최댓값입니다. 기록이 없으면 null입니다. 폴링할 때마다 현재 시각으로 바꾸지 않습니다. SQLite 수정시각이나 실시간 프로세스 검증 시각을 뜻하지 않습니다.
- `source.approved_commit`: DB의 PM 승인 스냅샷에 기록된 SHA입니다. 최신 main과 일치 여부를 이 도구가 온라인 확인한 것은 아닙니다.
- `global_mode`: `on`, `off`, `stop`입니다. 선언 파일의 초기값을 현재값으로 쓰지 않습니다.
- `job.status`: 원본 대기열 상태를 그대로 유지합니다. `lease_state`만 `live`, `expired`, `inactive`, `unknown`으로 계산합니다. 만료된 running을 orphaned로 갱신하지 않습니다.
- `is_running_confirmed`: mode ON, 멤버 ON, 원본 status running, lease fence 존재·유효 기한, 같은 owner/job의 최근 180초 이내 Worker active phase가 모두 일치할 때만 true입니다. fence는 존재 여부의 SQL boolean만 조회하며 hash 값을 가져오지 않습니다. Worker metadata에 lease generation은 없으므로 동일 작업의 재시도 전후를 이 값만으로 독립 증명할 수 없습니다. 이것도 최근 자기보고와 lease의 일치라는 보조 근거이며 모델 성공·현재 CPU 실행·정식 완료를 보증하지 않습니다.
- Worker는 `online`, `stale`, `never_seen`을 구분합니다. 180초 이상 지난 보고는 stale입니다. 현재 시각에서 보고가 더 오래되거나 lease가 만료되면 화면도 활성 표시를 해제해야 합니다.
- 모든 개발 작업은 `view: overview`, `stage: null`입니다. 명시된 제품 실행 근거 없이 다섯 Skill에 연결하지 않습니다.

DB 설정 없음·읽기 불가·스키마 불일치는 503과 고정 오류 코드로 표시합니다. 경로·비밀·원문 예외를 반환하지 않으며 실패를 데모 진행률이나 성공으로 대체하지 않습니다. 브리지는 기존 자동화 모드를 ON으로 만들지 않고 작업을 착수시키지 않습니다.

## 합성 검증

프로젝트 최상위 폴더에서:

```powershell
python -m unittest backend.tests.test_harness -v
```

검사는 합성 DB와 임시 loopback 서버만 사용합니다. 실제 팀 DB·Controller·모델·외부 API를 호출하지 않습니다. DB 바이트·행 불변, WAL 가시성, 만료·stale·범위 제한, 민감 필드 제외, GET 전용·토큰·Origin·스키마 오류를 확인합니다.

## 수동 CLI 작업의 범위

이 연결은 Controller에 등록된 작업과 Worker 자기보고, PM 승인 정식 과제 스냅샷을 읽습니다. 하네스 밖에서 사람이 직접 실행하는 Codex·Claude 터미널의 명령이나 작업 내용은 자동 수집하지 않습니다. 그런 수동 CLI도 표시하려면 해당 실행기에서 명시적인 상태 보고를 보내는 별도 연결이 필요합니다. 이번 구현은 터미널 감시·프롬프트 수집·팀 자동화 ON을 추가하지 않았습니다.
