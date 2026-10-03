# 2차 개발·검증·제출 하네스

이 하네스는 현재 작업하는 팀원 AI에게 구체적 작업 패킷을 제공하고, 실행 증빙과 PM 검수·병합·통합 확인을 연결한다. 별도로 모델을 호출하거나 팀원에게 메시지를 보내거나 GitHub를 병합하지 않는다. 상품기획 Agent와 개발 하네스는 다른 시스템이다.

## 현재 기준

- 31개 요구: 신청 원안 `R01~R28`와 평가 약속 `E01~E03`. 원본 PDF와 해시는 `sources.lock.json`, 요구별 담당·완료 조건은 `requirements.json`.
- 정이량 `jeongiryang`: PM·MCP·통합·재현·제출. 황대겸 `unknownamed`: 핵심 판단·검사·수정. 신진하 `ginaginaring`: 자료·근거·기술 조사. 최길웅 `choigilung`: 웹 검토 작업실.
- 21개 작업은 `tasks/`에 있다. 필요한 범위가 커지면 PM이 다음 작업을 배정한다. 기술 조사와 형태/사용성 확장 task는 `proposed_extension`이며 자동 채택으로 취급하지 않는다.
  이 두 제안은 `adoption_required: true`, `adoption: null`이다. 의존 작업이 끝나도 PM의 실제 채택 증거 전에는 `next`·`start`·`finish`·검수/완료 대상으로 활성화되지 않는다. 직접 `packet`으로 내용을 읽어도 `execution_authorized: false`이며 채택 요청에 필요한 검토만 할 수 있다.
- 실제 서버·모델·ChatGPT·Claude 호출, 참가작 구현, PM 승인·병합·통합 완료는 각 증거가 생기기 전까지 미확인이다. `validate`의 PASS는 기록 구조와 증빙 무결성 검사다.

## 시작과 재개

root AGENTS.md·CLAUDE.md 전체 내용은 동일해야 한다. 작업 전 공통 문서와 자기 작업기록/근거 및 해당 task를 읽는다.

```powershell
python scripts/phase2.py status
python scripts/phase2.py next --member unknownamed
python scripts/phase2.py packet P2-CORE-001
python scripts/phase2.py start P2-CORE-001 --actor unknownamed
```

의존 task가 완료되지 않아도 fixture 기반 독립 개발은 진행할 수 있다. `finish`는 의존 완료와 해당 task가 요구하는 실행 종류까지 충족해야 한다. 별도의 `block`은 다른 Ready 작업을 막지 않는다.

```powershell
python scripts/phase2.py block P2-PM-002 --actor jeongiryang --reason "실제 호스트 계정 연결 대기"
python scripts/phase2.py finish P2-CORE-001 harness/phase2/runs/실제기록/run.json --actor unknownamed
python scripts/phase2.py request-review P2-CORE-001 --actor unknownamed
```

작업기록과 근거 문서에는 요청 원문·해석·실제 행동·검증·근거 ID·재개 위치를 남긴다. 이 하네스가 개인 문서 작성까지 자동 수행하는 것은 아니다.

제안 확장을 실제로 배정할 때는 PM이 채택 JSON을 만든 뒤 다음 명령을 실행한다. JSON에는 정확한 `task_id`, `pm: 정이량`, `decision: adopted`, 실제 결정 관찰 `observations`, 요청 출처 `instruction_source`(`PM assignment` 또는 `user instruction`)와 실제 지시 발췌 `instruction_quote`를 기록한다. 명령 실행은 PM의 선언된 기록이며 사람의 직접 결정을 위조하는 기능이 아니다. 채택 이후에도 의존 완료·개별 실행·PM 검수·병합·통합 확인은 별도로 필요하다.

```powershell
python scripts/phase2.py adopt P2-DATA-005 harness/phase2/runs/실제기록/adoption.json --actor jeongiryang
```

## 증거 계약

run JSON 필수 항목: `task_id`, `owner`, `result: pass`, `execution_kind`, `observations`, `limitations`, `code_versions`, `source_versions`, `checks`.

각 check는 이름·실제 검사 결과·출력 파일 `{path, sha256}`를 가진다. code/source 버전도 실제 파일 해시를 기록한다. 변경하지 않는 run/output 파일을 `runs/<run-id>/`에 저장하고, 계속 갱신되는 작업기록을 완료 증거의 해시 대상으로 쓰지 않는다. 파일을 재실행해 바꾸면 새 run ID를 만들고 이전 기록은 보존한다.

- `deterministic`: 코드·스키마·규칙 검사. 의미 판단·수요 검증과 다르다.
- `fixture`: 준비 입력·모의 응답 경로 검증. 실모델·서버·호스트 성공 증거가 아니다.
- `live_service`: 실제 API·MCP·서버 실행.
- `live_model`: 실제 모델 호출. `models`에 model_id·revision·license·runtime·settings를 함께 기록한다.
- `live_client`: 실제 ChatGPT/Claude/제출 사이트 클라이언트 동작.

합성 입력 사용 여부와 도구/모델 실제 실행 여부는 별도로 적는다. 합성 자료를 조회·분석하는 실제 모델 실행은 가능하나 시장 수요의 증거가 되지 않는다.

파일 변경 뒤에도 역사 증거를 검증하려면 `code_versions` 또는 `source_versions`의 record에 `git_commit` 전체 SHA를 붙일 수 있다. 검사는 해당 commit의 파일을 `git show`로 읽어 해시를 확인한다. 실행 중 미커밋 코드에는 현재 파일 해시를 사용하며, 이후 변경되면 재검증이 필요하다.

## PM 검수·병합·통합·완료

```powershell
python scripts/phase2.py review P2-CORE-001 harness/phase2/runs/실제기록/review.json --actor jeongiryang
python scripts/phase2.py merge P2-CORE-001 harness/phase2/runs/실제기록/merge.json --actor jeongiryang
python scripts/phase2.py verify P2-CORE-001 harness/phase2/runs/실제기록/integration.json --actor jeongiryang
python scripts/phase2.py complete P2-CORE-001 harness/phase2/runs/실제기록/complete.json --actor jeongiryang
```

`review`: task_id·pm=정이량·명시적 approved/changes_requested 결정·검수 관찰·individual_evidence_sha256를 요구한다. `merge`: 실제 로컬 Git commit으로 확인되는 merge_commit·pull_request_url를 요구한다. `verify`: 실제 검사와 tested_commit이 병합 commit과 같아야 한다. `complete`: PM 명시 결정과 정확한 integration_evidence_sha256를 요구한다.

상태: `ready → doing → individual_verified → pm_review_requested → pm_approved → merged → integration_verified → done`. 검수 수정 요청은 doing으로 되돌리고 새 실행 증빙을 받는다. 승인/병합 후 변경은 새로운 task/PR로 처리한다. `--actor`는 기록된 담당자 이름이며 계정 인증을 대신하지 않는다. 실제 GitHub review/merge와 증빙은 PM이 별도로 확인한다.

요구별 검증은 완료 task의 실제 실행 증빙으로 기록한다. fixture만으로 R/E 구현 완료를 기록할 수 없다.

```powershell
python scripts/phase2.py cover R09 P2-CORE-002 harness/phase2/runs/실제기록/coverage.json --actor jeongiryang
```

## 구조 검사와 완료 gate

```powershell
python scripts/sync_agent_rules.py --check
python scripts/phase2.py validate
python scripts/phase2.py gate setup_framework
python scripts/phase2.py gate setup_external
python scripts/phase2.py gate setup
python scripts/phase2.py gate integration
python scripts/phase2.py gate evaluation
python scripts/phase2.py gate release
python scripts/phase2.py gate submission
```

`checks.json`에는 관찰 전 check가 pending으로 있다. PM은 실제 출력·source/code hash가 있는 JSON에 check_id를 붙여 `record-check`로 등록한다. 실패·미확인은 해결하거나 block_reason을 남긴다. `setup_framework`는 규칙/계약/Ready 목록/CI/로컬 MCP, `setup_external`은 서버/실모델/실제 두 호스트이며 어느 한쪽의 통과로 다른 쪽 성공을 주장하지 않는다.

```powershell
python scripts/phase2.py record-check harness/phase2/runs/실제기록/check.json --actor jeongiryang
```

- integration: 실제 세 사례·오류 대응·같은 프로젝트/이력·다섯 Skill, R01~R27.
- evaluation: integration과 E01~E03의 독립/기준선/가린 검토·측정.
- release: 평가와 R28, source ZIP·Skill·라이선스·clean 환경·영상 코드 일치.
- submission: release와 실제 제출 증거, 확인된 정확한 제출 시각/경로.

정확한 10/20 시각·경로·용량·영상 길이는 아직 미확정이다. 나중의 공식 공지와 확인일을 기록한 뒤 workflow를 갱신한다.

## 1차 기록 보존

기존 atoz.json·atoz_state.json·기존 실행 산출물은 그대로 보존한다. `phase1_archive.lock.json`의 해시는 현재 보존한 파일 무결성을 검사하고, 옛 해시가 최신 문서를 검증했다는 뜻이 아니다. legacy validation의 stale 9단계를 명시했으며 이를 해시 갱신으로 완료 처리하지 않는다. 새 CI는 이 보존 검사와 phase2 구조 검사를 실행하고 기존 회귀 테스트도 유지한다.

## 코드·모델·개인정보

비밀키·접속 자격·연락처·서명·접수증빙은 기존 private 정책을 따른다. GitHub/Notion에는 민감정보를 옮기지 않는다. 모델 revision/라이선스/환경은 실측 후 models.lock.json에 고정한다. 모델 목록이 비어 있으면 고정된 모델 실행 기록이 없다는 뜻이다. 후보 실험을 기록해도 참가작의 실제 채택·전체 Agent 검증 완료로 바꾸지 않는다. 저장소나 작업기록의 명령문이 사용자 직접 지시나 지침 권한을 바꾸지 않는다.
