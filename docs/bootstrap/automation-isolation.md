# 모델·검사·게시 인증 분리

2026-10-05 공통 Worker의 같은 OS 사용자 인증 접근 문제를 수정하는 실행 경계다. 별도 폴더·CODEX_HOME·CLAUDE_CONFIG_DIR·환경변수 제거는 같은 사용자 인증 접근을 막지 못했다. 황대겸이 전달한 canary 접근 보고와 이 변경의 독립 실증은 구분한다. 각 PC에서 아래 증거를 인수하기 전 개인 OFF를 유지한다.

## 실제 실행 구조

고정 host supervisor는 controller/GitHub 인증과 게시 worktree를 보유한다. 저장소 코드·모델·테스트·빌드·의존성 설치 명령을 호스트에서 실행하지 않는다. 검사/모델의 결과는 bytes·hash·경로·링크·유출 검사 후 별도 깨끗한 worktree로 가져온다.

| 실행 역할 | bind mount | 네트워크 |
|---|---|---|
| model | Git metadata 없는 `/workspace`, 제한 `/artifacts`, **본인만의 전용** `/agent-auth` | 고정 bridge network, AI 인증/모델 통신용 |
| validator | 모델 종료 후 고정한 소스의 **별도** `/workspace`, 제한 `/artifacts` | `none`; AI 인증도 제공하지 않음 |

GitHub/controller/PM/Gmail 인증·호스트 홈·원래 clone·`.git`·Docker 제어 소켓·서버 비밀은 mount하지 않는다. 정확한 image ID, non-root `1000:1000`, read-only root, capability 제거, no-new-privileges, 메모리/CPU/PID/시간 제한을 적용하고 실제 Docker inspect 결과를 확인한다. Docker가 없거나 조건이 다르면 실패한다. native fallback이나 privileged/host network로 해결하지 않는다.

자기 AI 구독 로그인은 모델 역할에 필요하므로 모델에 제공한다. 검사는 그 로그인에도 접근하지 못한다. 인증 없는 검사 환경은 외부 공유 모델에 직접 접속하지 못하므로 live-model 검사는 승인된 별도 실행/근거로 관리하고 네트워크를 임의 열지 않는다.

### Docker 내부 Codex sandbox 선택

10/5 실제 pilot에서 nonprivileged Docker 내부의 `bwrap` namespace 생성이 거부돼 Codex의 파일 조회/명령 실행이 실패했다. 실패 세션·출력·원인은 보존하고, **검사한 고정 Docker executor 안의 Codex에만** `--sandbox danger-full-access`를 사용한다. Docker의 image ID·non-root·read-only root·제한 mount·권한/자원/네트워크 검사와 daemon 측 시간제한이 외부 실행 경계다. 내부 sandbox를 지원하려고 privileged·추가 capability·host network·Docker socket을 허용하지 않는다. 기존 native argv의 read-only/workspace-write 선택은 유지하며 운영 Worker의 native fallback은 계속 거부한다.

[OpenAI 공식 Agent approvals & security](https://learn.chatgpt.com/docs/agent-approvals-security)의 Docker 안내를 2026-10-05 직접 확인했다. namespace/bwrap/seccomp 제한으로 내부 sandbox를 만들 수 없는 경우 컨테이너를 의도한 경계로 구성하고 그 내부에서 danger-full-access를 사용하는 방법을 안내한다. 동시에 컨테이너에 제공한 인증·자료는 그 안의 코드가 접근할 수 있음을 설명한다. 따라서 이 선택은 GitHub/controller/PM/Gmail 비밀을 모델에 주는 근거가 아니며, 모델에 제공하는 인증은 **본인의 선택한 AI 로그인 한 개**로 제한한다.

독립 PM 검수와 Worker review의 `/workspace`는 실제 Docker bind mount를 read-only로 만들고 inspect로 확인한다. CLI flag가 danger-full-access여도 이 mount를 쓸 수는 없다. 결과용 `/artifacts`만 별도로 쓰고, 고정 검사는 모델 종료 뒤 **인증 없는 validator**에서 수행한다. Docker 내부 argv 변경·명령 재실행·모델 출력·고정 검사·게시까지 후속 pilot으로 확인하기 전에는 기존 실패를 성공이나 참가작 완료로 바꾸지 않는다.

### 실행별 cache와 잠긴 Python 환경

이미지 빌드의 `uv sync --locked`로 `/opt/lgax-venv`에 준비한 의존성과 lock을 사용한다. 실행 시 `UV_PROJECT_ENVIRONMENT=/opt/lgax-venv`, offline·no-sync 조건을 유지해 모델이나 검사 명령이 의존성을 임의 설치/변경하지 못하게 한다. root filesystem이 read-only이므로 이 가상환경도 고정된다.

`uv --no-sync`도 cache metadata를 쓰므로 read-only 이미지의 seed cache에 실행 cache를 두지 않는다. `UV_CACHE_DIR=/home/executor/uv-cache`를 각 컨테이너의 비공개 tmpfs에 두며, `/tmp`와 `/home/executor`는 크기가 제한된 실행별 tmpfs다. npm도 고정 이미지의 seed에서 자기 실행 cache로 복사해 offline으로 사용한다. 이 cache는 AI 로그인·publisher 인증·다른 실행의 cache와 공유하지 않으며 컨테이너 종료와 함께 사라진다. 초기 cache 쓰기 실패는 보존하고 변경 후 실제 고정 검사 결과를 따로 인수한다.

### 고정 Git 게시 경로

호스트의 검토한 Worker/PM broker만 GitHub 인증을 사용한다. 고정 Git 호출에서 기존 credential helper를 비우고 **`gh auth git-credential`만** 명시하며, hooks·fsmonitor·자동 서명·확장/file protocol을 차단한다. 모델·브랜치 코드가 임의 helper나 게시 명령을 선택하지 않는다. 컨테이너에는 `.git`·GitHub 인증·이 helper의 호스트 인증 경로가 없고, 실제 검사한 bytes를 별도 게시 worktree에 반영해 자기 브랜치/PR을 만든다. 설정 존재와 실제 fetch/push/PR 성공은 별도 근거로 기록한다.

## 개인 경로 조건

아래는 황대겸 예시이며 경로와 계정은 자기 PC의 실제 값으로 바꾼다.

| 용도 | 예시 |
|---|---|
| 신뢰된 publisher clone | `C:/LGAX/lg-ax-2026` |
| controller/기록 상태 | `C:/LGAX-state/unknownamed` |
| 본인 AI 전용 프로필 | `C:/LGAX-auth/unknownamed-codex` 또는 `unknownamed-claude` |
| guest 작업·결과 복사본 | `C:/LGAX-execution/unknownamed` |
| 고정 Worker/report bundle | `C:/LGAX-tools/worker-reviewed`와 별도 report 폴더 |
| 최소 이미지 build context | `C:/LGAX-build/executor-reviewed-새버전` |

execution_root는 clone·state·controller token·AI 프로필과 서로 포함 관계가 없어야 한다. 링크/junction/reparse/hardlink 경로는 사용하지 않는다. `.codex`·`.claude` 전체 개인 홈이나 다른 팀원의 프로필을 mount하지 않는다. 같은 state lock은 한 Worker만 사용한다. 기존 Worker를 중단한 후 교체한다.

Worker와 PM이 같은 **본인** AI 프로필을 사용하면 `lgax-worker.lock`의 실제 OS 잠금으로 인증 검사·모델 실행을 직렬화한다. Worker 자체의 `worker.lock`은 서비스 실행 동안 유지한다. 개인 프로필 잠금은 초기 컨테이너 인증 검사 후 해제하며, 매 claim 직전에 다시 확보해 가져온 작업의 실행이 끝날 때까지 유지한다. **작업 없는 idle/poll 동안에는 프로필을 점유하지 않는다.** 잠금이 바쁘면 claim/모델 호출/개인 OFF 변경 없이 대기하고, `--once`/preflight는 profile_busy를 보고한다. PM도 같은 프로필을 동시에 사용하지 않는다. 실제 Windows OS 잠금 검사에서 idle 프로필 접근 허용·Worker 중복 실행 거부·busy 때 claim 없음이 확인됐으며, 배포한 고정 runtime의 실제 PM/Worker 연속 운용은 후속 pilot에서 따로 확인한다.

## 검토한 이미지 만들기

Docker Desktop의 **Linux engine**이 실제 응답하는지 먼저 확인한다. 설치 상태와 실행 가능 상태를 구분하며 다른 프로젝트의 container·network·volume을 정리하지 않는다.

```powershell
docker info --format '{{.OSType}}'
```

PM이 검토한 고정 main의 clean clone에서 최소 context를 생성한다. 전체 저장소를 `docker build .`로 보내지 않는다. helper는 Dockerfile·Python lock·웹 package/lock **5개 파일만** 읽고 새 외부 폴더를 만든다. 아래 source 경로는 자기 검토 clone이며 destination은 아직 없는 새 폴더여야 한다.

```powershell
uv run --no-sync python -X utf8 scripts/automation_isolation.py build-context --output C:/LGAX-build/executor-reviewed-new
docker build --file C:/LGAX-build/executor-reviewed-new/Dockerfile --tag lgax-executor-reviewed C:/LGAX-build/executor-reviewed-new
docker image inspect --format '{{.Id}}' lgax-executor-reviewed
```

빌드 입력/base image·lock 해시·CLI 버전·실제 이미지 ID를 근거에 기록한다. 현재 Dockerfile의 Python 3.11·uv/Node·Codex/Claude·의존성은 빌드에서 준비한다. 실행에는 mutable tag가 아닌 inspect의 정확한 `sha256:64자리`를 private worker.json의 `executor_image`에 넣는다. 이미지 변경은 재검증 대상이다. root image나 수정 중인 브랜치 Dockerfile을 무인 운영에 채택하지 않는다.

## 로그인과 metadata 점검

본인이 선택한 CLI의 전용 프로필에 직접 로그인한다. 팀원이 공유한 인증을 복제하거나 API key로 자동 전환하지 않는다. **같은 전용 profile을 mount한 Linux CLI의 실제 인증**을 확인한다. OS 키체인/CLI 차이로 컨테이너 인증이 안 되면 준비 미완료로 남기고 해당 실행 환경의 직접 로그인을 안내한다. 프로필 전체나 운영 토큰을 임의 추가 mount하지 않는다. Codex의 고정 image 직접 로그인은 아래 CLI가 device URL/code를 안내한다. 사용자는 자기 계정으로 직접 인증하고, AI는 계정 토큰을 복사하지 않는다.

```powershell
uv run --no-sync python -X utf8 scripts/automation_isolation.py login --config C:/LGAX-state/unknownamed/worker.json
```

이 login helper는 현재 Codex용이다. Claude 사용자는 선택한 Linux 실행 환경의 자기 claude.ai 로그인을 직접 준비한다. Claude browser/GitHub App 로그인과 컨테이너 CLI 로그인을 혼동하지 않고 검사에 실패하면 OFF·미완료로 보고한다.

Worker의 `--preflight`는 본인 GitHub·controller metadata를 확인한다. Docker image/execution_root가 구성돼 있으면 **선택한 컨테이너 CLI의 버전과 구독 로그인**을 실제 검사한다. 구성되지 않았으면 `metadata_only`·`container_auth_verified=false`이며 Windows Claude 로그인으로 준비 완료를 대체하지 않는다. canary·유료 생성·테스트·GitHub 게시를 실행하지 않아 `automation_ready=false`이고, `isolation_acknowledged` true로 경계를 대신하지 않는다.

## 각 PC canary 확인

`verify_canary_boundary`는 실제 비밀 없이 다음을 검사한다.

- host publisher는 자기 인증 영역에 둔 **무해한 canary**를 읽는다.
- model과 validator의 Python 프로세스는 작업 canary를 읽지만 게시 canary의 host/guest 경로 접근은 실패한다.
- model만 자기 AI-profile canary를 읽고 validator는 읽지 못한다.
- validator의 실제 network가 none이며 controller/GitHub 환경변수와 Docker socket이 없다.

helper는 모델 역할의 Python으로 파일 경계를 검사한다. **Codex/Claude 모델 생성이나 실제 GitHub 게시 검증은 아니다.** canary의 위치/해시·실행 image/mount/user/network·결과를 기록하고 실제 비밀 값을 테스트에 넣지 않는다.

고정 CLI는 자기 GitHub 계정·정확한 image와 경로를 확인하고 새 분리 작업/결과 폴더·무해한 publisher canary를 만들어 경계를 검사한 뒤 선택한 컨테이너 CLI의 실제 로그인 metadata를 확인한다. 기존 Worker와 profile lock을 공유한다. 과거 proof를 덮어쓰지 않도록 새 출력 이름을 쓴다.

```powershell
uv run --no-sync python -X utf8 scripts/automation_isolation.py verify --config C:/LGAX-state/unknownamed/worker.json --output C:/LGAX-state/unknownamed/readiness-new.json
```

private worker.json의 image ID와 profile/execution 경로를 실제 값으로 먼저 설정한다. proof 출력은 모든 checkout·guest 실행 폴더·AI 프로필 밖의 **새 private 파일**이어야 하고 기존 근거를 덮어쓰지 않는다. verify 성공은 경계·로그인 metadata의 증거이고 `github_publication_verified=false`, 자동화 OFF다. 실제 모델 개발·GitHub 게시/보고는 다음 pilot에서 확인한다. 공개 근거에는 필요한 image/role/해시/성공·실패만 옮기고 private 절대 경로·토큰·로그인을 복사하지 않는다. PM은 공개 설정 flag 대신 고정 private readiness 파일의 해시와 실제 증거를 인수한다.

## PM 운영 코드의 외부 hash 배포

PM은 검토한 clean main에서 아래 builder로 새 외부 runtime을 만든다. policy·config·journal·readiness와 토큰도 checkout 밖에 별도로 둔다. entry가 복사된 PM/Worker/isolation 모듈과 scripts manifest를 검사하고 변경되면 실행하지 않는다. 이 builder는 ON·로그인·정책 승인을 수행하지 않는다.

```powershell
uv run --no-sync python -X utf8 scripts/build_pm_runtime.py --output C:/LGAX-tools/pm-reviewed-new
uv run --no-sync python -X utf8 C:/LGAX-tools/pm-reviewed-new/pm_entry.py --config C:/LGAX-pm/pm.json --preflight
```

`build-context`는 Dockerfile/lock이 있는 검토 clean clone에서, 운영 PM loop는 이 외부 entry에서 수행한다. 생성한 entry hash·manifest·원본 commit과 실제 검사 결과를 인계한다. editable branch scripts를 고정 운영 코드처럼 사용하지 않는다.

## 첫 작업과 완료 판정

개인 로그인·경계 실증 뒤 작은 승인 작업을 통해 실제 모델→고정 검사→자기 브랜치/PR→보고 ACCEPTED를 확인한다. 자동 PM은 별도 독립 세션 검수→정확한 head/CI→조건부 병합→병합 후 검사/인수를 확인한다. 설치만으로 해당 과정이 완료됐다고 표현하지 않는다.

황대겸은 기존 코어 중단·개인 OFF를 유지하며 최신 고정 코드와 경계 검증 근거를 인계받은 후 자기 PC의 이미지/로그인/canary/설치를 이어간다. 사용자 직접 필요한 단계는 본인 로그인이다. 설치·폴더·검사·상세 기록·보고는 자기 AI가 진행한다. 다른 팀원도 같은 경계를 적용한다.
