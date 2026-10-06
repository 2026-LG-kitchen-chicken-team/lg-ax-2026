<!-- member-log:entry v1; generated navigation, original content below -->
원본: `docs/작업근거/정이량.md` · source commit `84844b86d4d90faf341c0b19ef7407be274b9d17`

원문 byte 구간: 79436..84072 · 원문 행: 289..310

[개인 목차](../README.md) · [원바이트 전체 원본](../archive/84844b86-original.md)

<!-- member-log:body:start -->
### 정이량-E020-AUTOPM-ISOLATION — 시작 근거

#### 실제 pilot 실행 복구 근거 (2026-10-05)

- PR79/main `f2cbf017835a22dc58eba866664df42ea3836307` 실제 병합·4개 CI, production 재배포/공식 스냅샷 승인과 모두 OFF를 확인했다. 작은 pilot은 P2-PM-003 아래 한 회귀 인수 단위이며 부모 완료가 아니다.
- 첫 실패: 모델24.609초/exit0 결과는 bwrap namespace 생성 거부·변경0이고 validator는 `/opt/uv-cache/sdists-v9/.git` permission denied/exit2다. private attempt1 checkpoint/결과/검사 로그와 blocked ACK·개인 OFF를 보존했다. 게시/병합 없음.
- 공식 [OpenAI 컨테이너 격리 안내](https://learn.chatgpt.com/docs/agent-approvals-security), 10/5 직접 조회: Docker namespace 제한으로 내부 sandbox가 불가할 때 외부 격리를 마련해 컨테이너 안에서 `--sandbox danger-full-access`를 사용하는 조건을 안내한다. Docker 경로만 적용하고 native는 유지한다. pinned CLI0.155.0의 실제 `exec --help`로 지원 모드를 확인했다. 모델 본인 인증·bridge 접근의 위험과 GitHub/PM/controller 인증 차단은 구분한다.
- 실제 uv 복구: image `sha256:76ed86b7e2a84169b14e6910b67d10a8453e0e58e53f8f2e9ef96e404df8d494`, validator의 `uv run --no-sync python -m unittest tests.test_contracts -v` 4개/exit0/1.781초. uid1000/read-only root/cap drop/no-new-privileges/network-none/workspace+artifacts만/AI와publisher 인증 없음, private HOME cache·고정 venv/offline 유지. private proof의 필요 관측만 인수한다.
- 새 회귀166개(skip4)·Ruff/변경 검사 성공, Windows OS 잠금 경쟁과 native sandbox 보존 포함. 실행기 복구 근거이며 네 PC 준비·제품 성능·참가작 완성·24시간 안정성 증거는 아니다.

#### 실제 경계·로그인·생성 근거 추가 (2026-10-05 07:27 KST)

- `isolation-canary.json`은 실제 Docker inspect/mount/user/caps/root/network 및 harmless canary 측정이다. model AI profile 접근과 validator zero-auth를 구분한다. publisher host 양성 대조만으로 실제 게시를 주장하지 않는다. selected image76ed86… 실제 build/context5파일 및 local engine29.6.2 확인. raw logs·readiness는 외부 private state에 남겼다.
- 새 profile의 실제 컨테이너 CLI 버전·login status를 확인하고 `automation_isolation.py verify`에서 canary와 own login을 함께 검사했다. 첫 로그인 timeout, browser 설정 승인, fresh device 재발급·완료를 보존한다. 인증 값/이메일/기기 코드는 docs에 복사하지 않았다.
- `isolated-generation.json`은 실제 Codex fresh readonly session의 wait 결과/usage/boundary/events hash다. input13727/output70; production OFF, mutation0. 모델/검사 파일 접근 경계와 실제 구독 생성은 입증하지만 Worker 게시·PM 병합·타 PC 준비·제품 Agent 수요/품질/최종 제출은 입증하지 않는다.
- 전체 unittest731(skip4), 최신 automation270(skip5), changed-code Ruff, agent rules byte일치/계약/phase2 validate/diff-check 통과. fixture/회귀와 actual canary/generation을 혼동하지 않는다. 후속 CI/head/merge/재배포/작은 완주 증거는 별도 추가한다.

- 관련 기록 정이량-20261005-007-AUTOPM-ISOLATION. 2026-10-05 KST main28d3eee/PM 계정/온라인 스냅샷/전원 OFF·큐0 직접 조회. 황대겸의 canary 접근 성공은 사용자 전달 보고이며 현재 Worker/process의 같은 사용자 실행과 일치한다. 그 PC의 직접 재현 증거로 가장하지 않는다.
- 기존 process.py Job Object/시간·중단 제한은 프로세스 종료 경계이며 OS 사용자 인증 파일 격리가 아니다. worker의 isolated_environment는 검사에도 AI home을 넣고 동일 worktree를 인증된 publisher로 commit한다. 이를 실제 실행 격리/zero-auth 검사/clean snapshot 게시로 변경한다.
- 공식 자료: https://docs.docker.com/engine/security/ · https://docs.docker.com/engine/storage/bind-mounts/ · https://learn.chatgpt.com/docs/non-interactive-mode · https://learn.chatgpt.com/docs/auth/ci-cd-auth. Docker 설정/마운트/daemon 제어가 격리 경계를 결정한다. Codex CLI 비대화형/구조화 출력과 지속 개인 인증은 독립 운영 루프/무제한 사용 보증이 아니다. API 자동 전환하지 않는다.
- 실제 Windows11 Home·Docker CLI29.6.2/desktop-linux, Ubuntu24.04·docker-desktop WSL 등록 확인. 최초 Docker Engine 연결 실패를 보존한다. 향후 버전/이미지 digest·actual canary·CLI·CI·PR·병합 증거를 아래에 추가한다.


<!-- member-log:body:end -->
