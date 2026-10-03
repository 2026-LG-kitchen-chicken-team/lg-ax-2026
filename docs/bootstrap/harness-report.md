# Phase2 하네스 구축·검증·독립 검토 기록

확인일: 2026-10-04 KST. 수행자: PM 정이량의 초기 설정 지시를 수행한 Codex 하네스 담당. 다른 세 팀원이 이 작업을 수행한 것으로 기록하지 않았다.

## 수행한 범위

- `scripts/phase2.py`: 담당별 상태·다음 작업·작업 패킷·착수/차단·개별 검증·PM 검수·실제 Git commit 확인·병합 후 통합 검증·PM 명시 완료·요구 충족·체크 등록·gate 명령.
- `harness/phase2/`: 원안 R01~R28·평가 E01~E03 총 31개 요구, 4명 역할·21개 작업, 19개 체크, 공식/신청 PDF 해시, 모델 버전 목록, 기존 phase1 보존 lock, 실제 GitHub Issue/Project 연결.
- `.github/`: 작업·계약·오류·실험·제출 Issue Forms, PR 검증 양식, PM CODEOWNERS, Python 3.11/uv·계약·회귀·stdio MCP·Node22 웹 시험/빌드 CI.
- `tests/test_phase2.py`: 최종 24개 격리 시험. Windows 파일 읽기의 UTF-8을 명시했고, 잘못된 JSON 증거와 PM 미채택 확장의 자동 실행도 거부한다.
- 원래 AtoZ JSON·state·실행 결과 12개 파일을 수정하지 않고 보존했다. 과거 `ax_workflow validate`의 stale 9단계를 명시했다. 과거 의존 해시를 새 문서 해시로 바꾸어 완료로 위장하지 않았다.

## 실제 확인한 결과와 근거

실행 출력과 JSON 근거는 `harness/phase2/runs/bootstrap-local-20261004/`에 있다. 검토에서 발견한 core의 버전 검사가 수정된 뒤 b run, 확장 채택 gate와 지침 일치 검사 후 c run, Git과 동일한 LF 형식 및 dataset manifest 해시 확인 후 **최종 e run**에 새 실행 결과를 기록했다. d run의 실제 해시 불일치 실패도 보존했다. 이전 근거는 보존했다. 출력은 명령·종료 코드·stdout/stderr를 포함하며 JSON은 실제 코드·입력/계약·출력의 SHA256을 갖는다. 최종 결과에는 코드·시험·의존성 23개 파일 해시를 고정했다.

| 검사 | 실제 결과 | 근거 |
|---|---|---|
| 전체 Python 시험 | 최초 91개, 버전혼입 회귀 후 92개, 최종 확장 채택 회귀 포함 **93개 PASS**; phase2 24개 | 각 run의 `unittest.txt` |
| 공통 JSON Schema·자료·요청·응답 | PASS | `contracts.txt` |
| phase2 기록 무결성 | PASS | `phase2-validate.txt` |
| 실제 로컬 stdio MCP 초기화·도구 발견·호출 | PASS | `mcp-stdio.txt` |
| 요구·담당·Ready·실제 Issue 연결 | 31개 요구·21개 작업·4명 모두 착수 가능 작업 확인 | `backlog-check.txt` |
| 변경 파일 공백 오류 | `git diff --check` PASS | 이 세션 실제 실행 결과 |

`framework_contracts_valid`, `framework_backlogs_ready`, `local_mcp_smoke`를 실제 근거로 등록했고 이후 `phase2 validate`도 통과했다. 근거 생성 중 존재하지 않는 `data/demo/bootstrap.json` 경로로 메타데이터 생성이 한 번 실패했다. 실제 입력 `data/demo/dataset.json`·`manifest.json` 경로로 수정했고 미완성 근거를 체크로 등록하지 않았다.

이 결과는 하네스·계약·개발 기반 검증이다. 상품기획 Agent 완성, 실모델 품질, 수요, 2차 접수, 사람의 PM 승인·실제 병합 완료를 뜻하지 않는다. 21개 task의 `done`은 0개, 31개 요구의 `verified`도 0개로 유지했다. 개인 `finish`는 `individual_verified`까지만 진행한다. PM 검토·실제 commit/PR·병합 commit의 통합 결과·정확한 결과 버전에 대한 명시 완료 없이는 `done`이 될 수 없다.

## 남아 있는 gate

- `framework_rules_synced`: 최종 root AGENTS.md/CLAUDE.md의 전체 내용·LF 바이트 일치를 실제 검사하고 e run의 파일 해시·출력으로 등록했다.
- `framework_ci_configured`: 워크플로 파일은 구축했으나 이 체크 계약은 **GitHub CI 실제 통과**이다. 로컬 시험으로 대신 PASS 처리하지 않았다. 첫 PR/실제 GitHub 실행 URL과 결과가 필요하다.
- `setup_external`: 실제 서버·모델·ChatGPT·Claude의 증빙은 root/모델 담당이 수집·등록한다. root가 공개 MCP SDK 호출 성공을 보고했으나 공개 SDK 성공과 실제 두 서비스 UI 호출은 별개다.
- 참가작 integration/evaluation/release/submission은 실제 구현·독립 사례·비교 평가·깨끗한 환경 재현·제출 증거를 충족할 때 진행한다. 정확한 10/20 제출 시각/경로는 미확정으로 보존했다.

한 구성 요소가 통과해도 전체 setup으로 바꾸지 않는다. 소스 파일이 변경되면 해당 현재 파일 해시 근거는 stale이 되므로 재검증한다. 역사 근거를 고정하려면 실제 commit의 `git_commit`/파일 해시를 사용한다. `--actor`는 선언된 수행자이며 계정 인증을 대체하지 않는다.

## 독립 PM 검토: root에 전달한 수정 사항

`docs/bootstrap/README.md`, `scripts/bootstrap_github.py`, 새 core/API/MCP 및 웹을 읽고 다음 사항을 전달했다. 아래 파일들은 하네스 담당이 대신 수정하지 않았다.

1. `docs/bootstrap/README.md`의 미구현 분석 경로가 `/api/analysis`로 적혀 있지만 실제 API·웹은 `/api/planning-requests`를 사용한다. 실행 안내 경로를 일치시켜야 한다.
2. `scripts/bootstrap_github.py`는 모든 Project 진행 상태를 Ready로 표시한다. 의존 task가 미완료인 pending 작업도 Ready가 되고 재실행하면 기존 Doing/Done과 증빙 필드를 초기값으로 덮을 수 있다. 처음 생성한 항목과 기존 진행 항목을 구분하고 로컬 상태·의존 상태를 반영해야 한다.
3. `packages/core/src/lgax_core/store.py`의 evidence→feature 검사가 모델 ID만 비교했다. 기존 manual을 새 ID/source ID로 복제하고 document_version만 다른 값으로 설정한 메모리 데이터에 같은 FEATURE-001을 붙이면 DemoStore가 허용하고 조회 결과에 서로 다른 버전이 연결됐다. 재현은 복사한 메모리 자료에서만 수행했고 저장소 자료는 변경하지 않았다. 웹 담당이 root 검토 지시에 따라 버전 일치 검사와 회귀 시험을 추가했다. 하네스는 기존 code hash의 stale을 정상 검출했고 새 stdio MCP·전체 92개 시험 근거로 체크를 갱신한 후 다시 validate PASS를 확인했다.

root가 문서 경로와 bootstrap 재실행 보존을 수정하고 명시적 Project 동기화 스크립트를 추가했다. 세 지적과 확장의 PM 채택 gate를 재검토한 판정은 [독립 AI PM 검토](pm-review.md)에 있다. 이는 사람의 PM 승인이 아니다.

현재 웹은 원문 조회·모델별 필터·요청 입력과 명시적 미구현 상태를 제공하며 가짜 콘셉트 성공을 반환하지 않는다. MCP는 읽기 합성 자료 3도구를 제공하며 모델 실행·개인자료·서버 조작 도구를 노출하지 않는다. 이는 현재 준비 단계에 맞는 범위다. 실제 호스트/CI 증빙은 해당 담당자가 별도 gate로 연결한다.
