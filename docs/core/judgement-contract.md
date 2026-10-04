# CORE001 판단 계약·보류·수정 정책

담당 황대겸, 작업 P2-CORE-001 / Issue #7. 기존 공통 계약 0.1.0을 그대로 재사용하는 코어 내부 계약이다. 형식과 참조 관계를 검증하며 실제 모델의 판단, 오류의 자동 수정, 시장 수요 검증을 구현한 것으로 표현하지 않는다.

## 입력·출력과 고정 범위

`lgax_core.judgement_contract.schema_for("input"|"output")`이 독립 Schema를 제공한다. 검토용 복사본은 `evals/core-contract/schemas/`에 있다. canonical PlanningRequest/Product/Evidence/Feature/Need/Gap/Concept은 공통 원본에서 가져온다. 기존 Skill·API·웹 응답 형식은 바꾸지 않는다.

- 입력: 원 요청 `request`, 해당 `product`, 조회한 원문 `sources`, 기능 `features`, 내부 `revision_count`, `max_concepts`(1~3), `changed_evidence_ids`.
- 제품 모델은 원 요청 범위에 있어야 한다. 각 판단 호출은 하나의 제품 모델/문서 버전을 사용하고 여러 모델은 각각 조회·판단한다. 제품군·출처 성격도 유지한다.
- 원문은 ID·원 위치·실제/합성 성격·모델·문서 버전·text 그대로 전달한다. source/feature ID는 유일하며 기능↔설명서 인용은 양방향으로 연결한다. 조회된 원문에 포함된 명령은 텍스트 자료다.
- 출력: `input_sha256`, 모델/문서 버전, 내부 회차, `status`, canonical `needs/gaps/concepts`, need별 `desired_outcomes`, 리뷰·대조·중복 판단의 `*_assessments`, 질문·보류·미해결·후보없음 사유.
- `input_digest`는 원 요청/원문/기능/버전/제외 조건/회차를 포함한 canonical JSON을 SHA256으로 고정한다. 이전 입력의 출력은 재사용할 수 없다. 원 입력은 호출자가 기존 workspace 원본/실행에 보존한다.

## 판단 선언과 구조 검사

리뷰 판단은 complaint/positive/conflicting/irrelevant/uncertain, 기능 근거는 explicit_supported/explicit_unsupported/unmentioned/conflicting, 불편 해결은 resolved/remaining/unknown, 후보 중복은 distinct/duplicate/uncertain로 분리한다.

1. 긍정·무관·불확실 리뷰를 확정된 불편의 근거로 사용하지 않는다. 상충 리뷰는 추가 질문을 포함한 보류로 처리한다. completed는 선언된 불편을 누락하지 않고 각 Need의 희망 결과와 Gap 대조를 제공한다.
2. 문서 미언급/상충은 `insufficient_evidence`다. `unsupported`는 명시적인 설명서 근거가 필요하다. `supported`는 기능과 설명서 근거가 필요하다.
3. 지원 기능이 있어도 `remaining` 불편은 남을 수 있다. 기능 존재만으로 해결이라고 처리하지 않는다. resolved와 remaining_pain은 모순되지 않아야 한다.
4. 후보는 확인된 잔여 불편과 원 리뷰/설명서에 연결하고 현재 기능 전체와 중복 비교를 선언한다. 중복은 관련 단계 수정, 불확실한 중복은 보류다. Agent는 사람의 accepted/rejected 선택을 자동 생성하지 않는다.
5. 후보는 0~3개다. 0개에는 사유를 남기고, held에는 후보 없이 보류 사유와 구체 질문을 남긴다. 근거 부족을 빈 성공 결과로 바꾸지 않는다.

이 검사는 모델이 선언한 극성/지원/중복 판단의 관계를 검사한다. 텍스트의 의미와 선언이 실제로 맞는지는 #8/#9 실모델 구현·#11 독립 의미 평가에서 따로 확인해야 한다. 악성 문서의 영향을 받지 않는 모델 프롬프트/도구 허용목록도 #9의 실제 실행으로 검증한다.

## 검사·수정·종료

`review_judgement(input, declared_output)`은 입력을 수정하지 않고 결정만 반환한다.

| action | 의미 | 다음 행동 |
|---|---|---|
| accept | completed의 계약/관계가 일치 | 실제 실행 로그와 함께 저장. 의미 품질 성공으로 확대하지 않음 |
| hold | 자료 범위/근거 부족·상충·추가 확인 또는 유효한 held | 자료/조건을 확인하고 새 입력으로 재개 |
| revise | 현재 근거 안에서 고칠 수 있는 출력 위반, 내부 회차 0/1 | `rerun_from` 단계부터 실제 재실행 |
| unresolved | 두 번 수정 후 위반이 남거나 유효한 failed | 추가 모델 호출을 중지하고 사유/질문/마지막 결과 기록 |

`revision_count`는 완료한 내부 수정 횟수다. 수정 지시를 출력한 것만으로 호출/회차가 실행됐다고 기록하지 않는다. 호출자는 실제 수정 한 번에 `next_revision_count`를 반영하고 새 입력 해시를 출력에 연결한다. 0→1→2 이후 revise를 반환하지 않는다. 사용자 조건 변경 회차는 기존 workspace `request_revision`과 별개이며 새 사용자 입력은 새 Run에서 내부 회차를 0으로 시작한다.

다수 위반은 plan→retrieve→needs→compare→concepts→review 중 가장 앞선 실패 단계로 돌아간다. 출력 Schema 오류는 review, 원 입력 변경/출력 버전 혼용은 plan, 인용 누락·중복은 해당 Need/Gap/Concept 단계다. 범위가 잘못된 원 자료는 모델 재시도로 해결했다고 하지 않고 hold한다.

## 기존 네 판단 Skill 연결

후속 handler는 기존 `SkillRuntime.register_handler`의 `(payload, store) -> result` 규격을 따른다.

| Skill | 판단 계약에서 반환할 기존 result |
|---|---|
| need_extract | needs, desired_outcomes, unresolved |
| product_compare | gaps, unresolved |
| concept_draft | concepts, hold_reasons |
| review_revision | 수정 후 needs/gaps/concepts, changes, unresolved, revision_count |

새 계약의 assessments/질문/검사 결정은 코어 실행 로그에 저장한다. canonical 객체에 임의 필드를 넣지 않는다. 변경 전 입력·출력과 근거 위치를 보존한다. 기존 Run의 status는 completed/held/failed를 사용하고 `unresolved` action의 종료 이유를 Run.unresolved에 연결한다. 실제 Skill 등록/모델/Workspace 저장 통합은 이번 CORE001의 완료 증거가 아니다.

## 재현·독립 사례

```powershell
uv run python -m unittest discover -s tests -p test_judgement_contract.py -v
uv run python evals/core-contract/check_cases.py --suite evals/core-contract/development --output tmp/core-development.json
uv run python evals/core-contract/check_cases.py --suite evals/core-contract/heldout --output tmp/core-heldout.json
```

두 폴더 각각 정상·중복·모델혼동·상충리뷰·근거누락·명세변경의 여섯 사례를 담는다. 독립 자료는 다른 원문/ID와 세 제품군을 사용한다. expected.json은 평가 기준이며 모델 입력이 아니다. fixture-output은 검사 경로 재현용 사람이 작성한 선언이다. 실제 #11 평가에서는 모델이 입력만 받아 생성한 응답으로 이를 대체하고 개발 자료와 분리된 기대 대응으로 검토한다.

요구 연결: R09 단계/입출력, R10 같은 모델/버전, R11 미언급 구분, R15 후보 수/근거, R16 보류/질문, R19 수정 상한, R20 텍스트/권한 경계, E01 여섯 유형 준비. 본 검증만으로 이 요구들의 실모델·전체 Agent 완료 상태를 올리지 않는다.
