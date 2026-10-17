# 신진하 — 작업근거 목차

<!-- member-log:owner-updates:start -->
- 2026-10-17 [v21 원본 연구원·승인 UI 구조](2026-10-17/신진하-20261017-KITCHEN-AX-V21-APPROVED-COMPOSITION.md). 이미지 무변경·기존 기능/병렬 확대 유지, 공개 Site 버전22·143개 검사 통과; 독립 UI 보존.
- 2026-10-17 [v20 번호순 배치·대기 연구원 착석](2026-10-17/신진하-20261017-KITCHEN-AX-V20-ORDERED-GRID.md). 기존 기능·병렬 확대 유지, 공개 Site 배포·138개 검사 통과; 독립 UI 보존.
- 2026-10-17 [v19 이름표 가림 방지·메인 AI 상태 색상](2026-10-17/신진하-20261017-KITCHEN-AX-V19-LABEL-CLEARANCE.md). 원본 캐릭터·병렬 확대 유지, 공개 Site 배포·135개 검사 통과; 독립 UI 보존.
- 2026-10-17 [v18 Skill·도우미 구분과 역할별 동작](2026-10-17/신진하-20261017-KITCHEN-AX-V18-SKILL-AGENTS.md). 공개 Site 배포·133개 검사 통과; 실제 native 업무/부모 연결 한계·PM 인수와 구분.
- 2026-10-17 [v17 A안 프리미엄 연구소 디자인](2026-10-17/신진하-20261017-KITCHEN-AX-V17-PREMIUM-LAB.md). 시각 소스4파일만 변경, 기존 분석/CLI 기록·병렬 확대 유지; 독립 보존/PM 검토 단계.
- 2026-10-17 [v16 이전 디자인 유지·CLI 기록 기능 통합](2026-10-17/신진하-20261017-KITCHEN-AX-V16-CLASSIC-RECORDS.md). 기본 공장·v5/v15 보존, 기록 재생은 오른쪽 패널; 실제 CLI 업무/PM 인수와 구분.
- 2026-10-16 별도 UI 보존: [KITCHEN AX v15 팀 저장소 보존·접근권한 확인](2026-10-16/신진하-20261016-KITCHEN-AX-V15-TEAM-SNAPSHOT.md). 기존 v5·제품 코드를 유지하고 새 버전 폴더/브랜치에만 추가.
- 2026-10-15 별도 UI 보존: [KITCHEN AX 공장 대시보드 독립 스냅샷](2026-10-15/신진하-E-20261015-KITCHEN-AX-DASHBOARD-SNAPSHOT.md). 새 폴더·보존 브랜치만 사용하며 팀 제품 통합/PM 인수와 구분한다.

## 작성자의 최신 재개 요약
- 최신 기록 ID / 한국시간 / 목표: `신진하-E-DATA190-CORE198-INTEGRATION-01a1100e` · 2026-10-06 22:40 KST · PR190/CORE198 DATA 소비 정합·web 오류7·실측225 인수/독립검수·운영 조회.
- 완료/미완료: CORE198 고정policy를소비해conflicting 예외와실제schema4회귀/한국어7설명추가, Docker71핵심검사PASS. 전체Python/web 최종재검사중. PR200 실제225실측의원문21/질의15/모델·원문SHA/10개진단metrics 독립audit PASS(모델추가0). 승인운영3GET재조회는로컬오류2/외부502로미확인. PM운영읽기인계·FR01gold·PR190 검수/CI·CORE실모델 의미품질이남음. 부모Done 아님.
- 상세 기록: [이번 날짜·기록ID](2026-10-06/신진하-E-DATA190-CORE198-INTEGRATION-01a1100e.md)
- 관련 근거: [190/198 실행 인계](../../../evals/data190-core198-integration/20261006-01a1100e/handoff.json)
- 최종검사: 2026-10-06 23:16 KST DockerPython1498/skip3·reason registry5/safe-ci4/빌드·Ruff/계약/지침PASS. PR190 고정원반례/보류정보전파를CORE198와통합. local전체web timeout은보존하고새head CI/PM검수를기다림. [검사원로그](../../../evals/data190-core198-integration/20261006-01a1100e/checks.json)
- 새 네후속 결과 `신진하-E-FOUR-FOLLOWUP-01a10600` · 2026-10-06T21:57 KST: 검색225/실패0·630근거대조PASS; 운영GET6 실패/버전미확인, 날짜8핀대조PASS·운영/WEB미확인, FR-01/독립평가미완료. [고유상세](2026-10-06/신진하-E-FOUR-FOLLOWUP-01a10600.md) · [인계](../../../evals/data-four-followup/20261006-01a10600/README.md). 부모Done아님.
- 최신 기록 ID / 한국시간 / 현재 목표: `신진하-E-DATA-INTEGRATION-R4-01a1100e` · 2026-10-06 20:56 KST · PM DATA-INTEGRATION-R4의3팩원문/날짜/검색 대조·후속제출.
- 실제 완료 범위 / 미완료·막힘 / 다음 행동과 담당: 원36/CSV8열 보존, 108원문·ID/모델/버전 연결, 15query독립재계산/재생·40거절, 최신검사main087bd에서PDF3/근거21/실HTTP46·재시작PASS. 원날짜미상/PM31날짜/DATA9날짜는각source/version/IDs로유지;청소1/3과1/4는원문membership가다름. PM 운영/분류/독립자료 승인, CORE 의미/보류, WEB 새DATA9팩화면·내보내기가남음. 부모Done/실고객수요아님.
- 상세 작업근거: [R4 고유 기록ID](2026-10-06/신진하-E-DATA-INTEGRATION-R4-01a1100e.md)
- 관련 근거: [3팩 고정값·실행·담당 인계](../../../evals/data-integration-r4/20261006/README.md)
- 선행 실제상태: PR183·PR189 실제병합 확인. 최신main b67886f 위R4단위에서108바인딩/15query/40거절·실HTTP46/PDF3/근거21/재시작PASS. PM188날짜3파일은고정핀과같음; 공통문서nav는PM188미병합으로미제공. 이번R4의새PR/CI/PM 인수·운영은별도.
- 별도 운영 읽기 조회 `OPS-READONLY-01a10600`(2026-10-06T21:04 KST): PR183/main7파일 기준 동일, 운영GET6 응답 미확보로 일치 미확인. [새 운영 읽기 근거](2026-10-06/신진하-E-OPS-READONLY-01a10600.md); 기존 R4 후속·원실행/실패는 유지.
- `DATA-D1-D2-01a10600` / 2026-10-07: 리뷰238 통합 DB·XLSX·개발141 묶음 및 기존3PDF/21근거·공식FAQ3/설치3/Q&A1 첫 인계. P0 소비·Q&A2미확인·독립 승인·전체Done은 남음. [고유 상세](2026-10-07/신진하-E-20261007-D1-D2-01a10600.md).
- 같은 D1·D2 후속: 첫6fd98c0 뒤 PM PR245/ef29aa8 P0규격 수신, 현재 canonical3입력과 source141/공식근거170의 별도 계약 대조 진행. 원DB/XLSX·원19회귀/실패는 유지; 실제모델/운영/#12Done 아님.
- 10/8 최종 D1·D2: P0 정식3입력·개발141·공식근거 연결 PASS. 연구DB238/Excel 보존, 안내1셀 현재화. [최종 기록](../../작업기록/신진하/2026-10-08/신진하-20261008-D1-D2-P0-인계-01a10600.md). 운영/실모델/독립평가/전체Done은 별도.
<!-- member-log:owner-updates:end -->
기존 원문의 기계적 분할·탐색 목차입니다. 새 수행·판정·완료 상태를 추가하지 않습니다.

[연결된 개인 작업기록](../../작업기록/신진하/README.md) · [기존 경로·anchor 목차](../신진하.md) · [전체 원바이트 snapshot](archive/84844b86-original.md)

## 원문 구간 — 원래 순서

- 0001 · `legacy` · [소개·공통 참조](legacy/0001-소개-공통-참조.md)
- 0002 · `legacy` · [현재 상태](legacy/0002-현재-상태.md)
- 0003 · `legacy` · [근거 기록](legacy/0003-근거-기록.md)
- 0004 · `legacy` · [신진하-E015-shared-connection — gh 설치·개인 인증 막힘·새 ACK/부분 인수 확인](legacy/0004-신진하-E015-shared-connection.md)
- 0005 · `legacy` · [신진하-E014-local-remaining — 현재 연결 실패·평가 준비·새 ACK/PM 검수 대기](legacy/0005-신진하-E014-local-remaining.md)
- 0006 · `legacy` · [신진하-E013-ci-recovery — 게시 후 옛 입력 버전 회귀 실패 복구](legacy/0006-신진하-E013-ci-recovery.md)
- 0007 · `legacy` · [신진하-E012-publish-citations — 후속 PR·인증 보고 게시 승인](legacy/0007-신진하-E012-publish-citations.md)
- 0008 · `legacy` · [신진하-E011-stage45 — 인용 연결 보완과 의미 평가 입력 준비](legacy/0008-신진하-E011-stage45.md)
- 0009 · `legacy` · [신진하-E010-handoff — 최신main 재검사·부분 인수 게시 승인](legacy/0009-신진하-E010-handoff.md)
- 0010 · `legacy` · [신진하-E001-local — 식기세척기 예시의 실제 제품 대응](legacy/0010-신진하-E001-local.md)
- 0011 · `legacy` · [신진하-E002-local — 세 제품군 기존 자료의 실제 확보·참조 대조](legacy/0011-신진하-E002-local.md)
- 0012 · `legacy` · [신진하-E003-local — 세 실모델 참고팩·#12 충족/잔여 대조](legacy/0012-신진하-E003-local.md)
- 0013 · `legacy` · [신진하-E004-local — R03 환경·기존 경로 진단](legacy/0013-신진하-E004-local.md)
- 0014 · `legacy` · [신진하-E005-local — CHECKPOINT 부분 전달·연결 및 평가 구분](legacy/0014-신진하-E005-local.md)
- 0015 · `legacy` · [신진하-E006-local — #12 계약 검사·부분 전달 재개 확인](legacy/0015-신진하-E006-local.md)
- 0016 · `legacy` · [신진하-E007-local — 승인 환경의 기존 계약·조회 실제 실행](legacy/0016-신진하-E007-local.md)
- 0017 · `legacy` · [신진하-E008-local — 실제 설명서 등록·파싱·기획 입력·조회 연결](legacy/0017-신진하-E008-local.md)
- 0018 · `legacy` · [신진하-E009-local — CSV 원문 연결·실모델 작업실 조회·평가 인수metadata](legacy/0018-신진하-E009-local.md)
- 0019 · `legacy` · [신진하-E017-evidence-publication — 게시 승인·증거 버전/범위 검증](legacy/0019-신진하-E017-evidence-publication.md)

## 기록 ID 조회

- `E016-manual-execution`: [원문 1](legacy/0002-현재-상태.md)
- `신진하-E015-shared-connection`: [원문 1](legacy/0004-신진하-E015-shared-connection.md)
- `신진하-E014-local-remaining`: [원문 1](legacy/0005-신진하-E014-local-remaining.md)
- `신진하-E013-ci-recovery`: [원문 1](legacy/0006-신진하-E013-ci-recovery.md)
- `신진하-E012-publish-citations`: [원문 1](legacy/0007-신진하-E012-publish-citations.md)
- `신진하-E011-stage45`: [원문 1](legacy/0008-신진하-E011-stage45.md)
- `신진하-E010-handoff`: [원문 1](legacy/0009-신진하-E010-handoff.md)
- `신진하-E001-local`: [원문 1](legacy/0010-신진하-E001-local.md)
- `신진하-E002-local`: [원문 1](legacy/0011-신진하-E002-local.md)
- `신진하-E003-local`: [원문 1](legacy/0012-신진하-E003-local.md)
- `신진하-E004-local`: [원문 1](legacy/0013-신진하-E004-local.md)
- `신진하-E005-local`: [원문 1](legacy/0014-신진하-E005-local.md)
- `신진하-E006-local`: [원문 1](legacy/0015-신진하-E006-local.md)
- `신진하-E007-local`: [원문 1](legacy/0016-신진하-E007-local.md)
- `신진하-E008-local`: [원문 1](legacy/0017-신진하-E008-local.md)
- `신진하-E009-local`: [원문 1](legacy/0018-신진하-E009-local.md)
- `신진하-E017-evidence-publication`: [원문 1](legacy/0019-신진하-E017-evidence-publication.md)

## 기존 불변 세션 — 원래 경로 유지

- [data002-history-publish-20261005-01a10812.md](../세션/신진하/data002-history-publish-20261005-01a10812.md)
