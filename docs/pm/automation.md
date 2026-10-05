# 팀 개발 자동화 운영

2026-10-05 정이량의 “모두 진행하자 반영해” 승인으로 구축했다. 이후 사용자는 정이량 CLI가 다음 업무 판단·배정·독립 검수·조건부 병합·후속 배정을 이어가도록 승인했다. 단일 저장소·담당 영역·31개 신청 요구사항·보호 규칙은 유지한다. **검증 전 팀 모드와 개인 선택은 모두 OFF**다. 자동화 코드·각 PC 준비·실제 개발 완주·참가작 완성은 별도다. 최신 실행 경계는 [Docker 격리 설정](../bootstrap/automation-isolation.md), 자동 PM은 [고정 정책 운영](autonomous-pm.md)을 따른다.

## ON/OFF를 누가 정하는가

정이량이 이 채팅에서 “팀 자동화 ON/OFF/긴급 STOP”을 지시하면 PM AI가 인증된 운영 자격증명으로 적용하고 실제 상태를 다시 조회한다. 각 팀원은 자기 자동화만 켜거나 끈다. 팀 ON과 개인 ON이 모두 있어야 자기 Worker가 승인 작업을 가져간다. 전원을 켜도 PC·인증·실행 환경이 준비되지 않으면 작업하지 않는다.

| 모드 | 동작 |
|---|---|
| ON | 승인된 작은 작업만 배차 → 격리 개발·검사 → 불변 기록 → PR. 별도 자동 PM 정책·PM 개인 ON이면 독립 검수·조건부 병합·병합 후 인수·후속 배정 |
| OFF | 새 자동 착수·코드 게시 중단, 실행 중인 자기 Worker도 종료. 기존 사람 지시·Issue·Project·메일·상세 기록·PM 검수와 아래 병목 개선은 계속 사용. 이미 완료된 읽기 검토의 일반 댓글은 게시 가능 |
| STOP | 새 배차·게시 허가 중단. Worker가 연결된 자기 실행을 종료하고 복구 기록 보존. 이미 GitHub가 받은 요청을 되돌리는 기능은 아님 |

```powershell
uv run --no-sync python -X utf8 scripts/automation.py status
uv run --no-sync python -X utf8 scripts/automation.py mode on
uv run --no-sync python -X utf8 scripts/automation.py mode off
uv run --no-sync python -X utf8 scripts/automation.py mode stop
# 개인 선택은 자기 인증 계정으로, 예: 신진하
uv run --no-sync python -X utf8 scripts/automation.py mode on --member 신진하
```

팀 모드는 [운영 Issue #28](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/28)의 자동화 현황 댓글에도 표시한다. 실제 현재 값은 인증된 `automation.py status`가 기준이다. [저장소 Projects](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/projects)는 조직 Project1을 연결한다. 개인 Project3를 새 운영에 쓰지 않는다.

## 기존 병목 개선은 OFF에도 적용

- 큰 과제는 제출·검수 가능한 작은 단위로 나눈다. 일부 PR 인수는 부모 과제 Done과 구분한다.
- PM은 담당·목적·고정 main commit·입출력 샘플·허용 파일·검사 명령·완료 조건·의존·기한을 지정한다. 일반 `Ready`만 보고 자동 착수하지 않는다.
- 팀원은 자기 세션 공간을 사용하고 수동 작업도 중앙 경로/자원 예약을 한다. 검수 대기 결과의 경로 잠금은 PM 인수까지 유지하며 다른 승인 범위를 이어간다.
- 기존 공유 모델에 인증된 접근을 제공한다. 모델·digest·생성 옵션·자료 버전을 고정해 팀원이 직접 검증하고 결과를 PM에게 전달한다. OFF에서도 사용 가능하다.
- 개발과 읽기 전용 독립 검수는 병렬 운영한다. PM의 운영 계정과 Worker 자격증명은 분리한다.

## 작업 패킷과 잠금

정식 배정은 기존 `assign_task.py`의 Issue·배정 JSON·실제 메일 경로를 따른다. 자동화 패킷은 그 배정의 작은 실행 단위이며 별도의 공식 완료 승인이 아니다. `scripts/automation.py prepare`로 고정 배정과 코드를 연결하고 `enqueue`로 PM이 승인한다. 미완성 선행 작업·부분 개발은 명시적 PM 검토 없이 자동 해제하지 않는다.

패킷은 job ID·담당 계정·parent task ID·assignment ID·승인 근거·고정 commit·허용 파일·검사 명령·시간 제한·우선순위·잠글 자원·선행 작업을 포함한다. 샘플은 `services/automation/job.example.json`이다. 승인된 구현 패킷만 실행하며 확장 아이디어는 자동 채택하지 않는다.

SQLite 배차가 같은 작업·겹치는 경로·공유 자원의 동시 사용을 막는다. lease 만료는 고아 상태로 남겨 잠금을 유지한다. PM이 기존 실행 중단을 확인한 뒤에만 재배정한다. 최대 두 번까지 명시적으로 재시도하며 무한 재시도하지 않는다. 구현 중 main 이동은 PM 재검토 대상으로 남긴다. 읽기 검토는 PR의 고정 head를 사용하고 게시 전에 최신 head를 다시 확인한다.

```powershell
uv run --no-sync python -X utf8 scripts/automation.py reserve manual-data13 --path data/research/my-run --ttl 3600
uv run --no-sync python -X utf8 scripts/automation.py release manual-data13
uv run --no-sync python -X utf8 scripts/automation.py enqueue docs/pm/automation/jobs/승인된작업.json
uv run --no-sync python -X utf8 scripts/automation.py reconcile 작업ID --action block --reason "기존 실행 종료 확인" --runner-stopped
```

## 기록·보고·PM 경계

자동 작업은 `docs/작업기록/세션/{성명}/{job_id}.md`와 `docs/작업근거/세션/{성명}/{job_id}.md`를 **새 파일로** 남긴다. 원문 지시·AI 해석·가정·실제 수행·파일·검사·실패·한계·다음 행동을 기록한다. 같은 이름의 과거 기록은 덮어쓰지 않는다. 수동 작업의 기존 개인 문서 형식은 유지하고 개인 재개 요약은 자기 담당 단일 기록자가 세션 링크를 연결한다.

Worker는 자기 GitHub 계정으로 브랜치·PR까지만 게시한다. 고정 배포한 보고 스크립트의 해시를 확인한 뒤 자기 세션 두 문서를 같은 PR head 링크로 제출한다. 실제 ACCEPTED를 확인하며, 보고 실패는 PR을 보존하고 미완료로 남긴다. 팀원이 Project 설정·배정·공식 Done을 변경하지 않는다. PM의 읽기 검토 결과는 고정 head의 일반 댓글이며 승인·병합을 대신하지 않는다.

PM이 검수 → 실제 병합 → 병합 후 통합 실행 → 기존 phase2·공식 Project 승인 스냅샷 갱신을 수행한다. 최신 사용자 위임으로 고정 자동 PM broker도 등록된 필수 capability 안의 일상 배정·독립 검수·조건부 병합·인수를 수행할 수 있다. 현재 main/base·PR head·필수 CI 전체 SUCCESS·개발과 다른 검수 세션·실제 검사 근거를 확인하고 즉시 재조회한다. 무인 관리자 bypass는 기존 수동 권한과 별도로 고정 정책에 명시하며 보호 규칙을 낮추지 않는다. 자동화 작업 `accepted`는 부모 phase2 Done·의존 해제와 별도다. 최신 부모 완료 경로는 [연쇄 운영 지침](orchestration.md)을 따른다. 모든 요구의 실제 근거·독립 판정·완료 증거 게시 PR·실제 CI/병합·Project 및 중앙 수신을 확인한 부모만 완료하고, 연결 설정이나 작은 업무 인수만으로 Done을 만들지 않는다. Worker는 main push·병합·bypass를 하지 않으며, 범위/계약/운영 정책/권한 변경·공식 제출·추가 비용은 사용자 판단으로 올린다.

## 현재 연결과 남은 설치

중앙 배차·모델 게이트웨이·메타데이터 bridge는 연구실의 LG 전용 user 서비스와 영구 SQLite로 분리했다. 공개 연결은 `https://eryang-lab.tailb7c3c1.ts.net/lgax-automation`이며 Bearer 인증을 요구한다. 기존 `/`, `/lg-ax`, 8443/10000 경로는 유지한다.

**현재 HTTPS 접근은 정이량 PC의 LG 전용 연결을 경유한다. 이 PC가 꺼지면 팀원의 원격 접속도 중단된다.** 서버 직접 HTTPS 공개는 서버 관리자 권한이 없어 완료하지 않았다. 연결 장애 때 Worker는 새 작업·게시를 중단한다. PC 없이 공개 접속하려면 연구실 관리자가 LG 경로의 HTTPS 연결을 별도로 제공해야 한다.

네 PC의 전용 실행 계정/VM·개별 GitHub 인증·선택한 Codex 또는 Claude Code 로그인·Worker 실행 확인은 각 환경에서 필요하다. [각 PC 초기 설정](../bootstrap/automation-workers.md)을 자기 AI와 진행한다. Windows 설치는 `services/automation/install-worker.ps1`, Linux 예시는 `lgax-worker.service`를 따른다. 개인 PC의 환경변수 제거만으로 파일·키체인까지 격리했다고 표현하지 않는다. GitHub self-hosted runner는 현재 설치하지 않았으며 개인 PM 계정에 무제한 workflow 실행 권한을 부여하지 않는다. 고정 Worker의 승인 큐 polling을 먼저 사용하고 runner는 전용 실행 환경에서 선택적으로 추가한다.

10/5 이전 Worker는 모델/테스트와 publisher가 같은 OS 사용자여서 황대겸의 무해한 canary 접근 보고대로 폴더/환경변수 분리만으로 경계를 보장하지 못했다. 현재 코드는 고정 host supervisor가 인증을 보유하고 모델·저장소 테스트·빌드·설치는 Docker에서만 실행한다. 모델에는 본인의 전용 AI 프로필과 Git metadata 없는 작업 복사본만, 검사에는 별도 소스 복사본과 인증 없는 network=none 환경만 제공한다. 실제 image ID·mount/user/network를 확인하고 Docker 불가 때 native 실행으로 대체하지 않는다. 검사가 끝난 소스 해시·링크/범위/유출·공유 Git 설정을 확인한 뒤 깨끗한 별도 worktree에서 게시한다. 실제 canary와 로그인·개발/검수/병합 완주의 증거는 따로 인수하며 **개인/팀 검증 전 OFF를 유지한다.** 전용 계정/VM이라는 이름이나 isolation_acknowledged=true는 완료 근거가 아니다.

팀원은 자기 GitHub CLI로 로그인한 뒤 `automation.py setup --member {성명} --controller-url {위주소}`를 실행한다. GitHub 토큰은 인증 확인에만 전달하며 서버에 보관하지 않는다. 개인 자동화 토큰을 발급받고 Codex는 별도 CODEX_HOME에서 `codex login`, Claude Code는 별도 CLAUDE_CONFIG_DIR에서 `claude auth login`한다. 인증 파일을 공유하거나 여러 PC에서 복제하지 않는다. 선택한 `worker.example.json` 또는 `worker.claude.example.json`의 절대 경로를 자기 환경에 맞추고 격리를 실제 확인한 뒤 설치한다. 고정 runtime/report bundle을 저장소 밖에 배포한다. 모델 프록시는 `python -m services.automation.model_proxy --config {개인client.json}`으로 loopback18873에 제공한다.

기존 코어의 모델 설정은 `LGAX_MODEL_ADAPTER=ollama`, `LGAX_MODEL_ENDPOINT=http://127.0.0.1:18873`, `LGAX_MODEL_ID=qwen3:8b`, `LGAX_MODEL_DIGEST=500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`이다. Worker에 프록시 URL을 설정하면 같은 값을 제공한다. 실제 생성 옵션과 사용량을 기록하며 인증 토큰을 모델 프롬프트에 넣지 않는다.

## 지원 범위와 확인 기준

Claude Code도 같은 큐·ON/OFF·작업 lock·세션 기록·PR·PM 검수를 사용한다. 개인 설정의 engine으로 선택하며 현재 실행기끼리 자동 fallback하지 않는다. Claude의 실제 native 옵션/빈 로그인 거부는 점검했으나 개인 구독 로그인과 실제 모델→검사→PR pilot는 각 PC에서 남아 있다. 상세 설치·제한 도구·구독 정책과 실제 검증 범위는 [초기 설정](../bootstrap/automation-workers.md)을 따른다. CLI 버전 변경은 PM의 재검증 대상이다.

OpenAI의 [CI/CD 인증 안내](https://learn.chatgpt.com/docs/auth/ci-cd-auth)는 개인 로그인 상태를 신뢰된 지속 runner에서 보존하는 고급 구성을 설명한다. 한 인증 파일을 병렬 실행·여러 PC에 공유하지 않고 만료·재로그인을 처리해야 한다. [비대화형 실행](https://learn.chatgpt.com/docs/non-interactive-mode)과 [요금/사용량](https://learn.chatgpt.com/docs/pricing)을 따른다. ChatGPT 구독 사용량과 API 별도 과금은 구분하며 API로 자동 전환하지 않는다. 무제한·24시간 성공을 보장하지 않는다.

실제 설치·인증·도구 실행 증거, OFF/STOP·timeout·재시도·복구·잠금·권한 거부 검사와 최종 CI를 남긴다. 현재 읽기 전용 Codex pilot 성공을 개발 Worker의 전체 무인 완주로 표현하지 않는다. 실제 배포와 검사 기록은 `evals/team-automation/20261005/`에서 확인한다.

PR75는 원격 CI4 성공 후 정이량 PM이 main `c6c1382`에 수동 병합했고, 병합 후 CI와 같은 코드 여부도 확인했다. [실제 반영 근거](../../evals/team-automation/20261005/delivery-proof.json)를 따른다. 기존 팀원 보고 collector의 긴 한국어 보드 표시 오류도 display-only 제한으로 복구하고 대기 보고의 실제 수신 확인·원문 해시·재시작 보존을 검증했다. [복구 근거](../../evals/automation/20261005/reports-display-recovery.json)를 따른다. Worker가 팀원의 지시나 상세 기록을 줄이는 동작은 아니다.
