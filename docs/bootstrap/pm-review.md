# 2차 개발 기반 독립 AI 검토

확인일: 2026-10-04 KST. 검토자: Codex 하네스 담당 AI. 판정: **현재 개발 기반을 이어서 사용하는 데 적합**. 사람인 PM 정이량의 직접 승인·GitHub 병합·참가작 완성 판정과 구분한다. 이 문서로 task를 `pm_approved` 또는 `done`으로 변경하지 않았다.

## 검토 범위와 수정 확인

root README·AGENTS/CLAUDE·인수인계·체크리스트·공식 요건·개발 시작 안내, `scripts/bootstrap_github.py`, `scripts/sync_github_phase2.py`, 현재 core/API/MCP/웹과 phase2를 읽었다.

| 이전 지적 | 최신 확인 | 판정 |
|---|---|---|
| 안내의 `/api/analysis`가 실제 경로와 불일치 | 안내·API·웹 모두 `/api/planning-requests`, 명시적인 501 `NOT_IMPLEMENTED` | 해결 |
| 모든 Project 작업을 Ready로 표시하고 bootstrap 재실행이 진행·근거를 덮음 | 기존 Issue는 본문/검수/근거 PATCH 없이 보존. 초기 상태/증거/우선순위 설정은 새 Project 생성 때만 실행. 별도 명시 동기화는 pending→Deferred, ready→Ready, Doing/PM 검수/병합/통합/Done을 실제 로컬 단계에 맞춤 | 해결 |
| 새 문서 근거가 다른 버전 기능을 참조해도 허용 | core가 evidence→feature 모델·문서 버전을 함께 검사. 해당 실패 재현에 대한 회귀 시험 포함 | 해결 |
| 제안 확장이 의존 완료만으로 실행 목록에 들어갈 수 있음 | 제안 2개에 `adoption_required: true`, `adoption: null`. PM의 실제 지시 출처/발췌·task ID·명시 채택 근거 전에는 next/start/finish/검수/완료 비활성 | 해결 |

PM은 실제 추가 배정 시 `phase2.py adopt`로 채택 근거를 기록한다. 이 명령은 선언된 담당자 기록이며 인간의 결정을 대신 만들어내거나 계정을 인증하지 않는다. 이번 검토에서 두 제안은 채택하지 않았다.

## 실제 검사와 근거

최종 실행 근거는 `harness/phase2/runs/bootstrap-local-20261004e/`에 보존했다. 지침·자료·계약을 Git과 동일한 LF 형식으로 맞춘 후 실제 검사를 재실행했다.

- 전체 Python **93개 PASS**, phase2 **24개** 포함. 제안이 의존 완료 후에도 비활성이고 PM 외에는 채택할 수 없으며 실제 채택 근거 후에만 Ready가 되는 격리 회귀 시험을 추가했다.
- 공통 JSON Schema·데이터·입출력 계약 검사 PASS.
- 실제 로컬 stdio MCP initialize·도구 목록·도구 호출 PASS. 합성자료 입력임을 보존했다.
- 최신 AGENTS.md와 CLAUDE.md의 **전체 바이트 동일** PASS.
- 31개 요구·21개 실제 Issue 연결·4명별 필수 Ready 작업·제안 2개 비활성 상태 확인.
- 공식 2차 PDF와 최신 황대겸 팀장 명의 신청 PDF의 현재 SHA256이 `sources.lock.json`과 일치. 2차 안내·팀장 변경 문서가 같은 원본 경로를 가리킴. 10/20 일자와 정확한 시각/경로 미확정 상태도 공식 안내 요약과 일치.
- 요구 추출에 사용한 전략 문서는 역할/동일 지침 안내 갱신으로 전체 해시가 추출 당시와 달라졌다. 원래 `sha256_at_extraction`을 보존했고 최신 문서의 R01~R28/E01~E03 **31개 약속·완료 조건이 JSON과 정확히 같음**을 다시 대조했다. `requirements-mapping-check.txt`에 당시/최신 전체 문서 해시와 일치 결과를 기록했다. 변경된 전체 문서를 당시 읽은 원본으로 위장하지 않았다.
- 위 4개 framework 체크를 실제 코드·시험·의존성·입력/출력 해시로 등록한 후 `phase2 validate` PASS.

최종 원시 결과: e run의 `unittest.txt`, `contracts.txt`, `mcp-stdio.txt`, `rules-synced.txt`, `backlog-check.txt`, `requirements-mapping-check.txt`. 문서/Project 스크립트 독립 대조 결과는 c run의 `pm-review-check.txt`다. JSON 근거는 실제 코드/시험/의존성 23개 파일 버전과 원본/출력 SHA256을 포함한다. 기존 91·92·93개 시험 run은 역사로 보존했다. LF 정규화 직후 d run에서 dataset 실제 해시와 manifest의 이전 해시 불일치를 검출해 실패로 남겼다. root가 현재 LF 바이트의 dataset 해시를 manifest에 반영한 후 e run은 모두 통과했다. 실패를 삭제하거나 통과로 변경하지 않았다.

## 판정의 한계와 다음 확인

현재 전체 task `done`과 요구 `verified`는 모두 0개다. 개발 하네스·자료 조회·계약·웹 골격의 검증을 실제 상품기획 판단/콘셉트/수정 Agent 구현이나 효용 입증으로 확대하지 않는다. 설정 검토와 로컬 실행 성공으로 GitHub CI를 통과 처리하지 않았다. `setup_framework`는 실제 CI 결과가 남아 있다.

root가 실제 ChatGPT·Claude 도구 호출과 모델 실험을 별도 증빙으로 등록한다. 이 독립 검토는 해당 원격 서비스를 다시 조작하거나 제출·GitHub 병합을 실행하지 않았다. 호스트 UI 성공, 모델 revision/라이선스/실측, 실제 GitHub CI·통합·평가·배포/제출 증거는 각각의 gate에 연결한다.

기존 phase1 JSON·state·실행 결과 12개는 보존되고 legacy stale 9단계는 숨기지 않았다. 민감한 개인 서류 원본은 private/에 남으며 Git/Notion에 이전하지 않았다.
