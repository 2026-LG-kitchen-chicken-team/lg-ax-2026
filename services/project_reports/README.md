# PM 관리 프로젝트 자기보고 서비스

확인일: 2026-10-04 KST. 협업의 전체 역할·기록·검수 흐름은 [팀 협업 체계](../../docs/협업체계.md)를 따른다.

팀원은 저장소의 자기 담당 이슈에 로그인 계정으로 구조화된 진행 보고를 남긴다. PM이 따로 배포한 읽기/검증/반영 서비스가 보고를 검사한 뒤 GitHub Project의 `Status`, `팀원 보고`, `최근 보고`, `다음 행동` 네 필드만 갱신한다. 팀원에게 Project Write 또는 PM 인증 토큰을 공유하지 않는다. 정식 `진행상태`·담당자·우선순위·기한·설정·완료 판정은 PM 흐름으로 유지한다.

## 구성

| 파일 | 역할 |
|---|---|
| `scripts/project_report.py` | 전체/담당별 온라인 상태 조회와 자기 보고 검증·미리보기·발송·수신 확인 |
| `scripts/project_report_common.py` | GitHub API, 보고 형식/계정/담당/버전/PR 검사, 네 필드 갱신 제한 |
| `harness/phase2/project-reports.policy.json` | 레포·Project·PM 계정·운영 Issue·작업별 담당/이슈/항목·접수 시작 시각·PM이 승인한 초기 스냅샷의 관리 원본 |
| `services/project_reports/worker.py` | PM 계정으로 새 보고 수집·원문 해시 기록·상태 반영·수신 확인·상태 저장 |
| `services/project_reports/lgax-project-reports.service` | 사용자 systemd 서비스, 45초 간격 수집·실패 후 재시작·전용 쓰기 경로 |

배포본은 `worker.py`, `project_report_common.py`, PM 검토한 `policy.json`을 함께 고정한다. 정책과 코드를 팀원 브랜치에서 자동으로 갱신하지 않는다. GitHub의 main에서는 JSON 작업 기록만 읽으며 그 코드·워크플로·모델을 실행하지 않는다. main의 변경값은 승인 대기 자료이며 공식 판단에는 PM 배포 정책의 승인 스냅샷과 실제 PM 동기화 승인을 사용한다. 보고 댓글도 실행 명령이 아닌 입력 데이터다.

## 공식 상태의 신뢰 경로

최초 공식 상태는 PM이 별도 검토·배포한 정책의 `approved_main_commit`·`approved_tasks`다. worker는 이를 전용 상태 파일에 보존한다. 이후 신뢰 스냅샷 갱신은 정책에 지정된 운영 Issue #28에 실제 PM 계정이 작성한, 편집되지 않은 `/lgax-sync` 댓글만 허용한다. 접수 시작 시각 이후의 새 댓글이어야 하며 JSON에는 `commit` 한 항목의 전체 40자리 SHA만 들어간다. worker가 조회한 정확한 현재 main SHA와 일치해야 한다.

```powershell
uv run python scripts/phase2.py validate
uv run python scripts/sync_github_phase2.py
uv run python scripts/sync_github_phase2.py --apply
```

마지막 적용 명령은 실제 PM 계정·현재 원격 main과 로컬 HEAD 일치·작업 JSON 미저장 변경 없음·하네스 검증을 확인한 뒤 공식 Project 필드와 `/lgax-sync` 승인 댓글을 게시한다. 미리보기는 변경하지 않는다. 팀원은 적용 명령을 실행하지 않는다. 수동으로 main JSON만 바꾸거나 자기보고를 제출해 Done·의존 해제·확장 채택을 승인할 수 없다. 서비스의 승인 접수도 AI/사람이 실제 성능을 다시 검수했다는 뜻은 아니며 PM의 연결된 실행·검수 근거를 읽는다.

PM의 승인 댓글 형식은 다음과 같다. 설명용 SHA 문자열은 실제 전체 40자리 값으로 대체한다.

````text
/lgax-sync
```json
{"commit":"정확한_현재_main의_전체40자리_SHA"}
```
````

worker는 공개 main과 신뢰 스냅샷의 차이를 `unapproved_state_changes`에 표시하고, 승인되지 않은 main 변경을 공식 상태에 적용하지 않는다.

## 팀원 사용

```powershell
uv run python scripts/project_report.py status
uv run python scripts/project_report.py status --member 신진하
uv run python scripts/project_report.py report P2-DATA-001 --status doing --summary "세 제품의 문서·모델·버전 연결을 작성 중" --next-action "제품별 근거 ID와 원문 위치를 검사" --send --wait 60
```

현재 GitHub CLI 인증 계정과 해당 작업의 정책상 담당 계정이 같아야 한다. 자신의 로그·근거를 commit·push한 뒤 발송한다. CLI가 기본 생성하는 링크는 현재 HEAD의 `docs/작업기록/{성명}.md`와 `docs/작업근거/{성명}.md`이며 GitHub에서 읽을 수 있어야 한다. 두 링크는 같은 전체 40자리 commit SHA를 사용한다. `--log-url`, `--evidence-url`로 같은 레포의 자기 파일에 해당하는 고정 commit 링크를 명시할 수도 있다.

`--send`가 없으면 사전 검사와 댓글 원문 확인만 수행한다. `--wait 60`은 최대 60초 동안 PM 계정 수신 확인을 조회한다. 발송 응답의 `sent`와 보드 반영의 `project_updated`는 다른 값이다. 대기 종료 후 반영을 확인하지 못하면 원 댓글 URL을 보존하고 수신 확인/Project를 재조회한다. 실패했다고 무조건 같은 보고를 재발송하지 않는다.

## 접수 형식과 검사

댓글 원문은 `/lgax-report` 다음 줄에 JSON 코드블록 하나만 둔다. 직접 작성하는 경우도 CLI와 동일한 검사를 적용한다.

````text
/lgax-report
```json
{
  "task_id": "P2-DATA-001",
  "status": "doing",
  "summary": "실제 진행 요약",
  "next_action": "다음 구체 행동",
  "log_url": "https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/전체40자리commit/docs/작업기록/신진하.md",
  "evidence_url": "https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/blob/전체40자리commit/docs/작업근거/신진하.md"
}
```
````

위 예시의 commit 문구는 실제 전체 commit SHA로 바꾼다. 형식을 직접 조립하기보다 CLI를 사용하면 입력 검사와 링크 생성을 함께 수행한다.

- 필수: `task_id`, `status`, `summary`, `next_action`, `log_url`, `evidence_url`.
- 선택: `reason`, `pr_url`. 추가 필드·중복 키·빈 문자열·과도한 길이·일부 연락처/자격증명 패턴은 거절한다. 자동 검사가 모든 개인정보를 탐지하는 것은 아니므로 작성 전 직접 가린다.
- 상태: `doing`, `blocked`, `review_requested`. blocked는 `reason`, 검수 요청은 `pr_url`이 필요하다. Done·PM 승인·병합·통합 완료는 접수 상태가 아니다.
- 담당: 정책상 계정이 해당 열린 이슈의 현재 담당자여야 한다. 다른 담당자의 보고나 다른 이슈에 쓴 보고는 거절한다.
- 의존: 선행 작업 대기 중에도 부분 개발·부분 PR을 보고할 수 있다. 접수 기록과 상태 조회에 미완료 의존을 남기며, 보고만으로 정식 완료나 다음 작업의 의존을 해제하지 않는다. PM이 채택하지 않은 확장 작업은 접수하지 않는다.
- 버전: 자기 기록/근거를 GitHub에서 실제 읽고 원문 해시·git blob을 기록한다. 파일 존재 검사는 그 안의 주장이나 모델 품질을 독립 검증하지 않는다.
- PR: 같은 레포·보고자의 PR이어야 한다. 검수 요청은 main 대상의 열린 비초안 PR이며 기록 commit과 현재 PR head가 정확히 같아야 한다.
- 정식 판정 보호: PM 승인·병합·통합 확인·완료 상태의 작업을 자기보고로 덮어쓸 수 없다. 이후 PM이 승인한 스냅샷의 공식 기록은 이전 자기보고보다 우선한다. 승인 없는 main 수정은 이 우선권을 갖지 않는다.
- 수정: 편집된 보고는 거절한다. 수정 내용은 새 댓글로 보고한다. 이미 처리한 댓글 ID는 다시 적용하지 않는다.

반영 성공 후 `LGAX-RECEIPT {댓글ID} ACCEPTED`, 거절이면 `REJECTED` 수신 확인을 PM 계정으로 남긴다. 성공 수신 확인은 계정·담당·버전·형식 조건을 통과해 보드에 반영했다는 뜻이다. 실제 실행 성공·PM 승인·병합·전체 완료를 뜻하지 않는다. 기존 접수 댓글을 나중에 수정해도 저장된 접수 원문 해시는 유지한다.

## 보드 조회의 해석

상태 조회는 온라인 Project와 GitHub main의 JSON 작업 기록을 읽고 조회 시각·main commit을 반환한다. `formal_harness_status`는 main 파일에 기록된 값이며 그 값만으로 PM 승인 여부를 입증하지 않는다. `project_formal_status`, 단순 `board_status`, 자기보고 상태·보고 나이·24시간 이상 오래됨·정식 표시 불일치·의존 작업·착수 가능 여부·근거를 함께 보여준다. `may_start`는 main·Project 공식 표시 일치와 선행 작업의 양쪽 Done을 요구하는 보조 표시다. 실제 착수/완료 판단은 PM 배정·신뢰 스냅샷·승인 근거와 대조한다.

보고 없음은 실제 진행 미확인이다. 오래된 보고나 정식 표시 불일치가 있으면 최근 개인 기록·이슈·PR·PM 승인과 main 하네스를 확인한다. PM이 승인한 후속 기록으로 자기보고가 오래됐으면 Project 최근 보고에 역사 보고로 남기고 다음 행동은 최신 PM 지시 확인으로 바뀐다. 이력은 삭제하지 않는다. 서비스는 정식 `진행상태`의 잘못된 값을 직접 고치지 않으며 PM이 원인을 확인한다. CLI의 사전 검사 통과나 댓글 발송만으로 접수를 확정하지 않고 worker의 ACCEPTED 수신 확인을 확인한다.

## PM 배포·운영

사용자 서비스의 기본 전용 경로는 다음과 같다. `%h`는 서비스 계정의 홈이며 실제 계정·호스트 확인은 PM 실행 증빙을 따른다.

| 경로 | 내용 |
|---|---|
| `%h/.local/share/lgax-project-reports/` | PM이 검토해 고정한 배포 코드·공통 모듈·정책·배포 버전 기록 |
| `%h/.config/lgax-project-reports/token` | PM GitHub 인증 토큰, 서비스 사용자 소유·0600. 출력·Git·이슈·Notion에 기록하지 않음 |
| `%h/.local/state/lgax-project-reports/state.json` | 승인 스냅샷·승인 commit/출처·처리 댓글 ID·원문 해시·자기보고·수신 확인·마지막 성공 시각 |
| `%h/.local/state/lgax-project-reports/health.json` | 마지막 성공·공개/승인 commit·미승인 차이·접수/거절 수·필드 갱신 요약 |
| `%h/.local/state/lgax-project-reports/worker.lock` | 같은 작업 공간의 중복 수집 프로세스 방지 |

Project의 네 필드는 PM이 미리 생성한다. `팀원 보고` 선택값은 Doing / Blocked / Review requested다. Project 항목 ID가 정책과 달라졌거나 정책상 담당과 main 작업 소유자가 다르면 임의 갱신하지 않고 PM이 조정한다. 새 작업·계정·이슈 추가는 정책 원본과 배포 정책을 PM이 함께 검토해 변경한다.

```sh
systemctl --user status lgax-project-reports.service
systemctl --user restart lgax-project-reports.service
journalctl --user -u lgax-project-reports.service --since today
```

서비스는 기본 45초마다 수집하며 GPU·모델·외부 수신 포트를 사용하지 않는다. GitHub API로 조회·갱신하는 단방향 작업이다. 에러 로그에는 인증 토큰·원 댓글·API 원문을 출력하지 않고 에러 종류만 남긴다. 상세 실패는 비공개 증빙과 원본 이슈에서 대조한다. 상태 기록을 먼저 저장하고 필드별 갱신을 비교해 재시도하며, 수신 확인은 보드 반영 뒤 작성한다. 일시적인 네트워크/권한 오류를 잘못된 팀원 보고로 판정하지 않는다.

인증 토큰은 GitHub Actions에 배포하지 않는다. 현재 개인 소유 비공개 저장소에서 사용 가능한 브랜치 보호 여부와 일반 팀원 Write를 검토한 뒤 PM이 독립된 서비스 배포 경로를 관리한다. 서비스의 제한은 PM 배포 코드/정책을 통한 API 호출 범위이며 GitHub 자체가 토큰에 필드 단위 권한을 부여하는 구조가 아니다. 토큰 접근이 가능한 운영자는 별도의 관리 권한을 가진다는 점을 구분한다.

## PM의 새 배정과 실제 Gmail 발송

진행 자기보고와 PM 새 배정 메일은 서로 다른 경로다. PM AI가 `scripts/assign_task.py`로 확정 배정의 공용 JSON·이슈 댓글·비공개 발송 대기를 만든 뒤 연결된 Gmail 도구로 실제 전송한다. Gmail Sent 메타데이터의 message ID·발신자·수신자·제목·발송 관찰을 대조한 수신증으로 기록한다. 준비 명령은 메일을 보내지 않는다. 같은 배정 ID의 기존 전송 기록을 확인해 중복 발송을 막는다. 이 서비스가 상태 댓글을 읽었다는 이유만으로 이메일을 보내거나 팀원 수신을 주장하지 않는다. 사람이 GitHub에서 임의로 배정을 바꾼 모든 경우를 메일 daemon이 감시하는 구조가 아니다.

PM은 등록된 작업에 `PM-YYYYMMDD-고유접미사` 배정 ID를 만들고 입력 JSON을 준비한다. 필수 항목은 `assignment_id`, `task_id`, `purpose`, `instructions`(목록), `acceptance`(목록), `next_action`이다. 선택 항목은 `deadline`, `source`, `requirement_ids`다. 수신자 이름·주소·확인 출처/일자와 PM 발신 주소는 비공개 `private/team-notifications/contacts.json`의 검증된 값으로 관리한다. 아래 경로와 `PM-20261004-EXAMPLE`은 설명용이며 실제 배정 입력/ID로 바꾼다.

```powershell
uv run python scripts/assign_task.py prepare private/team-notifications/assignment-input.json
uv run python scripts/assign_task.py prepare private/team-notifications/assignment-input.json --apply
uv run python scripts/assign_task.py sending PM-20261004-EXAMPLE
```

`prepare --apply`는 배정 Issue 댓글, `docs/pm/assignments/{배정ID}.json`, `private/team-notifications/outbox/{배정ID}.json`을 만들고 PM 전용 `최근 배정`·`메일 안내`만 갱신한다. 첫 미리보기는 외부 변경 없이 검증한다. `sending`을 기록한 뒤 PM AI가 연결된 Gmail 도구로 outbox의 실제 수신자·제목·본문을 보내고 보낸편지함을 확인한다. `sent`·`sending`·`unknown` 기록이 이미 있으면 보내기 전에 기존 발송을 대조한다.

실제 Gmail 결과와 Sent 조회를 비공개 수신증에 기록한다. 항목은 `assignment_id`, `message_id`, `source`(`Gmail send_email result` 또는 `Gmail Sent reconciliation`), `recipient_email`, `sender_email`, `subject`, `sent_observed: true`다. 실제 outbox·검증된 PM 발신자와 일치해야 한다. 주소/원본 수신증은 private 밖에 복사하지 않는다.

```powershell
uv run python scripts/assign_task.py sent PM-20261004-EXAMPLE --receipt-file private/team-notifications/receipts/PM-20261004-EXAMPLE.json
```

이 명령은 비공개 outbox의 발송 상태와 공개 `docs/pm/assignments/{배정ID}.notification.json`, Issue의 발송 확인, PM 전용 `메일 안내`를 갱신한다. 공개 기록에는 수신자 주소·메일 본문을 넣지 않는다. 실제 발송은 수신자 열람·작업 착수와 다르다. 공용 배정/발송 기록은 팀원이 읽을 수 있도록 commit·push/PR로 공유하되 원본 입력과 이미 생성된 배정 JSON을 혼동하지 않는다.

수신자 주소·발송 대기·전송 증빙은 Git/Project/일반 docs에서 제외한다. 서버에 상시 Gmail 인증 토큰이나 발송 자격증명을 배포하지 않는다. 실제 메일 사용 명령과 발송 확인은 PM 운영 문서와 최신 근거를 따른다.

## 실제 검증·배포 상태

2026-10-04 PM 전용 서비스의 실제 배포·활성·45초 수집·재시작 후 승인/처리 상태 보존을 확인했다. [배포 증거](../../evals/team-coordination/20261004/service-deployment.json)를 따른다. 실제 보고 접수/거절·메일 발송은 별도 실행 증거로 확인하며 배포 성공만으로 수신·참가작 완료를 판정하지 않는다.

구현 파일과 절차 설명은 서비스 운영 성공 증거와 다르다. 배포본 버전/해시·서비스 활성 여부·실제 보고의 접수/거절·네 필드 변화·PM 정식 필드 보존·재시작 재처리 방지·토큰 가림은 최신 정이량 기록과 연결된 실행 증빙으로 확인한다. 실제 팀원 계정의 보고와 PM 계정의 자체 시험도 구분한다. 팀원 계정 로그인이 없으면 실제 그 팀원의 접수까지 시험했다고 보고하지 않는다.
