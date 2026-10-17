# KITCHEN AX 독립 보존 검사 근거

근거 ID: `신진하-E-20261015-KITCHEN-AX-DASHBOARD-SNAPSHOT` · 2026-10-15 KST

## 고정 출처

- 원본 소스 SHA: `f49db0e0146fd4d06937ae26063f77224f78cd67`.
- 공개 화면: https://kitchen-ax-factory-20261015.tlswlsgk7174.chatgpt.site/ · Site 버전 5.
- 보존 대상 기준 main SHA: `eab85d48385f965eef48c07a6cdd8f6fd9851c62`.
- [파일별 SHA-256·변환 내역](../../../../대시보드%20신진하/SNAPSHOT-MANIFEST.json).

## 실제 확인

- 기존 팀 clone을 수정하지 않고 현재 main에서 별도 sparse clone·새 브랜치를 만들었다. 해당 브랜치와 새 보존 폴더가 원격/기준 tree에 없음을 확인했다.
- GitHub 기존 Git 인증의 계정 `ginaginaring`과 대상 저장소 이름·비공개 상태·push 권한을 GitHub API로 확인했다. 인증정보는 파일이나 출력으로 남기지 않았다.
- 패키지 36파일·매니페스트 항목 35개를 파일 목록과 SHA-256으로 재검사했다. 팀 checkout에 복사한 뒤에도 35개 해시를 재검사했다.
- 원본 추적 소스 31개: 30개 바이트 동일, README 1개는 원문 suffix 보존. 기존 `.openai/hosting.json`은 바이트 동일한 비활성 참고 경로로 옮겼다.
- 활성 Site 설정·배포 Workflow·실제 업로드 자료·환경 비밀·SQLite DB·node_modules·dist가 패키지에 없다. README 상대 링크 5개가 존재하고 실행 명령은 독립 하위 폴더를 기준으로 한다.
- 이전 동일 소스 검증: JS 41개 PASS·빌드 PASS·데스크톱/모바일 기본과 선택 패널 및 Escape 복귀 확인. 이번 복사에서 새로 테스트/빌드한 것은 아니다. 팀 전체 검사와 PM 검수를 대신하지 않는다.

## 보존과 비수행

main, 보호 규칙, 배포, 운영 자동화, 팀 Task/Project 상태, 다른 담당자 코드·기록과 다른 저장소에는 쓰지 않는다. 브랜치 게시/PR 수신·CI·검수·병합은 각 실제 원격 근거로 구분한다. 기존 팀 Agent나 실제 CLI/LLM과 연결됐다고 주장하지 않는다.

[사용자 지시·작업 기록](../../../작업기록/신진하/2026-10-15/신진하-20261015-KITCHEN-AX-DASHBOARD-SNAPSHOT.md)
