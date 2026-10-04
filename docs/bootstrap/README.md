# 2차 개발 시작 안내

2026-10-04 사용자 승인 계획을 단일 저장소 `2026-LG-kitchen-chicken-team/lg-ax-2026`에 적용한다. 이 문서는 개발 기반 안내이며 참가작 전체 구현 완료를 뜻하지 않는다.

## 팀이 시작할 곳

### 현재 재개 기준 (2026-10-05)

운영 보드는 [조직 Project1](https://github.com/orgs/2026-LG-kitchen-chicken-team/projects/1)이며 [저장소 Projects](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/projects)에서도 같은 보드를 연다. 이전 개인 Project3는 역사 기록이며 새 작업에 사용하지 않는다. [PM 현재 배정](../pm/현재배정.md)·[Project 이관 기록](../프로젝트이관_2026-10-05.md)을 따른다.

현재 Done은 초기 설정2·WEB001/002·CORE001의 5개 작업이며 신청31요구 verified0이다. PR58에서 실제 Qwen 판단→인증 API·결과 저장→전용 MCP 조회를 확인했으나 변경 실행에 제외 조건 위반이 남았다. 후속 의미 검토·검사/수정 Agent·실제 웹 판단 흐름·독립 평가·최종 제출의 최신 범위는 [PM 현재 배정](../pm/현재배정.md)을 읽는다. 현재 우선 배정은 PM #19/#20 통합→#21 평가→#22 제출, 황대겸 #8 의미 검수→#9 수정/검사, 신진하 #12 자료팩→#13/#14, 최길웅 #25 후보 검토/조건 재실행→#26이다.

### 초기 PM 공통 연결 진행 (10/4 역사)

아래는 PR31 선행 구현 당시 상태이며 현재 작업은 위 재개 기준을 우선한다.

정이량 #19/#20의 선행 구현: [공통 작업실 API·저장·권한](../pm/workspace.md), [구조화 모델 어댑터](../pm/model-adapters.md), [다섯 Skill 실행 계약](../pm/skills.md). SQLite 원입력/변경 이력과 인증된 loopback API·MCP stdio·웹용 TS 클라이언트를 실제 연결했다. 서버 재시작 보존과 Lab/Ollama 실제 호출도 확인했다. 실제 화면 연결·코어 결과 저장·네 판단 Skill의 실모델 반복 실행은 후속 통합이다. 기존 공개3도구의 계정 검증을 새 작업실 OAuth 검증으로 확대하지 않는다.

P2-PM-003/004는 전체 완료 조건이 남아 있으므로 Done으로 바꾸지 않는다. 황대겸 #8/#9, 최길웅 #24/#25와 정이량 통합 후 재개한다. 참가작31요구 verified0을 유지한다.

선행 코드와 규격은 [PR #31](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/31)로 main에 병합했다. [실제 CI·병합 commit·공통 기록 재확인](../../evals/pm-workspace/20261004/delivery/checks.json)과 PM의 정이량-20261004-003/E004에서 확인한다. 이 PR 병합은 PM 두 과제의 전체 완료와 별개다.

| 담당 | 업무 | 초기 첫 Issue (10/4) | 편집 영역 |
|---|---|---|---|
| 정이량 / jeongiryang | PM, 공통 계약, 연결, 통합·검수·병합·제출 | [공동 실행/이력 #19](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/19), [다섯 Skill #20](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/20) | 계약, API/MCP, 하네스, CI, 운영 문서 |
| 황대겸 / unknownamed | 핵심 판단·대조·콘셉트·검사·수정 | [판단 계약 #7](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/7) | 공통 코어의 판단 구현, 관련 Skill·평가 |
| 신진하 / ginaginaring | 자료 처리·검색·원문 근거·모델 비교 | [세 제품 자료팩 #12](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/12) | data, 자료/검색 코어, 모델 서비스·평가 |
| 최길웅 / choigilung | 웹 기획 작업실·사용자 검토·수정 이력 | [웹 작업실 #23](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/23) | apps/web, 웹 검증·사용 안내 |

[고정 운영 Issue #28](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/28) · [2차 개발 Project](https://github.com/orgs/2026-LG-kitchen-chicken-team/projects/1).

대시보드 편집/관리는 정이량 PM만 한다. 세 팀원은 Project 조회 전용이고 자기 Issue/PR·작업기록으로 진행/검수 요청을 남긴다. 신진하의 새 저장소 초대 수락·Write 권한을 확인했고 자료 Epic #5·#12~#16 담당자로 지정했다. [실제 권한 변경·검증](../프로젝트권한_2026-10-04.md)을 따른다.
모두 자기 `docs/작업기록/{성명}.md`와 `docs/작업근거/{성명}.md`를 읽고 사용자 지시·AI 해석·실제 수행·증빙·다음 행동을 기록한다. 이 초기 설정은 PM의 AI가 수행한 공통 작업이다. 각 팀원이 수행했다고 대신 기록하지 않는다.

### 자기보고와 PM의 공식 승인

[협업 체계](../협업체계.md)와 [PM 관리 서비스](../../services/project_reports/README.md)를 따른다. 세 팀원은 Project Read를 유지하고 자기 인증 계정으로 자기 담당 Issue에 세 상태만 보고한다. 자기 기록·근거를 같은 전체 commit SHA로 commit·push한 뒤 사용한다.

```powershell
uv run python scripts/project_report.py status
uv run python scripts/project_report.py status --member 신진하
uv run python scripts/project_report.py report P2-DATA-001 --status doing --summary "세 제품의 문서·모델·버전 연결을 작성 중" --next-action "제품별 근거 ID와 원문 위치를 검사" --send --wait 60
```

blocked는 `--reason`, review_requested는 자기 열린 비초안 PR의 `--pr-url`을 추가한다. `--send`를 빼면 미리보기만 한다. 댓글 발송과 서비스의 ACCEPTED 수신 확인을 구분한다. 서비스가 반영하는 값은 자기 작업의 `Status`·`팀원 보고`·`최근 보고`·`다음 행동`뿐이며, 정식 `진행상태`·배정·우선순위·기한·완료는 PM 권한으로 남는다. 선행 작업 대기 중 부분 개발/검수 요청은 가능하나 보고만으로 의존을 해제하지 않는다.

공식 근거는 PM이 검증한 배포 정책의 승인 스냅샷과 운영 Issue #28에 실제 PM 계정이 남긴 `/lgax-sync` 승인이다. PM은 정확한 현재 main commit·근거를 검증하고 `uv run python scripts/sync_github_phase2.py --apply`로 공식 필드와 승인 댓글을 게시한다. 팀원이 main 파일을 수정한 사실이나 로컬 조회의 착수 가능 표시만으로 Done·의존 해제·확장 채택을 확정하지 않는다.

새 배정의 공용 JSON·Issue·비공개 발송 대기 → 연결된 Gmail 실제 발송 → Sent 메타데이터 확인·수신증 기록은 PM AI가 수행한다. 팀원 보고 서비스가 수동 GitHub 편집을 감시해 메일을 보내는 구조는 아니다. 2026-10-04 실제 배포·재시작 보존, PM 계정 보고/거절 시험과 세 메일 SENT 대조를 확인했다. 세 팀원 계정의 실보고·열람은 별도이며 최신 정이량006/E007과 evals/team-coordination/20261004/를 따른다.

## 구조와 공통 계약

- `apps/web`: React·TypeScript·Vite 기획 작업실. 자료 조회와 미구현 분석 상태를 표시한다.
- `apps/api`: 웹용 Python API. `apps/mcp`: 동일 코어의 읽기 MCP 도구.
- `packages/core`: 제품·근거 저장/조회와 후속 판단 구현. `packages/contracts`: JSON Schema Draft 2020-12 원본, Python 검증, TypeScript/Ajv 검증.
- `services/inference`: 연구실 공개 모델 실험/실행 환경. `data/demo`: 합성 냉장고·식기세척기·전자레인지 자료팩.
- `skills`: 기존 Skill 보존 및 후속 재실행 Skill. `evals`: 실제 모델 비교와 후속 독립 평가.
- `harness/phase2`: 31개 요구사항·21개 작업·검증 근거·검수/병합/통합 상태. 이전 선정/접수 AtoZ는 역사 상태로 보존한다.

초기 공개 API의 `POST /api/planning-requests`는 `501 NOT_IMPLEMENTED`를 반환한다. 인증된 private 작업실에서는 PR58의 실제 모델 판단·결과 저장·전용 MCP 조회를 확인했다. 공개 읽기 서비스와 부분 판단 실행을 구분하며, 조건 의미 검증·검사/수정·실제 웹 판단 흐름과 신청서 전체 구현의 최신 상태는 PM 배정과 실행 증거를 따른다.

## 로컬 설치와 실행

Python 3.11과 uv, Node 22 이상 및 npm이 필요하다. Windows 한글 경로에서 editable import는 `dev-mode-exact`를 사용한다. 실행 파일이 Windows 정책에 막히면 아래 Python 모듈 명령을 사용한다. 정책을 변경하지 않는다.

```powershell
uv sync --locked --dev
npm ci --prefix apps/web
uv run python -m lgax_api.server --host 127.0.0.1 --port 18867
uv run python -m lgax_mcp.server --transport streamable-http --host 127.0.0.1 --port 18866
npm run dev --prefix apps/web -- --host 127.0.0.1 --port 5173
```

각 서비스는 별도 터미널에서 실행한다. 웹 http://127.0.0.1:5173 , API http://127.0.0.1:18867/api/bootstrap , MCP http://127.0.0.1:18866/mcp .

```powershell
uv run python scripts/sync_agent_rules.py --check
uv run python scripts/check_contracts.py
uv run python scripts/phase2.py validate
uv run python -m unittest discover -s tests -v
uv run python scripts/smoke_mcp.py --transport stdio
uv run python scripts/smoke_mcp.py --url http://127.0.0.1:18866/mcp
npm run test --prefix apps/web
npm run build --prefix apps/web
```

## 자연어 지시와 개발 하네스

AI는 하네스 키워드 없이 작업 지시를 받으면 담당 패킷을 읽고 실제 작업을 수행한다. 하네스가 AI나 서버를 자동으로 대신 실행하지 않는다.

```powershell
uv run python scripts/phase2.py status
uv run python scripts/phase2.py next --member 황대겸
uv run python scripts/phase2.py packet P2-CORE-002
uv run python scripts/phase2.py gate setup_framework
uv run python scripts/phase2.py gate setup_external
```

준비→개발→개별 검증→PM 검수→실제 병합→병합 후 통합 확인→완료를 구분한다. 상태 명령에 이름을 적는 것은 인증·사람의 승인 증명이 아니다. 실제 GitHub PR·실행 결과·commit을 연결한다. 확장 기능은 필수 31요구와 구분하고 PM 배정 후 시작한다.

## 연결과 제출

공개 읽기 MCP는 `https://eryang-lab.tailb7c3c1.ts.net/lg-ax/mcp`이다. PC 서비스와 Tailscale이 실행 중이어야 한다. 합성자료 조회만 제공하며 개인정보·서버 제어·비용 발생 모델 실행 도구를 공개하지 않는다. ChatGPT/Claude의 실제 호출 여부는 [연결 검증](connections.md)에 기록한다.

공통 요구·모델 revision·근거 계약 변경은 PM에게 영향과 마이그레이션을 먼저 제시한다. 타인 영역이 필요하면 Issue에서 편집 범위를 조정한다. 10/6 오전 컨설팅 일정 확인, 10/20 발표자료·영상·README/Skill 포함 코드 ZIP 준비는 후속 작업이다. 정확한 제출 시각·경로·용량·영상 길이는 공식 확인 전이다.

## 초기 설정 완료 기록 (10/4 역사)

초기 설정·실제 연결은 [PR #29](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/29)로 병합했다. 실제 GitHub CI([최종 구현 검사](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/actions/runs/37147862767))와 병합 commit `ea4389a1d9d8d4e469bc049ab4e3ef91871ace8d`의 별도 깨끗한 작업 공간에서 Python 기본93·서버 운영6·웹11시험, 타입/빌드, 계약/기록, stdio/공개HTTPS MCP 호출이 통과했다. 근거는 `harness/phase2/runs/post-merge-ea4389a1d9d8/`다.

PR29 초기 설정 당시에는 P2-PM-001·002 두 작업만 Done이었다. 참가작31요구 verified0·전체 Agent/Skill/평가/ZIP 후속 상태와 당시 첫 배정 PM #19/#20·황대겸 #7·신진하 #12·최길웅 #23을 보존한다. 현재 Done5·황대겸 #8·최길웅 #25는 상단과 PM 현재 배정을 따른다. 다음 작업의 입출력/범위/완료 조건은 각 Issue와 packet을 따른다.

초기9체크의 코드/자료 원본은 실제 병합 commit의 바이트와 일치하는 스냅샷으로 고정했다. gate PASS는 기록된 초기 버전의 검증이며 현재 서버 생존을 감시하는 기능이 아니다. 새 기능·모델·자료 변경은 담당 작업의 새 run/현재 버전/실행 증거로 검사한다. 공통 data/demo와 bootstrap 실험의 원본을 덮어 쓰지 않는다.

LG Notion 페이지와 공모전 대시보드를 10/4 실제 결과로 갱신·재조회했다. 상세 로그/민감정보는 옮기지 않았고 다른 공모전 내용은 수정하지 않았다. 신진하의 초대 수락·Write 권한과 담당자 지정은 후속 확인 완료했다. 10/6 실제 컨설팅 일정·10/20 제출 세부는 여전히 확인 과제다.

## 개발 자동화와 병목 개선

[ON/OFF·설치·기록·공유 모델 접근](../pm/automation.md)을 따른다. 초기 모드는 전원 OFF다. 중앙 서비스와 개별 Worker 설치·인증, PC 온라인을 구분한다. 정식 PM 승인·병합·Done은 기존 규칙을 유지한다.

Codex와 Claude Code 중 자기 실행기를 선택할 수 있다. [각 PC의 초기 설정 안내](automation-workers.md)를 자기 AI와 함께 진행한다. Claude 사용자는 Codex 구독·로그인이 필요 없다. 웹 Claude/GitHub App 로그인과 로컬 Claude Code 로그인은 별개다.
