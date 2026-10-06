# LG AX 키친 상품기획 Agent

LG전자와 함께하는 국립창원대학교 AX 해커톤 전용 저장소다. **키친에서치킨먹기** 팀은 Theme A의 고객 불편·기존 제품 대조 기반 상품기획 Agent를 개발한다. 기획자가 리뷰와 제품 문서의 근거를 확인하고, 남은 불편·콘셉트·요구사항을 검토·수정하는 업무를 웹 작업실과 MCP에서 같은 코어로 수행하는 것이 목표다.

**지금 읽을 입구**

- [문서 정본·읽기 순서·작성 위치](docs/README.md)
- [작업 재개](docs/인수인계.md) · [PM 현재 배정](docs/pm/현재배정.md) · [검수·제출 점검](docs/진행체크리스트.md)
- [공식 요건](docs/대회요건.md) · [신청 원고](기획/제출제안서_원고.md) · [채택 설계](기획/채택안_Agent설계.md)
- 최신 [AGENTS.md](AGENTS.md)와 [CLAUDE.md](CLAUDE.md)는 전체 내용을 동일하게 유지한다. 승인된 본인 사서함의 LG 관련 메일·선행 협의와 자신의 재개 요약을 먼저 확인한다. 과거 운영 기록의 ‘현재·최신·ON’은 새 지시가 아니다. 자동화는 새 사용자 ON 지시 전 OFF를 유지한다.

**고정 개발 구조**

| 영역 | 위치·규격 |
|---|---|
| 웹 기획 작업실 | `apps/web` — React·TypeScript·Vite, npm |
| API·MCP·공통 판단 | `apps/api`, `apps/mcp`, `packages/core` — Python 3.11, uv |
| 공통 계약·자료·모델 | [JSON Schema](packages/contracts/schemas/lgax.schema.json), `data`, `services/inference` |
| 재실행 Skill·검증·개발 하네스 | `skills/*/SKILL.md`, `evals`, [phase2](harness/phase2/README.md) |

의존성은 `uv.lock`과 `apps/web/package-lock.json`을 따른다. 실기기·ThinQ 계정이나 기업 내부 데이터를 필수로 가정하지 않는다. 실제 구현·모델/자료 버전·현재 실행 환경·완료 상태는 [현재 배정](docs/pm/현재배정.md), 해당 작업 패킷·PR·불변 실행 근거를 조회한다. 원문·합성 자료, 실제 모델 판단·저장된 출력 재생, 검사·통합 완료를 구분한다.

**실행·검사 위치**

[bootstrap 실행 안내](docs/bootstrap/README.md)에서 설치·명령·환경 조건을 확인하고 최신 공통 지침의 권한 경계를 따른다. 제품 실행·테스트·모델은 승인된 격리 환경에서 수행하며 게시·PM 자격증명과 분리한다. [하네스 입구](harness/README.md), [평가](docs/pm/evaluation.md), [제출](docs/pm/submission.md), [협업·기록 규칙](docs/작업기록/README.md)에서 해당 업무의 실제 검사·증빙·보고·완료 조건을 확인한다.

**협업 위치**

- 비공개 저장소: [2026-LG-kitchen-chicken-team/lg-ax-2026](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026)
- [고정 운영 Issue #28](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/28) · [조직 Project](https://github.com/orgs/2026-LG-kitchen-chicken-team/projects/1) · [팀 협업체계](docs/협업체계.md)
- PM은 정이량, 공식 팀장은 황대겸이다. 각자 담당·편집 영역·후속 작업과 실제 권한은 공통 지침·현재 배정·인증된 조회에서 확인한다. 개인 정보·서명·동의·접수/결제 증빙·비밀키는 Git에서 제외된 `private/`에 유지한다.
- [LG 노션 페이지](https://app.notion.com/p/3e7b3295f8cb81fdb730f6ef105a927c)는 중요 일정·운영 안내의 참고/동기화 위치다. 실제 반영·재조회 없이 최신화 완료로 표현하지 않는다.

**이전 README와 기존 링크**

기존 날짜별 운영 본문은 [원바이트 원문](docs/history/project/20261006/originals/README.md)과 [원래 위치 기준 링크 안내](docs/history/project/20261006/links.md)에 보존했다. [이관 manifest·검사](docs/history/project/20261006/README.md)를 따른다. 아래 제목은 기존 anchor 호환 목차이며 새 경과를 누적하지 않는다.

<!-- document-navigation:legacy-anchors:start -->

# LG AX 해커톤 작업실

[당시 원문 — 원 경로 README.md, 1행](docs/history/project/20261006/originals/README.md#lg-ax-해커톤-작업실)

## 현재 상태

[당시 원문 — 원 경로 README.md, 21행](docs/history/project/20261006/originals/README.md#현재-상태)

## 지금 볼 문서

[당시 원문 — 원 경로 README.md, 44행](docs/history/project/20261006/originals/README.md#지금-볼-문서)

## GitHub 협업

[당시 원문 — 원 경로 README.md, 79행](docs/history/project/20261006/originals/README.md#github-협업)

## 이어서 볼 문서

[당시 원문 — 원 경로 README.md, 91행](docs/history/project/20261006/originals/README.md#이어서-볼-문서)

## 공식 링크

[당시 원문 — 원 경로 README.md, 101행](docs/history/project/20261006/originals/README.md#공식-링크)

## 승인 작업 자동화

[당시 원문 — 원 경로 README.md, 109행](docs/history/project/20261006/originals/README.md#승인-작업-자동화)

<!-- document-navigation:legacy-anchors:end -->
