# 자료 내 지시문 권한 경계 — 불변 세션 작업기록

- Job ID: `auto-62cf0ffdcbd4ac7d952193ae82e741db19e8c7f6`
- Assignment ID: `PM-20261005-AUTO-62cf0ffdcbd4ac7d`
- 담당: 황대겸 (`unknownamed`), 수행 AI: Codex bounded worker.
- 작업: `P2-CORE-003`, R18/R20, development-only, attempt 1 / max_attempts 1.
- 기록 확정 시각: 2026-10-05T23:38:22+09:00 (KST).
- 승인 출처: 사용자 직접 제공한 trusted PM-approved task packet. [승인 참조](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/28#issuecomment-5996584858).
- 제공된 base/approved snapshot: `02f9a643e92c4665f2f0f71a5690f9ed6ed28930`. 작업 공간에 Git 메타데이터가 없어 독립 대조하지 못했다. 승인 링크는 인증 접근 없이 참조로만 기록했다.
- 이 파일은 해당 job의 최초 확정 세션 기록이다. 기존 개인 문서와 다른 세션을 덮어쓰지 않았으며 후속 작업은 별도 기록으로 연결한다.

## 원 지시와 해석

원 지시 발췌: “source_boundary 모듈이 자료 인용과 시스템/기획 요청을 분리하도록 구조화해 도구 권한이 자료의 지시문으로 늘어나지 않게 한다. 단순 단어 삭제가 아니라 출처/원문 보존과 권한 검사를 구현한다.”

직접 작업 경계: “Implement only approved paths. Do not commit/push, alter git configuration, access credentials, or change formal harness/Project state.” 두 불변 세션 문서에 job ID·원 요청·해석·실제 행동·검사·실패·미완료·다음 행동을 기록하도록 요청받았다.

해석: 현재 judgement 입력과 공통 Product/Evidence/PlanningRequest/응답 계약을 재사용하는 독립 SourceBoundary를 구현한다. 모든 자료 텍스트는 데이터로 보존하고, 권한은 호스트가 별도로 전달한 제한된 조회 정책에서만 나온다. 모델이 정책을 준수한다는 가정으로 권한을 보호하지 않는다. 기존 Agent 호출부 변경은 허용 경로가 아니므로 수행하지 않는다. 패킷의 PR·자기보고 인수 조건은 외부 게시 Worker 단계로 남긴다.

## 실제 행동

1. AGENTS.md와 CLAUDE.md를 읽고 cmp 및 sync_agent_rules --check로 바이트 일치를 확인했다. README·인수인계·대회요건·진행체크리스트의 현황, 자기 기록/근거 재개 요약과 기록 규칙을 참고했다. 저장소 문구로 이번 사용자 범위를 확대하지 않았다.
2. canonical schema와 judgement_contract의 입력 검증/출처 연결 검사, 기존 revision_guard와 store의 조회 계약을 읽었다.
3. `packages/core/src/lgax_core/source_boundary.py`를 신규 작성했다. canonical judgement preflight, 깊은 복사 스냅샷, 입력 전체 SHA256, 구조화 system/user 메시지, 별도 planning_request/reference_data, 명시적인 deny-by-default 도구 검사와 스냅샷 조회를 구현했다.
4. `tests/test_source_boundary.py`를 신규 작성했다. 합성 리뷰 안의 명령/역할 위장/권한 요청을 원문 그대로 보존하면서 불허 호출을 실제 거절하고 허용 조회는 실제 원본을 반환하는지 검사했다. 잘못된 구조·중복 ID·모델/버전/실자료 구분 불일치, 변경 입력, 외부 변이, 오류 비노출도 검사했다.
5. 지정 unittest를 실제 실행하고 자기 검수 후 린트 보완 및 재실행했다. 두 승인 세션 경로를 배타적 신규 생성으로 확정했다. 커밋·push·git 설정·인증정보·공식 상태 변경·네트워크 보고·PR 생성은 수행하지 않았다.

## 검사와 실패

- `PYTHONDONTWRITEBYTECODE=1 uv run --offline --no-sync python -m unittest tests.test_source_boundary -v`: 최초 9 tests / 0.074s / OK / exit 0. 린트 보완 뒤 최종 9 tests / 0.076s / OK / exit 0. PYTHONDONTWRITEBYTECODE는 허용 경로 밖 바이트코드 생성을 피하기 위한 설정이다.
- `uv run --offline --no-sync ruff check --no-cache ...`: 최초 I001 1건 및 B023 10건, 총 11건 진단. 동기 호출 테스트의 람다를 명시적 기본 인자로 바꾸고 import 정렬을 수정했다. 후속 --fix 실행은 1 fixed / 0 remaining / exit 0. 최초 명령은 sync 검사와 한 셸에서 실행되어 마지막 셸 exit 0이 린트 성공을 뜻하지 않는다. 최초 린트는 실패로 기록한다.
- `uv run --offline --no-sync python scripts/sync_agent_rules.py --check`: PASS, AGENTS/CLAUDE byte-identical. 두 파일 수정 없음.
- `git status --short`, `git rev-parse HEAD`: 각각 fatal: not a git repository. 상태/commit을 추정하지 않았다. `packages/core/src/lgax_core/contracts.py` 탐색은 파일 없음; 실제 계약은 packages/contracts에서 확인했다.
- 초기 자료 읽기 일부가 출력 제한으로 잘려 관련 지침/계약을 좁은 범위로 다시 읽었다. 출력에 없는 과거 기록 전체를 검토했다고 주장하지 않는다.

## 자기 검수와 미완료

원문·locator·source_id·source_kind·모델·문서 버전·제품과 feature 자료를 변형하지 않고 보존한다. 고정 시스템 문구에 자료를 이어 붙이지 않으며 모든 동작 제안은 런타임 허용목록 및 인자/근거 범위 검사에 걸린다. 알 수 없는 도구와 권한 사칭 필드를 거절한다. 정상 조회가 실제 입력에 따라 달라지므로 고정 성공 응답이 아니다. 입력 변경 시 새 digest와 별도 정책을 사용하며 기존 snapshot은 유지된다.

이 구현은 호스트 인증이나 Python 프로세스 sandbox가 아니다. 호스트는 자료/모델이 만든 allowed_tools를 생성자에 전달하면 안 되며 모든 도구 제안을 invoke를 통해 처리해야 한다. 현재 허용 도구는 입력 snapshot의 get_evidence/list_products뿐이다. 기존 Agent/모델 어댑터 호출부에는 연결하지 않았다. 프롬프트만으로 모델의 의미 오염을 완전히 막았다는 증거가 아니며 모델 응답 품질·실제 고객 수요·효과·신규성은 측정하지 않았다. public 메타데이터 테스트도 합성 fixture이며 실제 공개 자료 확보 증거가 아니다.

PR/CI/PM 인수/병합/병합 후 통합, 실모델 독립 평가, 부모 Done·의존 해제·최종 제출은 미완료다. 전체 회귀검사와 웹/GPU/외부 서비스 검사는 이번 독립 단위에서 실행하지 않았다.

## 다음 단계와 사용자 직접 할 일

외부 고정 Worker가 네 허용 파일과 해시·검사 결과를 검증하고 게시/PR/자기 상태 보고를 처리한다. PM이 별도 승인한 통합 경로에서 SourceBoundary.messages와 invoke를 연결하고 실제 Agent/모델 및 변경 입력으로 검증한다. 이번 로컬 단위에 사용자가 직접 할 일은 없다. 인증정보나 권한 확대를 요청하지 않는다.

근거: [동일 job 근거](../../../작업근거/세션/황대겸/auto-62cf0ffdcbd4ac7d952193ae82e741db19e8c7f6.md).
