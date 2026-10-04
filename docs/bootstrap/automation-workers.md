# 각 PC의 자동 개발 초기 설정 — Codex / Claude Code

2026-10-05 사용자 승인으로 두 실행기를 제공한다. **각자 선호하는 실행기 하나를 선택**한다. 배정·작업 잠금·상세 기록·검사·PR·Project 보고·PM 검수는 동일하다. Claude Code 사용자는 Codex 로그인이나 구독을 추가할 필요가 없다.

검증 전 팀/개인 모두 OFF다. 초기 설정을 끝냈다고 켜지지 않는다. 최신 Worker는 [Docker 실행·검사 경계](automation-isolation.md)를 사용한다. 모델·저장소 검사에 게시 인증을 제공하지 않고 실제 canary·본인 로그인·첫 PR/보고를 확인해야 한다. 정이량의 [자동 PM](../pm/autonomous-pm.md)은 별도 정책과 PM 개인 ON이 필요하다. 중앙 HTTPS는 아직 정이량 PC를 경유한다. 네 PC의 실제 준비는 각자 근거로 확인한다.

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
| 8. 경계/pilot/등록 | 실제 canary 분리 확인 → PM의 작은 승인 패킷으로 개발 pilot → 서비스 등록/개인 ON을 별도 확인 | model/validator 게시 canary 거부, 실제 종료/검사/자기 PR/보고 수신 확인. host canary 읽기와 GitHub 게시를 구분 |

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

report bundle 출력의 `trusted_report_script`·`trusted_report_sha256`도 설정에 추가한다. 공유 모델은 기존 개인 model proxy를 loopback18873에 실행하고 model_gateway_url로 연결한다. 공유 모델을 사용하지 않는 pilot는 이 선택 필드를 생략할 수 있다. 서비스 등록은 Windows `services/automation/install-worker.ps1`, Linux `lgax-worker.service`의 **개인 실제 경로**를 적용한다. Linux ReadWritePaths에도 선택 엔진 인증 폴더를 넣는다. Windows 등록은 해당 사용자가 로그인된 동안만 실행되며 sleep/offline에서는 작업할 수 없다.

사용자 직접 필요한 부분은 자기 계정 로그인이다. 환경 준비·설정 작성·bundle·점검·자기 상태 보고는 각자의 AI가 수행한다. 설치/로그인을 할 수 없으면 원인과 다음 행동을 자기 기록/Project에 남기고 기존 수동 작업은 계속한다.
