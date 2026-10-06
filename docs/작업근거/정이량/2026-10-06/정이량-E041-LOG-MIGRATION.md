# 정이량-E041-LOG-MIGRATION — 원문 손실 없는 기록 이관 검증

- 확인일: 2026-10-06 KST.
- 원본: Git commit `84844b86d4d90faf341c0b19ef7407be274b9d17`의 `docs/작업기록/{성명}.md`·`docs/작업근거/{성명}.md` 8파일과 기존 세션 28파일.
- 초기 측정: 누적 818,663바이트 + 세션 199,496바이트 = 1,018,159바이트. 누적 상대 Markdown 링크114개 + 세션14개 = 128개. 현재 대상 경로 누락0건.
- 검사 조건: trusted pure stdlib metadata 도구만 PM host에서 실행한다. 제품 코드/모델/API 호출 및 arbitrary repository 테스트는 실행하지 않는다. 제품 회귀 검사는 GitHub CI의 자격증명 없는 테스트 단계에서 확인한다.
- 보존 대상: 지시 원문·AI 해석·실제 수행·검증·실패/보류·재개 요약·ID 중복·기존 heading/anchor·상대 URL 목적지·과거 고정 commit 근거·세션 원 byte. 과거 원본 JSON/receipt와 해시를 이관 편의로 고치지 않는다.
- 계획된 검증: source byte SHA·연속 slice coverage·URL edit 역변환/원본 재구성·rendered SHA·원 heading 순서·원 세션 SHA·모든 상대 링크 대상·개인/호환index 경로.
- 제한: 문서 이관과 도구 검사 성공은 팀원의 실행 진실성·Agent 모델 품질·참가작 완료 증거가 아니다. 현재 보고 서비스는 새 nested raw URL을 직접 받지 않으므로 root 호환 목차 경로를 계속 사용한다. 기존 자동Worker writer·배포 pin은 변경하지 않는다.

## 실제 검사와 범위

- `python scripts/migrate_member_logs.py migrate --source-commit 84844b86d4d90faf341c0b19ef7407be274b9d17 --apply`: applied_and_verified, source_git_verified true, source_files8/sections231/session_files28/body_bytes818663/relative_links128.
- `python scripts/migrate_member_logs.py --verify`: 동일 결과. Git 원blob8·원세션28목록/byte와 manifest/snapshot/역변환을 함께 확인한다. [원본문manifest](../../../작업기록/이관/20261006/manifest.json), [이관 안내](../../../작업기록/이관/20261006/README.md).
- trusted metadata fixture: 최종29tests 실패0. 원 heading495개(모든 실제 heading level)의 순서/문구/레벨이 root 호환 목차와 동일하다. 기존 source selffragment0, 상대 링크128(본문114+세션14)의 대상 누락0.
- 별도 감사: 새 개인README8·호환8·이관안내·공통지침·PM새2기록 등26문서의 실제 상대Markdown링크1,071개 모두 존재한다. 새 migrationmodule을 import하지 않고 Gitblob와 byte범위/가역 URL edits를 독립 확인했다. 원snapshot8/818663 + 원session28/199496 = 1018159바이트를 보존했다.
- 작성자 marker8README 각1쌍·marker제외 source-derivedREADME SHA일치·타팀원6block빈값. 과거 source-derived 원문을 수정하거나 다른팀원의 최신성과를 새로 만들어 넣지 않았다.
- AGENTS/CLAUDE byte동일, SHA256 `109afcdfca1e09bee98e65fc26f3df9d254e6faddc81766138742200855ee940`. bootstrap변경은 안내문자열이며 compile-only 성공. git diff --check의 generated indexEOF8건을singleLF로교정후통과, 원본문변경0이다.
- 최초metadatahelper는 검토된sourcepin과현재branch의bootstrap/phase2문구가달라거절했다. 기존loader/pin·server배포를고치지않고 immutable Git metadata source로 별도 JSON검증하며 실제제품회귀는 원격CI로확인한다. 원거절과후속검사는별개로보존한다.
- 보고/인증/배포코드·automationwriter/session경로·중앙ON/OFF·작업완료상태·원비용변경0, 모델/API호출0. 실제 PR/main·CI 및 노션 succeeded/readback은 고정 운영 Issue28의 후속 checkpoint에 연결한다.
