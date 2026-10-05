# 황대겸 Worker 시작·원본 readiness 인계

PM-20261005-CORE-START-R1을 직접 사용자 승인으로 진행한 이 PC의 준비/등록/연결 증거다. 제품 개발·게시·부모 Done 근거가 아니다.

- `readiness.json`: 기존 공식 verify가 새 DSW 계정으로 만든 무해한 canary·실제 컨테이너 로그인 원본. 비밀/메일/호스트 절대 경로가 없음을 검토한 후 byte 그대로 게시했다. 원 SHA256은 handoff.json에 고정했다. 당시 `automation_enabled=false`는 검증 시각의 값이며 현재 중앙 상태와 구분한다.
- 이 폴더의 `.gitattributes`는 readiness.json 한 파일의 Windows 줄바꿈을 원본 bytes로 보존한다. 다른 파일의 변환 규칙은 변경하지 않는다. Git blob의 SHA256을 원본과 대조한다.
- `handoff.json`: 고정 code/module/report hash·actual image·원 검사 시각·Limited 예약 preflight·Worker/PID/OS lock·현재 중앙 상태와 미완료 조건.
- `collector=trusted_pm`은 공식 helper의 출력 문자열이며 사람 PM의 수신·승인 증거가 아니다. PM은 원본 hash·실제 두 role의 image/canary를 확인하고 자기 private readiness/pin에 인수해야 한다.
- 중앙 팀/개인 ON은 PM이 전환했고 본인 AI는 변경하지 않았다. Worker가 준비된 뒤 큐가 비어 있어 첫 모델 개발·검사·제품 PR 시험은 아직 시작되지 않았다. 본인 AI는 임의 job/policy/capability를 만들지 않는다.
- 실제 원 파일·이전 인증/설정·중단 코어 브랜치는 private 영역에 보존한다. 로그인·경계 검사를 반복하지 않았고 예약 실행 권한의 preflight만 추가했다. 첫 등록 뒤 `.ps1` 반환값을 외부 실행 종료 코드로 오판한 시도는 등록 사실 재조회 후 정상 기동으로 수정했다.
- 예약 Worker는 같은 사용자가 로그인하고 PC/Docker가 실행 중일 때 동작한다. 기존 작업·웹 PR83과 병렬로 같은 제품 파일을 수정하지 않는다.
