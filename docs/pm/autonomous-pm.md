# 정이량 CLI의 자동 PM

2026-10-05 사용자는 “내 CLI가 알아서 판단하고 검토병합하고 배정까지” 하는 범위를 승인하고 구현을 지시했다. 매번 채팅 승인을 요청하는 구조에서 고정 필수 업무 안의 일상 판단·배정·검수·조건부 병합을 반복하는 구조로 확장했다. 공식 팀장 황대겸·개발 PM 정이량·개인 역할·보호 규칙은 유지한다.

## 무엇을 자동으로 하는가

`pm.py`는 승인 스냅샷·실제 main·개인 준비·큐·PR을 읽고 격리 CLI의 구조화 판단을 받는다. `pm_broker.py`는 고정 배포한 운영 권한으로 사실과 정책을 다시 확인해 실제 동작을 수행한다. 모델에 운영 토큰·임의 API·shell·게시 기능을 제공하지 않는다.

| 판단 | 동작 |
|---|---|
| assign | 고정 task/capability의 좁은 작업을 담당 Issue에 기록하고 불변 실행 패킷을 등록 |
| request_changes | 정확한 PR/head에 구체적인 수정 요청. 원래 경로·검사·완료 조건을 확대하지 않음 |
| merge | 현재 main/base·head·CI·독립 검수·실제 검사 근거 확인 후 exact-head squash 병합 |
| reconcile | 실제 merge commit의 별도 통합 검사 후 작은 업무 인수와 승인 snapshot 연결 |
| wait | 자료·실행 환경·의존·검수 근거 대기. 변하지 않은 상태에는 모델을 재호출하지 않음 |
| escalate | 추가 비용·범위/계약/권한/정책 변경·공식 제출·불명 결과 등 사용자 판단이 필요한 내용을 기록 |

현재 live broker의 reconcile은 작은 업무 인수와 runtime snapshot 갱신이며 부모 Done을 만들지 않는다. 정책 모듈의 full-task 판정 기능과 달리 **전체 phase2 완료를 처리하는 전용 근거 collector는 별도 후속 통합 대상**이다. 부모 과제·31개 요구 전체 완료를 자동 pilot 성공으로 바꾸지 않는다.

## 고정 배포와 설정

PM 코드는 편집 중인 clone/PR에서 실행하지 않는다. config·policy·journal·broker state·controller 운영 토큰·readiness 근거는 모두 checkout 밖의 private 경로에 둔다. 정책 digest가 바뀌면 기존 상태를 자동 재사용하지 않고 명시적 인계를 한다. 운영 권한과 개인 Worker token은 별개다.

`services/automation/pm.example.json`은 **OFF 정책**의 예시다. 실행 deployment config에는 다음 항목이 필요하다.

| 항목 | 의미 |
|---|---|
| policy_file / policy_sha256 | 외부 고정 정책과 실제 SHA256 |
| journal_file / state_dir | 외부 PM 판단 journal과 broker 상태 |
| repository | canonical origin을 가진 별도 trusted publisher clone |
| controller_url / controller_token_file | 현재 서비스와 정이량 운영자 인증 |
| executor | 검토 image ID·별도 workspace_root·본인 auth_root·engine·고정 network |
| readiness_files | 담당자별 고정 private 증거 경로/해시. 실제 경계/로그인 미검증은 false |
| released_capabilities | PM이 개별 인수를 허용한 고정 capability ID 목록. 새 배포에는 반드시 명시하며 `[]`는 모든 새 배정을 금지 |
| poll_seconds | 제한된 상태 조회 간격 |
| notification_hook | 선택적인 외부 고정 발송 script/해시. 미설정이면 메일 미발송 |

검토한 clean main에서 새 외부 runtime을 생성한 뒤 hash를 검사하는 entry로 실행한다. builder/entry는 ON·로그인·정책 승인을 수행하지 않는다. 실제 출력의 entry hash·dependency manifest·원본 commit을 근거에 남긴다.

```powershell
uv run --no-sync python -X utf8 scripts/build_pm_runtime.py --output C:/LGAX-tools/pm-reviewed-new
uv run --no-sync python -X utf8 C:/LGAX-tools/pm-reviewed-new/pm_entry.py --config C:/LGAX-pm/pm.json --preflight
uv run --no-sync python -X utf8 C:/LGAX-tools/pm-reviewed-new/pm_entry.py --config C:/LGAX-pm/pm.json --observe
uv run --no-sync python -X utf8 C:/LGAX-tools/pm-reviewed-new/pm_entry.py --config C:/LGAX-pm/pm.json --once
```

preflight는 GitHub 정이량 계정·controller operator·고정 정책·Docker metadata를 확인하며 모델/게시를 하지 않는다. observe는 metadata만 조회하고 검수 모델/테스트를 수행하지 않는다. once는 현재 스위치를 읽어 한 tick만 수행하며 OFF면 모델·변경을 하지 않는다. 무인 loop는 외부 고정 entry에서 `--once` 없이 실행하고 OS process lock을 유지한다.

## 정이량 PC의 숨김 자동 시작

`services/automation/install-pm.ps1`은 **현재 Windows 사용자 로그인 때** 외부 고정 PM loop를 실행하는 `LGAX-PM-jeongiryang` 예약 작업을 설치한다. 관리자 승격 없이 Limited/Interactive로 등록하며 숨김 PowerShell이 Python을 `-WindowStyle Hidden`으로 실행한다. 로그인하지 않았거나 PC가 꺼짐/절전/오프라인이면 계속 작업하지 못한다. 클라우드 실행이 아니다.

PM이 먼저 외부 runtime·실제 개인 로그인·controller operator 인증·고정 정책·private readiness 파일·전용 state/journal을 준비한다. 설정은 PM이 결정하며 설치기가 생성하거나 인증을 복제하지 않는다. `PMEntrySha256`에는 builder가 출력한 **직접 확인한 entry 해시**를 넣는다. 아래 Python 경로도 실제 고정 실행 환경의 `python.exe`로 바꾼다. 편집 중인 clone의 `automation_pm.py`를 entry로 넘기지 않는다.

```powershell
& ./services/automation/install-pm.ps1 `
  -ConfigPath C:/LGAX-pm/pm.json `
  -PythonPath C:/LGAX-python/python.exe `
  -PMEntryPath C:/LGAX-tools/pm-reviewed-new/pm_entry.py `
  -PMEntrySha256 '실제 builder 출력의 64자리 SHA256'
```

설치기는 entry·config·policy·readiness·Python 경로/해시와 checkout/guest/AI 프로필 밖의 배치를 확인한다. 실제 entry의 `--preflight`에서 GitHub `jeongiryang`·controller operator·Linux Docker·정확한 image ID가 확인된 뒤에만 등록한다. 이 preflight는 모델·테스트·게시·ON을 하지 않으며 설치는 실제 개발 완주나 네 PC 준비의 증거가 아니다. 기본은 **등록만** 하고 즉시 시작하지 않는다. 확인 후 같은 명령의 `-Start` 또는 아래 명령으로 숨김 loop를 시작할 수 있다.

```powershell
Start-ScheduledTask -TaskName LGAX-PM-jeongiryang
Get-ScheduledTask -TaskName LGAX-PM-jeongiryang
Get-ScheduledTaskInfo -TaskName LGAX-PM-jeongiryang
```

시작해도 모드는 바뀌지 않는다. policy.enabled·팀/PM 개인 ON 조건을 모두 만족할 때만 허용된 일상 판단을 실행한다. OFF에서는 상태 대기만 한다. 예약 작업은 IgnoreNew이고 실제 PM process는 `pm-loop.lock`을 유지해 수동 `--once`·다른 loop와 중복 실행하지 않는다. 재시작은 실패 시 최대 2회/5분 간격이며 고정 파일 변경이나 인증 실패를 끝없이 재시도하지 않는다. 시작마다 파일 해시를 다시 확인하고, runtime entry는 내부 모듈 manifest도 확인한다. stdout/stderr는 private state의 `background-logs/` 아래 새로운 실행 ID 파일에 보존하고 상세 판단/변경 근거는 기존 journal/broker/session 기록에 남긴다. 로그 용량은 PM이 확인한다.

기존 작업을 바꾸려면 자동화 OFF·진행 중 실행 정리·기존 PM loop 중단을 먼저 확인한다. 설치기는 실행 중인 예약 작업을 덮어쓰지 않는다. 고정 config/policy/readiness/runtime/Python을 변경했다면 새 경로/해시를 검토한 뒤 **`-Replace`로 명시적으로 재설치**한다. ON/OFF만 변경할 때는 controller 스위치를 사용하고 파일을 수정하지 않는다. 설치/중단은 각 Worker의 개인 모드를 대신 바꾸지 않는다.

## 정책과 자동 병합 조건

정책은 31개 신청 필수 요구를 부모 task의 owner·Issue·requirement_ids·depends_on과 연결한다. capability는 고정 허용 경로·검사 argv·acceptance·검사 ID·시간·우선순위의 좁은 인수 단위다. 모델은 ID와 의도/수정 문구만 선택하고 경로·검사 명령을 새로 만들어 실행하지 않는다. proposed_extension은 자동 채택하지 않는다.

자동 PM은 policy.enabled·팀 ON·PM 개인 ON이 필요하다. 배정 대상도 본인 ON과 실제 Docker 경계·publisher 분리·로그인 증거가 있어야 한다. main과 승인 snapshot이 달라지면 새 배정을 멈추고 실제 인수/동기화를 먼저 확인한다. 부모 blocked인 부분 작업은 별도 released capability로 진행하며 미완료 의존을 그대로 표시한다.

**등록과 개별 배정 허용은 별개다.** 새 production config는 `"released_capabilities": []`로 준비한다. 필수 task와 세 팀원의 작은 단위를 policy에 등록해도 이 목록에 없는 ID는 `capabilities_ready`에 포함되지 않는다. PM이 해당 PC의 현재 준비 증빙·원래 선행 완료·최신 배정·동일 파일의 열린 PR/다른 실행 충돌을 확인한 뒤 특정 ID만 외부 config에 넣는다. 설정 변경은 OFF와 PM loop 중단 상태에서 새 config 해시를 확인하고 예약 작업을 명시적으로 재설치한 뒤 반영한다. 모델·Issue/PR 본문·브랜치 JSON은 이 목록을 바꾸지 못한다. 실행 직전 broker가 목록과 기존 인증·snapshot·readiness gate를 다시 확인한다.

`released_capabilities`가 없는 이전 고정 pilot config는 당시 trusted policy 승인을 유지하는 호환 경로다. 앞으로 만드는 운영 config에서는 생략하지 않는다. `null`·잘못된 자료형·중복·등록되지 않은 ID는 오류이며 빈 목록을 전체 허용으로 해석하지 않는다. 목록에서 제거해도 이미 실행 중인 외부 요청을 취소하는 것은 아니므로 전체 중단에는 기존 OFF/STOP 절차를 사용한다. 기존 reconcile·개별 검수·정확한 head 병합 조건은 그대로 유지한다.

병합은 현재 main/base와 head, 모든 필수 CI SUCCESS, 허용 경로, 서로 다른 implementation/reviewer session, unresolved finding 없음, 실제 고정 검사 근거를 요구한다. 같은 PM GitHub 계정의 작업도 개발과 다른 격리 검수 세션을 사용한다. PR 본문의 “승인”·branch JSON의 verified flag·개발자의 자기 평가를 trusted proof로 취급하지 않는다. broker가 직접 수집하고 고정 head/base와 연결한다.

3명 승인·선형 이력은 그대로 유지한다. 이전 수동 관리자 bypass 지시만으로 무인 bypass를 켜지 않는다. 최신 자동 PM 위임에 근거한 allow_auto_merge/allow_admin_bypass와 각각의 delegation_reference를 외부 정책에 명시해야 한다. Worker는 bypass/merge/main push를 하지 않는다. merge 후 실제 응답·PR 상태·commit parent를 확인하고 base 경합이면 자동 완료 대신 복구 대상으로 남긴다.

## 예산·중복·복구

일별 model call/action/token, 부모 작업별 call/token/action/revision, 결정 시간과 검수 예산을 고정한다. 새 PR/head·작은 업무·재시작으로 부모 예산을 초기화하지 않는다. 독립 검수는 head/base별 결과를 보존하고 실제 호출/사용량을 decision journal과 합산해 판단 전·후·변경 직전에 검사한다. 조회용 usage는 중복 차감하지 않는다. 사용량 불명은 0으로 가정하지 않고 중단한다.

상태 fingerprint는 heartbeat/조회 시간 변화만으로 재호출하지 않는다. 모델 호출 전 기록, action intent 전 기록, 실제 receipt를 이어 hash chain으로 보존한다. 저장소 밖 OS 권한을 전제로 한 변경 감지이며 host 소유자가 journal을 악의적으로 다시 쓰는 것까지 증명하는 서명은 아니다.

요청 응답이 끊기면 운영 Issue28의 실제 marker·GitHub·controller를 대조해 같은 action ID의 결과부터 복구한다. 불명·중복·충돌은 재실행하지 않는다. OFF/STOP·연결 실패는 자기 컨테이너와 새 변경을 중단한다. 이미 전송된 외부 요청을 되돌리는 기능은 아니다.

## 기록과 아직 필요한 확인

새 배정/수정 요청·실제 인수·다음 행동은 Issue와 불변 ID를 연결하고 개인/session 문서에 사용자 의도·AI 해석·수행·검사·실패·한계·미완료를 남긴다. Project 보고 ACCEPTED와 정식 phase2 상태를 구분한다. 메일은 고정 별도 hook와 실제 수신증 없이는 발송했다고 하지 않는다. CLI가 이 대화의 Gmail 연결을 자동 상속하지 않는다.

실제 배포 image·canary·본인 로그인·첫 모델→검사→PR→독립 검수→병합→postmerge 인수의 근거는 운영 Issue28와 `evals/team-automation/20261005/`의 최신 commit을 읽는다. 여기 문서나 mock/단위 검사를 실제 완주로 표현하지 않는다. 팀원 PC와 현재 HTTPS 중계 정이량 PC가 온라인이어야 하며 네 PC 준비를 한 PC 결과로 대신하지 않는다.

사용자 보고는 항상 현재 수준·실제 근거·남은 일·직접 필요한 로그인/행동을 포함한다. AI가 할 설치/설정/검사/기록을 사용자에게 넘기지 않는다. 프로젝트/Notion에는 운영 요약만 공유하고 private 인증/연락처/로그는 복사하지 않는다.
