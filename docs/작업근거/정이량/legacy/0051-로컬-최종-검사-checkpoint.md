<!-- member-log:entry v1; generated navigation, original content below -->
원본: `docs/작업근거/정이량.md` · source commit `84844b86d4d90faf341c0b19ef7407be274b9d17`

원문 byte 구간: 144026..147487 · 원문 행: 610..626

[개인 목차](../README.md) · [원바이트 전체 원본](../archive/84844b86-original.md)

<!-- member-log:body:start -->
## 로컬 최종 검사 checkpoint

코드 `921e8ff`에서 0후보 사유를 API/웹 snapshot과 JSON/Markdown 내보내기에 별도 보존하고 정상0후보를 unresolved로 잘못 분류하지 않게 고쳤다. 웹 사유 삭제/변조·사본 불변 회귀와 빈 trace 실패 저장을 포함했다. 이전 전체 Python373은 b1f9bbd checkpoint이며, 변경 뒤 workspace33·웹189(옵트인4 skip)·타입/빌드·변경 Python Ruff를 post-fix-checks.json에 기록했다. skip4는 실서버/실모델 환경을 기본 CI에서 호출하지 않는 명시적 opt-in이며 실제 별도 TypeScript HTTP/모델1검사는 workspace-live 근거다. 브라우저 E2E·모든 Python 최종 코드는 원격 PR/main CI로 추가 확인한다. 보호 규칙을 낮추지 않는다.

세 후속 배정은 실제 Issue 댓글·Project 최근배정에 prepared로 등록했다. 황대겸 CORE002-SEMANTIC-REVIEW, 최길웅 WEB003-LIVE-RESULTS, 신진하 DATA001-PLANNING-SCOPE. 주소/outbox는 private이며 Gmail 실제 발송은 다음 checkpoint에서 확인한다.

### PROJECTMOVE/E015 실행 checkpoint — 공유 전

- 실제 행위: 조직 Project1 생성·기존26이슈 재사용,25필드/옵션·238입력값·26목표일·순서/archived·이슈관계/linkedPR 대조. 구조 복사에서 항목이0개인 것을 확인해 별도 이관했다. 처음 Title 내장값은 쓰기 불가로 실패했고 내장 필드는 같은 이슈에서 조회하도록 고쳐 재조회·idempotent 재실행했다. GraphQL node limit은 pullRequests 연결 수를20으로 낮추고 페이지 누락 검사로 해결했다. 조회 실패를 성공으로 덮어쓰지 않았다.
- UI: source3Read, targetPMAdmin/3Read 및 조직 기본Write를Read로 낮췄다. 기본 저장소 선택/저장/재조회 성공. 보기10열/필터/그룹/정렬 및6자동화의 원본·복사본 조건/선택Status를 대조했다. 내부 보드 변경 이력/Insights는 새ID로 재생성하지 않고 원본에 보존한다. 개인보드 삭제 없음.
- 서비스: LG전용 worker만 잠시 중지→원본 최종snapshot→정책/코드manifest 전환→start 및 fresh health 확인. trusted_commit/seen_count/latest_count 보존. 기존token·승인수신증·GPU/다른서비스 변경 없음. `evals/project-migration/20261005/service-cutover.json` 참조. Python운영helper에 paramiko가 없어 해당 로컬venv에 공식패키지를 설치했으며 lockfile/제품의존 변경 없음.
- 코드: Project조직 소유자와 실제PM계정 분리, 적용 전 PM인증 유지. 새8회귀 및 기존검사 수행. github/state/policy/활성 README/지침 링크 변경. AGENTS/CLAUDE 동일. 상세개인 원본과 과거URL은 보존한다.
- 메일: 신규CORE/WEB/DATA 배정3건 모두 actual Gmail send→Sent label·From/To/Subject 대조→private원본수신증/publicnotification 기록→새Project mail SENT 반영. 미발송outbox 링크만 변경, 이전Sent원문 불변. 수신자의 열람·작업착수는 주장하지 않는다.
- PR58 실제병합6b9dbe9/CI4PASS; sourcePR53 e423f95/54 20e03ce를 다시조회한 뒤 인수PR58 링크로 닫았다. Draft55/56/57은후속검수대기. 실제 모델 조건위반은 E014 반대근거를 유지한다.
- 다음: 이관PR원격CI·관리자squash병합→정확한main공식sync ACCEPTED→새보드/서비스/메일/Notion 재조회 및 종료기록. 완료 전 그 단계는 미완료로 유지한다.



<!-- member-log:body:end -->
