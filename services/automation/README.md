# 승인 작업 자동화

[팀 운영과 ON/OFF](../../docs/pm/automation.md)를 먼저 읽는다. 중앙 서비스는 작업 데이터와 잠금을 관리하며 저장소 코드나 Issue 명령을 실행하지 않는다. Worker는 각자의 격리 환경·GitHub 인증과 선택한 Codex/Claude Code 로그인으로 실행한다. 신뢰된 bridge는 일반 검토 댓글과 운영 현황만 게시한다.

- `state.py`: 영구 큐·원자 배차·lease·경로/자원 잠금·OFF/STOP·PM 조정.
- `controller.py`: 인증·PM 운영자/Worker 분리·개인 가입·선택적 공유 모델.
- `worker.py` / `process.py`: 작업별 공간·상한/중단·실제 검사·불변 기록·별도 PR 게시.
- `claude.py`: 개인 claude.ai 인증·고정 CLI·restricted 파일 도구·구조화 최종 결과. 같은 Worker의 배차/중단/검사/게시/보고 경계를 사용한다.
- `github_bridge.py`: 고정 PR 읽기 검토 배정·head 재확인·중복 방지·Issue28 현황.
- `model_gateway.py` / `model_proxy.py`: 현재 LG Qwen 모델의 digest와 옵션을 검사하는 인증된 검증 경로. 임의 서버·모델 다운로드·GPU 제어는 제공하지 않는다.

로컬 개발 실행은 비공개 설정을 사용한다. 신규 초기화는 기존 상태를 덮어쓰지 않는다.

```powershell
uv run --no-sync python -X utf8 scripts/automation.py init
uv run --no-sync python -X utf8 -m services.automation.controller --config private/automation/controller.json --port 18871
uv run --no-sync python -X utf8 scripts/automation.py status
uv run --no-sync python -X utf8 -m unittest discover -s tests -p "test_automation*.py" -v
```

`worker.example.json`은 설치 전 예시이고 격리 확인은 기본 false다. 실제 절대 경로·개인 인증·고정 외부 보고 bundle을 준비한다. 운영자 토큰을 Worker에게 주지 않는다. 전용 실행 환경을 준비한 후 Windows 설치 script 또는 Linux user service를 사용한다. 이 예시를 추가한 것으로 서비스 설치·ON·인증을 완료했다고 보고하지 않는다.

Claude는 `worker.claude.example.json`을 사용하며 Codex 인증이 필요 없다. 기본 engine이 생략된 과거 설정은 Codex로 유지한다. [팀원별 초기 설정](../../docs/bootstrap/automation-workers.md)에서 설치·가입·직접 로그인·preflight·단일 Worker 등록 순서를 따른다. 같은 개인 state_dir의 lock이 두 실행기의 중복 Worker를 막으므로 엔진 변경 전 자기 Worker를 중단한다.

고정 자기보고 hook은 PM이 검토한 main에서 `scripts/build_worker_report_bundle.py --output {저장소밖의새폴더}`로 만든다. 반환된 `trusted_report_script`·`trusted_report_sha256`을 Worker 설정에 연결한다. 보고 스크립트·공통 검증 모듈·정책을 함께 해시 검사하며 팀원 브랜치의 보고 코드를 실행하지 않는다. 이는 파일 검증이며 운영 사용자 자격증명 격리를 대신하지 않는다.
