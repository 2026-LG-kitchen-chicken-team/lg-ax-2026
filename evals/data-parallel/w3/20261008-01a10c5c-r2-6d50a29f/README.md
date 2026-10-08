# W3 원실행 인수·입력 전달 검수 — 01a10c5c-r2-6d50a29f



최신 main `eab85d48385f965eef48c07a6cdd8f6fd9851c62`에서 정상 `run-1f83d846191941aea21153897b944ec1`와 조건 변경 `run-754268c6b0cb41bba50c5b8d713332d9`의 기존 공개 보고를 인수했다. **원 JSON 실제 파일·원 출력 필드는 미수신**이며 선언 SHA와 보고된 값은 실제 측정과 구분한다.



새 확인: 현재 시작 설정의 원문 제한은 항목당1000자다. PM 검토가 지목한 고정 원문6개는63~550자/총1345자/UTF8 3213bytes로, 이 설정을 적용하면 추가 삭제0이다. 후기4개는 full, 설명서2개는 이미 excerpt이며 전체 설명서 전달로 해석하지 않는다. 원실행의 적용 코드·설정·stage prompt/native/wire를 받지 않아 **실제 모델 전체 입력 전달은 null/미확인**이다.



- [정상·조건 인수](run-intake.json) · [선언/실제 SHA 구분표](run-intake.csv)

- [입력 전달6경계·원문 길이 대조](input-delivery-audit.json) · [검수표](input-delivery-checks.csv)

- [정확 코드·자료 pin](source-pins.json) · [CORE 수신 재사용](receipt-reuse.json)

- [첫 원필드·ZIP·같은DB 인계 조건](remaining-handoffs.json) · [검증](verification.json)



현재 공개 HTTP10묶음의 CORE 인수는 재사용한다. 원 기획의 HTTP/MCP 같은결과·생성 당시 loaded text·native usage·같은DB 재시작을 이 자료 조회로 대입하지 않는다. PR285·287의 새 run-f0eb와 원문6 연결 및 메일도 재사용하며 동일 검수·요청 메일을 반복하지 않았다.



새 모델/OCR·완료225회/11문항·기존HTTP109/재시작51·자료producer 재실행0. 제품/자료/개인README·다른창파일 수정0. PM Gold/채점자·전송범위·운영승인·병합은 미완료다. 다음 하나는 기존 요청 경로로 정상run의 첫 승인 원필드/원JSON 인수다.
