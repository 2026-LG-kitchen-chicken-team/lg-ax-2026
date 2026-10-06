<!-- member-log:entry v1; generated navigation, original content below -->
원본: `docs/작업근거/정이량.md` · source commit `84844b86d4d90faf341c0b19ef7407be274b9d17`

원문 byte 구간: 85618..89802 · 원문 행: 318..340

[개인 목차](../README.md) · [원바이트 전체 원본](../archive/84844b86-original.md)

<!-- member-log:body:start -->
### 정이량-E019-CLAUDEWORKER — 공식 지원·현재 상태 조사

- 관련 기록: 정이량-20261005-006-CLAUDEWORKER. 확인일 2026-10-05 KST. 사용자 직접 지시와 현재 main/온라인 Project를 대조했다.
- [공식 CLI](https://code.claude.com/docs/en/cli-reference): print 모드·JSON Schema·stream-json·제한 도구·restricted/safe-mode·auth status를 제공한다. auth status의 configDirectory는 2.1.268 이상이다. CLI capability를 실제 검사하고 부족하면 중단한다.
- [비대화형](https://code.claude.com/docs/en/headless): 최종 result 이벤트의 structured_output을 읽고 성공/오류/턴 제한을 구분한다. bare 모드는 구독 OAuth를 읽지 않으므로 이 구독 Worker에 사용하지 않는다. 비용 필드는 추정값이며 실제 청구서가 아니다.
- [인증](https://code.claude.com/docs/en/authentication)·[환경변수](https://code.claude.com/docs/en/env-vars): CLAUDE_CONFIG_DIR의 개인 전용 로그인과 API/다른 provider를 구분한다. 직접 로그인하고 자격증명을 복제하지 않는다.
- [SDK와 구독 공식 정정](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan): 6/15 변경을 보류하여 현재 SDK/claude -p가 구독 사용량을 차감한다. 본문의 과거 월간 SDK 크레딧 표를 현행 정책으로 인용하지 않는다.
- [Pro/Max](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan): Claude/Code가 같은 사용량을 공유한다. API key 설정은 별도 API 과금 경로이므로 제거/거부한다. 계정에서 활성화한 추가 사용량 과금까지 Worker가 해제하는 것은 아니다.
- 조사 한계: 현재 PC에 Claude native CLI/전용 로그인은 아직 확인되지 않았다. 공식 지원·코드/fixture 검증과 실제 개인 인증/모델 실행을 구분하며 무한 사용·24시간 완주를 주장하지 않는다.

#### E019 구현·검사 추가 근거 (2026-10-05 06:25 KST)

- native 실제 증거: `evals/team-automation/20261005/claude-native-proof.json`, @anthropic-ai/claude-code-win32-x64@2.1.289·native SHA256·버전/전체 argv·제한 도구·빈 auth 거부·0토큰. CLI/auth 실패를 확인했으며 실제 구독 생성이나 개발 PR 완주 증거가 아니다. 패키지/로그/empty auth는 Git 제외 private/runtime에만 있다.
- 실제 검사: `uv run --no-sync python -X utf8 -m unittest discover -s tests -p test_automation_claude.py -v` 18성공; 자동화 discovery141(skip1)·전체 discovery635(skip1) 성공. full discovery 이후 추가한 runtime2는 targeted18/141에서 확인했다. scope·OFF·원본 결과 계약·API fallback 거부·버전 변경·최종 오류/중복·CLI 출력 비밀 가림·고정 외부 runtime 변조 거부·읽기 executor 수신 확인을 검사했다. 실행/구조 검사이고 실모델 성능 증거는 아니다.
- 변경5Python Ruff0·지침 byte일치·check_contracts PASS·phase2 validate valid=true. 전체 Ruff24기존 진단은 이번 변경 파일에 없고 해결 완료로 표현하지 않는다. remote CI/actual merge는 후속 실제 결과에 연결한다.
- 중앙 재조회에서 team off·개인 전원 false·공식 snapshot88e19c3를 확인했다. 서버 정책·배정/Done·역할·GPU·모델 서비스를 바꾸지 않았다. Claude CLI 선택이 공모전 참가작의 추가 제품 기능은 아니다.

#### E019 검수 정정·추가 경계

- 원 전체635에는 runtime2가 이미 포함돼 있었다. 앞 설명의 “전체 후 runtime2 추가”는 순서 오해로 정정한다. metadata preflight와 인증 실패 halt2개를 나중에 추가하여 최종 loader637/Claude20/자동화143이다. 실제 원격 실행은 최종 PR77 head와 CI 로그를 확인한다.
- metadata preflight는 false를 유지한 채 인증/연결만 검사하고 일반 Worker는 false/문자열 false를 거부한다. 로그인 만료 등 실패의 retained checkpoint/halt_worker=true를 검사해 다음 작업의 소모를 막는다. 통제된 단위/통합 검사이며 네 PC의 실제 로그인·개발 완주가 아니다.



<!-- member-log:body:end -->
