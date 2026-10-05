# 독립 검토자에게 전달할 가린 파일

같은 최종 코드·자료·모델·설정의 실제 Agent/단일 프롬프트 결과를 방식 이름만 A/B로 가렸다.
이 폴더의 review.json·빈 scorecard.json 및 ../fresh-holdout-suite/materials만 검토자에게 전달한다.
원 실행 bundle·개발 진단·비공개 방식키는 검토 중 제공하지 않는다. 원 자료가 합성임을 알린다.
키는 private/manual-core-completion/independent-review-keys-fresh.json에 별도 보존하며 공개 Git에 넣지 않았다.
PM이 결과 작성과 독립된 검토자/공유 경로를 선택하고, 채점 후 원 결과와 방식키를 대조한다.
도구의 preparation 통과는 파일 해시·선언 조건 일치일 뿐 실제 품질 점수·독립 검수 완료가 아니다.
