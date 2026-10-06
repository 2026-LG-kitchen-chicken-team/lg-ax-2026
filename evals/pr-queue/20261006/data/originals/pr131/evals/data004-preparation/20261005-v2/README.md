# #15 충돌·명세 변경·근거 검수 준비

검사 기준10개와 개발용12사례(6유형별2개)를 작성했다.
정답 초안이며 PM 의미 검토와 실제 Agent/변경 서비스 실행은 미실행이다.

| 사례 | 유형 | 준비할 검수 |
|---|---|---|
| DATA004-DEV-N01 | normal | 선반 분리·청소 안내의 근거를 조회한다. |
| DATA004-DEV-N02 | normal | 바구니 조절 전 조건과 노즐 확인을 함께 조회한다. |
| DATA004-DEV-DU01 | duplicate_feature | 수동 출력 선택을 신규 기능으로 제안한다. |
| DATA004-DEV-DU02 | duplicate_feature | 시작 버튼의 30초 추가를 신규 기능으로 제안한다. |
| DATA004-DEV-MV01 | model_version_confusion | 냉장고 입력에 실제 다른 모델의 바구니 근거가 섞인다. |
| DATA004-DEV-MV02 | model_version_confusion | 개정번호가 없는 이전 설명서의 설치 간격을 요청한다. |
| DATA004-DEV-CR01 | conflicting_reviews | 합성 후기의 반대 의견을 빈도로 일반화하지 않는 개발 점검이다. |
| DATA004-DEV-CR02 | conflicting_reviews | 합성 후기의 다른 식기 조건을 동일 조건의 모순으로 합치지 않는다. |
| DATA004-DEV-ME01 | missing_evidence | 사용자 조합 저장·호출을 자동 메뉴로 대신 확정하지 않는다. |
| DATA004-DEV-ME02 | missing_evidence | 개인 식기의 치수·수량·배열 정보가 없는 적재 판단이다. |
| DATA004-DEV-SC01 | specification_change | 바구니 단계 수를 변경한 합성 명세의 영향 추적 준비다. |
| DATA004-DEV-SC02 | specification_change | 고주파 출력만 변경한 합성 명세에서 소비전력을 보존한다. |

실제 원문 충돌 C01(벽면 간격/적용 범위)·C02(출시년월)는 real-conflicts.json에 원본 관찰값·미해결 상태 그대로 보존했다.
상충 리뷰 유형의 입력4개는 합성 개발 fixture이며 실제 고객 리뷰는0개다. 원문은 private에 두고 공개 자료로 제시하지 않는다.
명세변경2개는 DEV-SPEC 합성 입력이다. 실제 제조사 개정·모델 사양 변경을 확보했다고 하지 않는다.
각 변경의 before/after snapshot/hash·새 source ID·조건과 영향 받을 판단/후보·보존할 사실을 나눴다.
개발 사례/기대 답안은 private/data004-development에 재생성하며 비공개 최종 독립 평가 경로를 읽거나 수정하지 않는다.
review-results-template JSON/CSV는 미실행/결과 null이다. 이 준비를 E01 독립6유형 평가 완료로 사용하지 않는다.

## 진행 체크리스트

- [x] 모델/버전/원문·조건·충돌·미확인·변경 영향·독립성 검사 기준 작성
- [x] 기존 실제 충돌2개 보존, 개발12사례·미실행 검수표 작성
- [ ] PM의 개발 기대 답안 의미 검토·자료 인수
- [ ] #13 실제 처리 출력으로 source ID/버전·근거 연결 검증
- [ ] 황대겸의 변경 재검토 서비스와 실제 영향/수정 결과 대조
- [ ] PM/평가 담당의 별도 독립6유형 실행·검토 및 최종 완료 판정

재현: 기존 Python3.11에서 scripts/prepare_data004_review.py 실행. 기존 출력이 있으면 덮어쓰기를 거부한다.
