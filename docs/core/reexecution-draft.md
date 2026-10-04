# CORE004: 조건·명세 변경 후 재실행 준비

LLM 연결 및 실제 모델 실행·검증은 미완료이며, 사용자 지정에 따라 PM 정이량이 이 Draft PR을 이어받아 진행합니다. 이 문서는 #10의 부분 코드·합성 입력 인수 안내입니다. CORE003 의존 해제, 세 제품의 실제 모델 의미 판단, CORE004 완료 근거가 아닙니다.

`lgax_core.reexecution.prepare_reexecution(previous, current)`는 CORE001 입력 두 개의 계약·제품/근거 참조를 검사하고 요청, 제외 조건, 제품, 원문, 기능, 버전과 후보 상한의 실제 차이를 비교합니다. 원 입력/이전 결과를 수정하거나 모델을 호출하지 않습니다. 반환값의 `prepared_input`은 깊은 복사이고 세 입력 해시는 이전·제공·준비 입력을 구분합니다.

| 변경 | 처음 다시 확인할 단계 | Workspace 처리 |
|---|---|---|
| 고객·사용 상황·과제·제외 조건 | plan | 고정 자료/제품 범위 안에서 새 run |
| 원문/기능 내용·추가·삭제 | retrieve | 현재 불변 자료 scope 규격상 새 project 필요 |
| 제품 모델·문서/자료 버전 | plan | 새 project 필요 |
| 원문/기능 배열 순서 | retrieve | 새 run |
| 후보 상한 | concepts | 새 run |
| 내부 수정 회차·변경 ID 선언만 변경 | 재실행 없음 | 이전 입력/회차 유지 |

여러 변경이 있으면 가장 앞 단계부터 권고합니다. 원문 내용과 함께 요청의 dataset_version도 바뀌면 plan부터 시작합니다. `stages`는 재실행 계획이며 실제 단계 실행 증거가 아닙니다. 부분 단계 실행에는 검증된 이전 결과/cache가 필요합니다. CORE002의 전체 pipeline으로 재실행해도 됩니다. 문서 버전이 바뀌면 모든 근거/기능의 버전이 현재 제품과 일치해야 합니다.

실제 변경 또는 호출 코드의 `explicit_new_run=True`에서 새 run의 수정 회차는 0부터 시작합니다. 이 bool은 담당자의 명시적 반복 실행을 표현하는 호출자 인수이며 문서·모델 출력에서 읽지 않습니다. 이 함수는 인증을 수행하지 않으므로 PM API가 owner 권한과 실제 이전 run을 조회해야 합니다. 원 요청이 그대로인데 회차만 0을 제출하거나 변경 ID만 선언하면 이전 회차를 유지합니다. `changed_evidence_ids`는 실제 추가/변경 원문의 ID로 다시 계산하고 삭제 ID는 `changes.evidence.removed`에 따로 기록합니다.

## 재현

```powershell
uv run python -m unittest discover -s tests -p test_reexecution.py -v
uv run python evals/core-reexecution/plan_examples.py --output tmp/core004-plans.json
```

`evals/core-reexecution/examples/`의 before/after 입력·dataset은 모두 자체 작성 합성 자료입니다. CORE001 독립 평가 사례를 사용하지 않았습니다. 각 dataset의 근거/기능은 대응 입력과 일치하며 기대 분석 결과는 포함하지 않습니다.

- 냉장고: 자동 세척 장치 제외 조건 추가. 같은 자료로 새 요청 실행을 준비합니다.
- 식기세척기: 긍정 리뷰 추가. 기존 불편과 함께 현재 자료에서 다시 판단해야 합니다. 추가 리뷰를 곧바로 해결 증거로 처리하지 않습니다.
- 전자레인지: 수동 가열에서 냉동밥 자동 가열 코스로 명세/문서 버전 변경. 기존 후보의 중복 여부·잔여 불편을 새로 판단해야 합니다. 실제 의미 결과를 미리 정하지 않습니다.

## PM이 이어서 실행할 범위

1. #54/#55의 모델/수정 코드를 검수·연결하고 승인된 endpoint·digest·예산으로 실제 실행합니다. 이 PR은 모델 설정을 추가하지 않습니다.
2. 세 before/after 입력 각각에 대응하는 dataset을 사용합니다. `new_project_required`이면 새 project를 만들고 이전 project의 자료 SHA를 교체하지 않습니다. 서로 다른 project 사이에서 기존 previous_run_id를 사용해 Workspace의 scope 검사(409)를 우회하지 않습니다. 비교 연결이 필요하면 PM이 공통 계약을 조율합니다.
3. before 실행의 실제 입력·결과/원문/모델 trace를 보존합니다. after는 준비 입력을 새 실행에 전달하고 별도 run으로 저장합니다. 요청 이력의 `request_revision`과 Agent 내부 `revision_count`를 구분합니다.
4. 후보 변화·기존 기능 중복 제외·보류 질문·최대2회 수정 및 새 명세의 근거를 원 출력과 비교해 기록합니다. 예제가 자동으로 기대 대응을 지시하거나 품질을 채점하지 않습니다.
5. 실제 생성/도구/수정 로그와 코드·자료·모델 버전을 연결한 live_model 근거를 제출하고 PM 검수→병합→통합 확인을 진행합니다. fixture 계획/단위 검사만으로 #10을 finish하지 않습니다.

Workspace/API/MCP/웹 반영과 실제 영향 비교 화면은 PM/웹 담당의 통합 범위입니다. 현재 helper는 이전 후보의 의미 변화나 수요·효과를 입증하지 않습니다.
