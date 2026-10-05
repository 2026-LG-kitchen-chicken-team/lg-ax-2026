# CORE005 독립 의미 평가 입력·기록 재생 준비

여섯 유형의 합성 원문과 검토 기준을 자체 작성했습니다. 최초 입력 준비 Draft #57은 PM이 #64로 부분 인수하고 닫았습니다. 현재 사용자가 자동화 이전 미완료 범위의 실제 모델 검증·보완·일반 PR 제출을 직접 요청해, PM이 사용한 고정 Qwen 모델/설정으로 실행을 재개했습니다. 첫 실제 비교는 `evals/core-live-completion/20261005/independent-comparison-01/`에 있으며 의미 점수·승자·독립 PM 검수·CORE004 의존 해제/E01 완료는 선언하지 않습니다.

CORE001의 fixture-output은 검사기의 오류 경로를 재현하는 사람이 작성한 판단 선언입니다. 이 폴더는 그 선언을 실제 모델 결과로 사용하지 않고 새로운 원문·요청으로 의미 판단을 검토하도록 준비합니다. 개발·기존 heldout·CORE004 예제의 원문/ID를 재사용하지 않았습니다. 자동 중복 검사는 현재 checkout의 기존 계약/예제 파일과 정확한 ID·원문 동일 여부만 확인합니다. 의미적 독립성·문항 난도·기준 타당성은 PM이 따로 검토합니다. 자료는 실제 LG 제품 사양이나 시장 증거가 아닙니다.

| case | 유형 | 원문에서 검토할 차이 |
|---|---|---|
| SEM-01 | 정상 | 회전판 분리 기능은 있어도 아래 홈 청소 불편은 남음 |
| SEM-02 | 기존 기능 중복 | 요청한 60초 문 열림 소리 알림이 이미 명시됨 |
| SEM-03 | 모델/버전 혼동 | 다른 모델/9.0의 조절 기능을 요청 모델/1.0에 적용할 수 없음 |
| SEM-04 | 상충 리뷰 | 같은 코스·적재 조건의 서로 반대되는 건조 리뷰 |
| SEM-05 | 근거 누락 | 시각 알림 여부를 확인할 설명서/기능 자료가 없음 |
| SEM-06 | 명세 변경 | 식기세척기1.0 수동 확인에서2.0 외부 검사 상태 표시로 변경 |

## 파일과 재현

- `manifest.json`: PM의 `scripts/prepare_evaluation.py`가 사용하는 여섯 유형 manifest 형식입니다. request는 실제 CORE001 전체 입력, data_path는 입력/대응 dataset(SEM-06은 변경 전 입력/자료도 포함) 파일입니다. 최종 출력 계약은 기존 CORE001 schema를 참조합니다.
- `materials/*.json`: 모델에 제공할 요청·원문·현재 자료·이전 입력만 담습니다. 서로 다른 모델을 잘못 섞은 SEM-03은 의도적인 scope 오류이며 이를 고치지 않습니다.
- `reviewer-only.json`: 모델에게 제공하지 않는 의미 검토 기준입니다. 실제 결과·평가·모델 필드는 null이며 검토 전 점수나 정답 결과로 채우지 않습니다.
- `prepare_inputs.py`: 실제 입력/Schema/자료 일치·기존 원문 분리와 여섯 유형을 검사하고 모델용 JSON·PM의 강한 단일 프롬프트 초안을 채운 baseline txt·원 바이트 해시를 새 폴더에 저장합니다. 기존 실행 파일이 있는 폴더는 거절합니다. 모델 호출·가린 검토·점수 산출을 하지 않습니다.

```powershell
uv run python -m unittest discover -s tests -p test_semantic_inputs.py -v
uv run python evals/core-semantic/prepare_inputs.py --output-dir tmp/core005-inputs-new
```

생성된 baseline은 전체 요청/자료/결과 Schema를 포함합니다. 독립 검토 기준/fixture-output은 넣지 않습니다. inventory의 `baseline_file_sha256`는 실제 txt 바이트 해시입니다. PM 결과 계약의 `method_setup.prompt_sha256`는 실제 전송한 문자열을 JSON canonical 방식으로 해시한 값이므로 파일 해시를 그대로 복사하지 않습니다.

### 실제 비교용 입력 길이와 실행

기본 `inline` 모드는 기존 출력과 동일합니다. `--baseline-contract-mode client_schema`는 전체 원문/자료를 compact JSON으로 전달하고, 결과 Schema는 모델 클라이언트의 형식 지침과 native `format`에 제공하는 동일한 전체 계약을 사용합니다. Schema를 삭제하거나 원문을 잘라 기준선만 짧게 만드는 방식이 아닙니다. 출력 Schema가 두 번 들어가던 초안은 일부 사례에서 16000자 전송 제한을 넘었으므로 실제 비교는 이 모드를 별도 새 폴더에 고정합니다.

```powershell
uv run python evals/core-semantic/prepare_inputs.py --baseline-contract-mode client_schema --output-dir tmp/core005-frozen-new
uv run python evals/core-semantic/run_comparison.py --frozen-inputs tmp/core005-frozen-new --output-dir private/core005-live-new --gpu-identity "사전에 확인한 GPU/기존 서비스의 식별 정보"
```

실행 전 모델 환경변수는 승인된 동일 endpoint/model/digest와 실제 출력·문맥·thinking 설정으로 명시적으로 준비합니다. 이 도구는 모델을 선택·다운로드하거나 원격 서비스를 시작/종료하지 않습니다. GPU 식별 정보는 먼저 실제 상태/기존 서비스 설정으로 확인한 값을 전달하며 도구 자체가 GPU 배정을 증명하지는 않습니다.

`run_comparison.py`는 먼저 고정 입력/원 자료/기준선/계약 해시를 대조하고 새 출력 폴더만 허용합니다. 같은 모델·자료·예산으로 두 방식을 순차 실행하며, scope 오류의 호출0·수정/재시도·실패도 보존합니다. SDK의 실제 생성 경로 진입과 반환한 원 응답을 별도로 기록해 호출/토큰을 합산하며, 반환 응답이 없어 토큰을 모르면 `null`을 유지합니다. baseline은 한 번의 전체 프롬프트이고 Agent는 기존 단계/최대2회 수정 정책입니다.

결과 bundle의 `success`는 실행 결과를 반환했다는 의미이며, Agent의 `held`가 정상 후보 완성을 뜻하지 않습니다. 기준선의 Schema 통과도 극성·지원·잔여 불편·중복 의미 정확도의 증거가 아닙니다. 작성자 관찰과 결과 생성에서 독립된 검수/점수를 구분합니다. 방식 이름이 포함된 원 결과를 독립 검토자에게 그대로 보내면 가림이 깨지므로 PM이 원본과 별도 검토 파일의 공유 경로를 결정해야 합니다.

## PM 실제 실행·검토 인수

1. #54/#55/#56 판단/수정/재실행 코드와 자료 담당 결과를 검수·통합합니다. PM이 최종 입력/출력 계약·고정 모델 digest·샘플링·충분한 출력/문맥 예산과 실제 전달 자료를 고정합니다. 최종 계약이 바뀌면 이 pack을 조율한 뒤 다시 고정합니다.
2. Agent에는 `materials.input`과 `materials.dataset`을 사용합니다. baseline은 생성된 txt 전체를 같은 모델/자료/계약 조건으로 전달합니다. 두 방식 모두 평가 기준을 읽지 않습니다. 생성 JSON은 입력 준비 artifact이며 외부 결과 record가 아닙니다. 반복 수·실제 호출 조건은 PM 평가 프로토콜에 기록합니다.
3. SEM-03은 모델 호출 전에 scope 검사가 실패/보류할 수 있습니다. 실패와 model_calls0도 기록하고 성공 결과만 추려 넣지 않습니다. 같은 잘못된 입력을 baseline에 제공하며 두 방식의 오류/판단 차이를 검토합니다. fixture preflight 위반은 실제 LLM 저항성의 증거가 아닙니다.
4. SEM-06은 previous 입력/자료로 before 실제 실행을 별도 보존하고 현재2.0 입력/자료로 after를 실행합니다. 이전 결과를 after의 정답으로 재사용하지 않습니다. Agent가 이용한 이력/자료 풀과 baseline 전달 자료가 다른 경우 동일 조건 비교로 승인하지 않고 공통 평가 조건을 다시 고정합니다. before·수정·재시도 호출의 측정 포함 범위를 선언합니다.
5. 각 원 응답·실패·도구/모델 호출/수정 trace·코드/자료/모델 버전과 미측정 null을 보존합니다. `reviewer-only.json`의 기준에 대해 **실제 원문과 결과**를 대조한 독립 검토 기록을 새 파일로 작성합니다. `review_judgement` 계약 통과만으로 극성·기능 존재/해결·중복·보류 의미가 맞다고 채점하지 않습니다.
6. 기준선 비교 결과가 있을 때 [PM 평가 도구](../../docs/pm/evaluation.md)를 사용해 같은 manifest와 실제 두 결과 묶음을 가린 검토로 넘깁니다. E01 여섯 유형 의미 검증, E02/E03 일반 LLM 비교/토큰 평가와 전체 Done은 각 실제 근거 후 별도로 판정합니다.

PM이 실제 실행·검수 중 확인한 의미 실패는 담당 코어의 후속 수정으로 처리합니다. 아래 기록 재생은 그 실제 실패를 고정하는 회귀검사이며 여섯 유형 독립 평가를 대신하지 않습니다.

## 기존 실제 응답의 로컬 재생

`replay_reviews.py`는 PM의 기존 실행 JSON 또는 `workspace-live.json`의 두 저장 실행을 읽어 현재 `review_semantics` 검사기로 재생합니다. 모델·서버에 접속하지 않으며 원 응답·후보·판정을 교정하지 않습니다. 원본 파일/검사기 해시, 원래 상태·실패·호출·토큰 수, 당시 판정과 현재 검사 결과를 새 파일에 보존합니다. 실패 호출과 의미 검토에 도달하지 못한 보류도 제외하지 않고 토큰 누락은 null로 남깁니다.

검토 당시 `reviewed_input`/`reviewed_output`이 있으면 그대로 사용합니다. 과거 거절 응답에는 후보 전체 snapshot이 없어 성공한 Skill 기록과 해당 원 선언을 대조해 복원하며, 전체 입력·출력 canonical SHA-256이 원래 검토의 해시와 정확히 일치할 때만 재생합니다. 실패한 후속 수정으로 과거 후보를 대체하지 않습니다. 원 응답/선언/저장 검토/trace가 다르거나 해시가 어긋나면 실행을 거절합니다. 기존 출력 파일도 덮어쓰지 않습니다.

```powershell
$records = Get-ChildItem evals/pm-review/20261005-round2/live-lg-final/*.json | Where-Object Name -ne 'summary.json' | ForEach-Object FullName
$records += (Resolve-Path evals/pm-review/20261005-round2/api-live/workspace-live.json).Path
uv run python evals/core-semantic/replay_reviews.py --record $records --output tmp/recorded-reviews-new.json
uv run python -m unittest discover -s tests -p test_semantic_recorded_reviews.py -v
```

이 9개 원 실행은 개발/제외 조건 pack과 API 저장 검증이며 SEM-01~06의 실제 결과가 아닙니다. 새 모델 호출은 0입니다. 원래 인용 오류가 계속 거절되고 저장 보류 판정이 동일한 것은 검사기 회귀의 근거입니다. 모델이 새 수정 callback을 성공시킨다는 증거나 의미 판단 품질 점수·기준선 비교·CORE002~005 Done으로 사용하지 않습니다.
