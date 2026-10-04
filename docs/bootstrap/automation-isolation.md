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

execution_root는 clone·state·controller token·AI 프로필과 서로 포함 관계가 없어야 한다. 링크/junction/reparse/hardlink 경로는 사용하지 않는다. `.codex`·`.claude` 전체 개인 홈이나 다른 팀원의 프로필을 mount하지 않는다. 같은 개인 프로필과 state lock은 한 Worker만 사용한다. 기존 Worker를 중단한 후 교체한다.

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
