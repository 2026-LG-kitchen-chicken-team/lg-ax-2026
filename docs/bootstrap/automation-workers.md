# 각 PC의 자동 개발 초기 설정 — Codex / Claude Code

2026-10-05 사용자 승인으로 두 실행기를 제공한다. **각자 선호하는 실행기 하나를 선택**한다. 배정·작업 잠금·상세 기록·검사·PR·Project 보고·PM 검수는 동일하다. Claude Code 사용자는 Codex 로그인이나 구독을 추가할 필요가 없다.

검증 전 팀/개인 모두 OFF다. 초기 설정을 끝냈다고 켜지지 않는다. 최신 Worker는 [Docker 실행·검사 경계](automation-isolation.md)를 사용한다. 모델·저장소 검사에 게시 인증을 제공하지 않고 실제 canary·본인 로그인·첫 PR/보고를 확인해야 한다. 정이량의 [자동 PM](../pm/autonomous-pm.md)은 별도 정책과 PM 개인 ON이 필요하다. 중앙 HTTPS는 아직 정이량 PC를 경유한다. 네 PC의 실제 준비는 각자 근거로 확인한다.

10/5 정이량 PC의 제한 pilot에서는 실제 Docker Codex 수정(168.109초) → 고정 validator(2.844초, 1개 테스트로 다른 프로젝트 부모 거부·같은 프로젝트 부모 허용 검증) → [PR82](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/82)의 CI 4개 성공 → [Project 보고 ACCEPTED](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/19#issuecomment-5985353509)까지 확인했다. 앞선 cache 권한 실패와 세션 근거 경로 미승인으로 게시가 차단된 두 시도는 보존했다. 독립 PM 검수·실제 병합·병합 후 통합 확인은 [pipeline 근거](../../evals/team-automation/20261005/pipeline-proof.json)의 최종 결과를 따른다. 이 한 건의 pilot과 전원 OFF 상태를 다른 세 PC의 준비 완료·팀 전체 가동·참가작 완성으로 확대하지 않는다.

## 팀원 AI에게 먼저 전달할 지시

> 이 저장소의 AGENTS.md와 동일 CLAUDE.md, docs/bootstrap/automation-workers.md, docs/pm/automation.md를 읽고 내 담당 계정을 확인해 LG 자동화 초기 설정을 진행해. 내 실행기는 Claude Code(또는 Codex)야. 실행 환경·개인 GitHub 인증·전용 AI 로그인·중앙 가입·고정 Worker/보고 bundle·preflight 순서로 준비하고 결과를 내 상세 작업기록/근거와 자기 Project 보고에 남겨. 비밀번호나 로그인 토큰은 복사/출력하지 마. 직접 로그인만 나에게 요청하고 AI가 할 수 있는 설치/파일 설정은 진행해. 격리 미검증을 true로 바꾸지 말고, 팀 ON·PM 병합·Done을 대신 수행하지 마. 현재 진행 수준·남은 일·내가 직접 해야 할 일을 마지막에 알려줘.

Claude 선택 시 초기 설정을 돕는 대화와 자동 작업을 수행하는 **로컬 Claude Code CLI**는 구분한다. 웹/앱 로그인이나 GitHub App 설치만으로 이 PC의 CLI 인증이 끝나지는 않는다.

## 초기 설정 순서

| 단계 | 팀원/자기 AI가 할 일 | 완료 증거 |
|---|---|---|
| 1. 실행 환경 | Linux Docker engine·검토한 최소 context/고정 image ID, 별도 clone·상태·execution·본인 인증 폴더, Python 3.11/uv·GitHub CLI 확인 | 실제 경로·image/user/mount/network. OS 계정/VM 이름은 경계 증거가 아님 |
| 2. 본인 인증 | `gh auth login` 후 실제 `gh api user --jq .login`이 자기 담당 계정인지 확인 | 본인 계정·저장소 Write. 토큰 원문 기록 금지 |
| 3. 중앙 가입 | `automation.py setup --member {성명} --controller-url {중앙주소}`로 개인 Worker 자격증명 발급 | private 설정/토큰 파일 위치·개인 OFF 상태. PM 운영자 토큰 공유 금지 |
| 4. 실행기 로그인 | 아래 선택한 AI의 개인 전용 폴더에서 직접 로그인 | host metadata와 같은 profile을 mount한 Linux CLI 인증 확인. 다른 팀원 인증 복제 금지 |
| 5. 고정 실행 파일 | PM 검토 main에서 저장소 밖의 새 폴더에 Worker와 report bundle 생성 | manifest·외부 entry 경로/해시. 편집 중인 브랜치에서 운영 코드 실행 금지 |
| 6. 개인 설정 | 해당 example을 private worker.json으로 복사, 실제 경로·계정·토큰·bundle·executor_image/execution_root 연결 | Docker 미준비 때 native fallback 없음·state_dir/lock 보존. legacy true가 증거가 아님 |
| 7. 사전 점검 | 고정 entry의 `--preflight`로 계정/로그인/버전/중앙 연결만 확인 | `preflight=passed`, `model_executed=false`. 유료 모델/작업 착수 아님 |
| 8. 경계/대기/pilot | 실제 canary 분리 확인 → 서비스 등록·OFF 대기 확인 → PM의 작은 승인 패킷으로 제한된 pilot | model/validator 게시 canary 거부, 실제 종료/검사/자기 PR/보고 수신 확인. host canary 읽기와 GitHub 게시를 구분. 설치만으로 Ready/개인 ON을 부여하지 않음 |

등록 계정: 정이량 `jeongiryang`, 황대겸 `unknownamed`, 신진하 `ginaginaring`, 최길웅 `choigilung`.

## Claude Code 선택

[공식 설치](https://code.claude.com/docs/en/setup)를 따라 native Claude Code를 설치한다. 이번에 실제 옵션을 점검한 버전은 **2.1.289**이며 `claude_version`과 정확히 맞춰야 한다. 설치된 버전이 다르면 PM에게 버전·옵션을 제출하고 재검증한다. Windows의 `.cmd` 래퍼는 쓰지 않고 `claude_executable`에 실제 `claude.exe` 경로를 넣는다. Linux는 native 실행 파일을 쓴다.

호스트 metadata 점검을 위해 직접 로그인할 PowerShell에서 **전용 개인 폴더**를 지정할 수 있다. 아래 계정/경로는 최길웅 예시이며 자기 이름으로 바꾼다. 지정한 CLI의 `auth login`을 실행하고 **Claude 구독 계정**으로 직접 로그인한다. 이 절차만으로 Linux 컨테이너 인증이 완료되지 않는다. 같은 전용 profile의 컨테이너 CLI 인증을 반드시 `automation_isolation.py verify`로 확인하고, OS 키체인 차이로 실패하면 선택한 실행 환경에서 본인 직접 로그인을 진행한다.

```powershell
$env:CLAUDE_CONFIG_DIR = 'C:/LGAX-auth/choigilung-claude'
& 'C:/LGAX-tools/claude.exe' auth login
```

`services/automation/worker.claude.example.json`을 사용한다. `engine=claude`, `claude_home`, `claude_executable`, `claude_version`, `claude_model=sonnet|opus|haiku`, `claude_max_turns`를 검토한다. 자동 운영 중 버전을 변경하지 않는다. 동일 state_dir의 Worker를 먼저 중단하고 설정을 바꾼 후 다시 점검해야 한다. Codex와 Claude를 같은 담당의 동일 큐에서 중복 서비스로 등록하지 않는다.

Worker는 자기 claude.ai 로그인·실제 configDirectory·공식 firstParty provider를 검사한다. Console/API key·apiKeyHelper·외부 provider·공유 OAuth token은 거부하고 inherited API/Claude 환경변수도 제거한다. `--restricted`와 `--safe-mode`로 프로젝트/개인 자동 실행 설정·플러그인·MCP를 끄고, 구현에는 Read/Glob/Grep/Edit/Write, 검토에는 Read/Glob/Grep만 제공한다. shell·네트워크·하위 Agent는 제공하지 않는다. Claude가 파일을 수정하면 고정 Worker가 승인된 검사 명령을 실행하고 결과·허용 경로·기록을 확인해 PR/보고를 게시한다. schema 실패·사용량/인증 실패·권한 거부·턴/시간 한계는 실패로 보존한다.

safe-mode에서는 CLAUDE.md가 자동 로딩되지 않으므로 작업 prompt가 동일 AGENTS.md/CLAUDE.md를 먼저 읽도록 지시한다. `--bare`는 구독 인증을 읽지 않아 사용하지 않는다. CLI 도구 제한을 별도 OS 사용자/publisher 인증 격리의 완료 증거로 표현하지 않는다.

[공식 SDK 정정](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan)에 따르면 현재 `claude -p`도 구독 사용량을 사용한다. 과거 별도 월간 크레딧 변경은 보류됐다. 자기 Claude 대화/Code와 사용량을 공유하므로 무한 실행을 가정하지 않는다. 계정에서 추가 사용량이 활성화돼 있으면 그 설정을 확인하며, Worker는 과금 설정을 바꾸지 않는다. 비용 메타데이터는 추정값이고 실제 결제액이 아니다. 확인일 2026-10-05; 정책 변경 시 공식 안내를 다시 확인한다.

## Codex 선택

`services/automation/worker.example.json`을 사용한다. `engine` 생략 시 기존 Codex 설정과 호환된다. Docker image와 실제 개인 경로를 준비한 뒤 `scripts/automation_isolation.py login --config {본인worker.json}`으로 고정 Linux CLI의 device 인증을 안내받아 ChatGPT 계정으로 직접 로그인한다. 전용 CODEX_HOME만 사용하며 다른 프로필을 복사하지 않는다. API key/provider로 자동 전환하지 않는다. Windows의 native codex.exe metadata 경로와 실제 컨테이너 codex를 구분한다. 나머지 중앙 가입·상태·기록·PR 절차는 같다.

## 공통 bundle·점검·서비스

`--preflight`는 본인 GitHub·controller를 확인하고 image/execution_root가 구성된 경우 **선택한 컨테이너 CLI의 실제 버전·구독 로그인**을 검사한다. 미구성은 metadata_only이고 Windows Claude 로그인으로 대신하지 않는다. Docker canary·유료 생성·실제 게시는 검사하지 않아 automation_ready=false다. 일반 Worker는 정확한 image ID와 별도 execution_root를 요구하며 Docker 불가 때 native 실행을 하지 않는다. `isolation_acknowledged`는 과거 호환용 표시이고 true/false 자체가 경계 완료나 실행 허가의 증거가 아니다.

PM 검토 main의 깨끗한 clone에서 아래 두 bundle을 **저장소 밖 새 폴더**에 만든다. Worker entry는 worker/process/claude/isolation/artifacts 모듈의 해시를 확인하고 변경되면 실행을 거부한다. 보고 entry도 자기 종속 코드/정책의 해시를 확인한다. 실제 출력 경로/해시와 검토 image ID를 개인 설정에 넣는다. hash 검사는 인증 접근 격리와 별개다. 이전 bundle을 수정해 재사용하지 않는다.

```powershell
uv run --no-sync python -X utf8 scripts/build_worker_runtime.py --output C:/LGAX-tools/worker-reviewed
uv run --no-sync python -X utf8 scripts/build_worker_report_bundle.py --output C:/LGAX-tools/report-reviewed
uv run --no-sync python -X utf8 C:/LGAX-tools/worker-reviewed/worker_entry.py --config C:/LGAX-state/choigilung/worker.json --preflight
```

report bundle 출력의 `trusted_report_script`·`trusted_report_sha256`도 설정에 추가한다. 첫 pilot에서는 공유 모델 선택 필드를 생략하고 offline 검사를 사용한다. validator는 network none이므로 호스트의 loopback18873 모델 proxy에 연결할 수 없다. 모델/검사가 필요하다는 이유로 인증 폴더·Docker socket을 더 mount하거나 host network·privileged를 켜지 않는다. live-model 검사는 PM이 승인한 별도 연결과 실제 근거로 관리한다.

서비스 등록은 Windows `services/automation/install-worker.ps1`, Linux `lgax-worker.service`의 **개인 실제 경로**를 적용한다. 현재 Windows installer는 `-DedicatedExecutionEnvironment`와 `isolation_acknowledged=true`를 요구한다. 실제 image/mount/canary 증거가 확보된 뒤 설치 호환용 선언으로만 사용하며, 이 값 자체를 readiness·ON·게시 검증으로 기록하지 않는다. Linux ReadWritePaths에도 선택 엔진 인증 폴더를 넣는다. Windows 등록은 해당 사용자가 로그인된 동안만 실행되며 sleep/offline에서는 작업할 수 없다. 설치·background 시작 시 중앙 팀/개인 OFF를 다시 확인한다.

사용자 직접 필요한 부분은 자기 계정 로그인이다. 환경 준비·설정 작성·bundle·점검·자기 상태 보고는 각자의 AI가 수행한다. 설치/로그인을 할 수 없으면 원인과 다음 행동을 자기 기록/Project에 남기고 기존 수동 작업은 계속한다.

## 황대겸 PC 인계와 기존 설치 갱신

황대겸의 `unknownamed` GitHub 인증·저장소 Write·Project 조회·중앙 개인 등록이 정상이라는 보고는 보존한다. 기존 native Codex 로그인이나 폴더 분리 검사로 새 Docker 환경을 준비 완료로 처리하지 않는다. **새 실행 환경의 전용 profile에서 본인이 직접 다시 인증**하고 실제 container metadata를 확인해야 한다. 본인·팀원의 기존 AI profile이나 Windows/OS 로그인 인증을 복제하지 않는다. 황대겸의 기존 코어 중단과 개인 OFF는 인계 검증 전까지 유지한다.

자기 AI는 다음 순서로 기존 세팅을 갱신한다. 다른 팀원도 자기 계정·실제 경로로 같은 절차를 따른다.

1. 기존 Worker/실행을 중단하고 원격 main과 로컬 차이를 확인한다. PM이 운영 Issue #28에 게시한 **정확한 main commit**과 연결된 변경·검증 근거를 확인한 뒤 깨끗한 clone에서 그 코드를 준비한다. 미커밋 작업을 강제로 reset하거나 기존 state·토큰·실행 기록·등록을 삭제하지 않는다. source commit과 bundle manifest/image ID를 자기 근거에 연결한다.
2. Linux Docker engine을 확인하고 [최소 context 빌드 절차](automation-isolation.md#검토한-이미지-만들기)로 image를 만든다. 다른 PC의 image ID 문자열만 복사하지 않고 **이 PC에서 실제 존재하는** 정확한 image ID를 기록한다. 빌드 입력·CLI 버전·image가 변경되면 PM에게 새 근거를 인계한다. PC별 빌드의 image ID가 다를 수 있으므로 PM이 자료와 실제 경계 증거를 인수한 뒤 private trusted config의 `readiness_files[계정].approved_executor_image`에 해당 계정의 정확한 image를 고정한다. proof의 최상위 image와 model/validator 관측 image가 모두 이 pin과 같아야 하며, 팀원의 자기보고만으로 pin을 자동 채택하지 않는다. 계정별 pin이 없으면 기존 PM image와 같은 경우만 허용한다.
3. 개인 worker.json의 `account=unknownamed`, 기존 controller URL/개인 token/state, 별도 `codex_home`, `execution_root`, 실제 `executor_image`를 연결한다. 경로가 서로 포함되지 않는지 확인하고, 기존 동일 state/프로필을 쓰는 Worker를 중복 등록하지 않는다. 이미 유효한 중앙 등록을 이유 없이 재발급하지 않는다.
4. `automation_isolation.py login --config {본인worker.json}`으로 **고정 Linux Codex CLI의 device URL/code**를 안내하고 본인이 ChatGPT 계정으로 직접 로그인한다. helper는 automation을 켜지 않는다. timeout·인증 실패는 미완료로 남기고 API fallback·프로필 복사를 하지 않는다. Claude 선택 시 현재 login helper는 지원하지 않으므로 선택한 Linux CLI의 본인 직접 인증과 실제 metadata 확인이 필요하다.
5. `automation_isolation.py verify --config {본인worker.json} --output {새private증빙.json}`으로 이 PC의 실제 model/validator canary·컨테이너 로그인·image/mount/network 증거를 만든다. 기존 proof를 덮어쓰지 않는다. 실패하면 설치 준비 완료가 아니며 팀/개인 OFF를 유지한다.
6. 같은 검토 main에서 **새 외부 경로**에 Worker/report bundle을 만들고 worker.json의 `trusted_report_script`·`trusted_report_sha256`를 갱신한다. 기존 고정 bundle 파일을 덮어쓰지 않는다. 새 entry의 `--preflight` 성공과 실제 source commit·모듈 hash를 기록한다. canary와 preflight 성공도 실제 모델 개발/PR/보고 성공과 구분한다.
7. 설치 script/service의 본인 실제 Python·entry·config 경로를 적용하고 background 대기 상태를 확인한다. 중앙 팀/본인 OFF를 재조회해 기록한다. 설치 완료 보고에는 **설치됨·OFF 대기·검증됨·미검증**을 나눠 적는다. CLI 로그인·경계가 확인됐어도 본인이 임의로 pilot 큐나 PM 정책을 만들지 않는다.
8. 근거 위치·commit/image·preflight/canary 결과·남은 항목을 자기 세션/개인 기록과 인증된 Project 보고로 PM에게 넘긴다. PM이 한 개의 작은 작업만 승인해 제한적으로 가동하면 실제 **모델 수정→고정 검사→자기 GitHub 브랜치/PR→보고 ACCEPTED**를 확인한다. 이어서 독립 PM 검수·병합·통합 확인의 실제 증거를 인수한 뒤 후속 자동 작업 가능 여부를 정한다. 다른 팀원의 준비 상태와 전원 가동은 별도다.

인계 완료는 이 PC의 실제 증거가 있어야 한다. 정이량 PC의 성공, 사용자에게 전달한 설정 지시, `isolation_acknowledged=true`, canary의 host 파일 읽기만으로 네 PC의 준비나 GitHub 게시 성공을 대신 증명하지 않는다. 현재 팀 전체 가동과 황대겸·신진하·최길웅 PC의 최종 검증 완료를 이 문서만으로 주장하지 않는다.
