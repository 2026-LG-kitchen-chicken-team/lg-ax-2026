# DATA source-followup 자기 검수 근거

- 고정 main/PR262: `dc0ccc05916c637b2e0c2cc268a061dfa655c0b7`/`a6da6784db60e99645fd57017d37ba1403af9cd1`.
- [인수 버전·입력 SHA·경계](intake-and-boundaries.json) · [공개읽기 응답URL/시각/SHA](public-read-receipts.json).
- [기존PDF 모델/조건 locator 대조](native-model-locators.json): 원15PDF/624쪽 텍스트를 새 적용 범위 확인에만 읽음. 다운로드/OCR0. 판본·SHA·페이지 및 실제본문 모델 명시5개가 원자료와 연결됨.
- [후기 정상 공개UI 관측](review-browser-receipt.json): 원ID·DOM 날짜/본문 위치·본문SHA. 고객 이름·이미지/전문 제외.
- [최초 응답 수신증](first-read-receipts.json) · [임시 파일명 충돌 원 실패·교정](capture-namespace-failure.json). 첫6개 support raw가PDP 임시파일에 덮어써져 새support/ focused네임스페이스로6회 제한 재수령했다. 원PR259/레포PDF·원기록은 바꾸지 않았다. 최초 지원 응답SHA가 새응답SHA와 같다고 보고하지 않는다.
- [자료 경계 검증 코드](verify_sidecars.py) · [실행 검증 결과](verification.json).

검증은 자료와 승인 경계를 확인한다. 모델/실제운영/독립성·최종 PM 승인이나 전체#12 Done을 판정하지 않는다. 동일 입력의 기존 모델/225검색/OCR 실험을 재실행하지 않는다.
