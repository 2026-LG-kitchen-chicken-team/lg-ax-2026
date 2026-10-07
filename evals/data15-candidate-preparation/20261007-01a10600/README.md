# #15 독립 평가 후보 분리와 노출 검수

확인 시각: 2026-10-07T11:43:43.862923+09:00. [PM 지시](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/15#issuecomment-6029601114)에 따라 기존 공개 8입력/7heldout은 개발 진단·회귀 자료로 보존하고, 새 독립 평가 분모에서 제외한다. 기존 노출이 사라졌다는 뜻이 아니다.

새 합성 6유형과 조건 변경 전 입력 1개를 본인 private에 준비했다. 입력·검토자 전용 기대 대응 초안·시연 참조를 서로 다른 폴더와 ZIP으로 분리했다. 실제 LG 사양이나 실제 고객 후기로 표시하지 않았다. PR에는 원 입력·답안·상황 서술·ZIP을 올리지 않고 manifest/hash/검수 결과만 포함한다.

[관찰한 검사](candidate-validation.json)는 입력 schema 7/7 PASS, 27개 참조 자료에 대한 canonical 입력·근거 ID·NFKC/공백 정규화 본문 중복 0이다. 최신 main `8ec1e8a51faabd6db032e52245680bef4229f93f`의 입력 schema도 검사 당시와 정확히 같은 bytes임을 [확인](PM-disposition-and-current-schema.json)했다. exact 중복 0은 의미 독립성이나 과거 튜닝 노출 없음의 증명이 아니다.

PM이 인계한 실제 후기 evaluation 36개는 별도 [후보 인수표](R5-evaluation-36-intake.json)로 대조했다. [내부 ID/본문 분할과 과거 노출 대조](R5-split-and-exposure-check.json)에서 확인한 참조에 대한 평가 분할 노출은 0개다. 다만 정확 구매 SKU·게시일 확인이 0개여서 제품 판단 입력/Gold는 승인되지 않았다. 공개 자료의 후보 인수와 독립성 승인을 구분한다.

CORE는 source→기능 지원→잔여 불편→확인 질문의 원문 매핑·반례 대조를 맡는다. 최종 독립 채점자는 PM이 작성자/코드·정답 작성에서 분리해 지정한다. 담당자·비공개 최종 검토 경로·Gold/의미 타당성·실제 독립 채점은 미완료다. 원문/답안을 개발·튜닝에 전달하지 않았다. 새 모델 실행 0회다.
