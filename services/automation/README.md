# 승인 작업 자동화

[팀 운영과 ON/OFF](../../docs/pm/automation.md), [실행 경계](../../docs/bootstrap/automation-isolation.md), [자동 PM](../../docs/pm/autonomous-pm.md)을 먼저 읽는다. 중앙 서비스는 데이터와 잠금을 관리한다. 고정 host supervisor만 controller/GitHub 인증을 보유하며 모델·저장소 테스트·빌드·설치는 Docker에서 실행한다. Docker 미준비 때 호스트 실행으로 대체하지 않는다. 기존 bridge는 일반 댓글/현황, 별도 자동 PM broker는 사용자 위임과 고정 정책 안의 배정·검수·조건부 병합을 담당한다.

- `state.py`: 영구 큐·원자 배차·lease·경로/자원 잠금·OFF/STOP·PM 조정.
- `controller.py`: 인증·PM 운영자/Worker 분리·개인 가입·선택적 공유 모델.
- `worker.py` / `process.py`: 작업별 공간·상한/중단·실제 검사·불변 기록·별도 PR 게시.
- `claude.py`: 개인 claude.ai 인증·고정 CLI·restricted 파일 도구·구조화 최종 결과. 같은 Worker의 배차/중단/검사/게시/보고 경계를 사용한다.
- `isolation.py` / `Dockerfile.executor`: 최소 build context·정확한 image ID·실제 mount/user/network 검사·모델과 인증 없는 validator 분리·canary 경계 실증.
- `artifacts.py`: 고정 소스 복사·링크/범위/유출 검사·검사 후 byte 일치 확인·별도 깨끗한 worktree 게시.
- `pm.py` / `pm_broker.py`: 등록된 필수 capability의 다음 업무 판단·배정·독립 검수·조건부 병합·병합 후 인수. 영구 예산·event 중복 방지·intent/실제 receipt·불명 결과 복구.
- `github_bridge.py`: 고정 PR 읽기 검토 배정·head 재확인·중복 방지·Issue28 현황.
- `model_gateway.py` / `model_proxy.py`: 현재 LG Qwen 모델의 digest와 옵션을 검사하는 인증된 검증 경로. 임의 서버·모델 다운로드·GPU 제어는 제공하지 않는다.

로컬 개발 실행은 비공개 설정을 사용한다. 신규 초기화는 기존 상태를 덮어쓰지 않는다.

```powershell
uv run --no-sync python -X utf8 scripts/automation.py init
uv run --no-sync python -X utf8 -m services.automation.controller --config private/automation/controller.json --port 18871
uv run --no-sync python -X utf8 scripts/automation.py status
uv run --no-sync python -X utf8 -m unittest discover -s tests -p "test_automation*.py" -v
```

`worker.example.json`은 설치 전 예시이며 실제 계정·절대 경로·본인의 전용 AI 인증·정확한 `executor_image=sha256:...`·별도 `execution_root`·고정 외부 보고 bundle을 준비한다. `isolation_acknowledged`는 과거 호환용 기록이며 실제 경계 증거를 대신하지 않는다. 운영자 토큰은 Worker에 주지 않는다. 개인 준비·canary·실제 로그인/게시를 확인한 뒤 서비스 등록과 개인 ON을 구분한다. 파일 생성만으로 설치·ON·인증 완료를 보고하지 않는다.

Claude는 `worker.claude.example.json`을 사용하며 Codex 인증이 필요 없다. 기본 engine이 생략된 과거 설정은 Codex로 유지한다. [팀원별 초기 설정](../../docs/bootstrap/automation-workers.md)에서 설치·가입·직접 로그인·preflight·단일 Worker 등록 순서를 따른다. 같은 개인 state_dir의 lock이 두 실행기의 중복 Worker를 막으므로 엔진 변경 전 자기 Worker를 중단한다.

고정 Worker는 PM 검토 main에서 `scripts/build_worker_runtime.py --output {저장소밖의새폴더}`, 보고 hook은 `scripts/build_worker_report_bundle.py --output {다른새폴더}`로 만든다. Worker는 worker/process/claude/isolation/artifacts manifest를 검사한다. 실제 출력의 `trusted_report_script`·`trusted_report_sha256`을 설정에 연결한다. hash 검사는 인증 격리와 별개다. PM은 모든 checkout 밖의 고정 코드·private 정책/설정/journal로 `scripts/automation_pm.py --config {외부pm.json} --preflight|--observe|--once`를 사용한다. `pm.example.json`은 OFF 정책 예시이며 deployment config가 아니다.
