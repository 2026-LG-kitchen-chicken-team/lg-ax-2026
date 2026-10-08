# DATA W3 기존 변경97dbc 실제 파일 인수

WEB의 기존 전체 공개 job response를 7,425bytes와 실제 SHA256 `e008c91fd9d1de097e6b377f0d546ce021bb686dbf23f49ed0504dcca060b6aa` 그대로 보존했다. result 정규화 SHA `bc72af4bc89943d89783c3a8f8c9dab0820578b6fa53c2a7d0ac8a0696f3c592`는 파일 SHA와 별개다. 게시 commit a90196b은 생성 프로세스 commit 증거가 아니다.

[원파일](run-97dbc649.job-response.json) · [실제 수신증](intake-receipt.json) · [기존 정상5ccd와 부모·조건·10필드 대조](public-result-lineage.json) · [W1 실제 인수·검수 재사용](W1-receipt-reuse.json) · [수신·전송·운영 관찰 범위](execution-observations.json) · [자기 바이트 보존 확인](verification.json)

정상 brief0c4a에서 변경 brief4526으로 revision0→1, bundle/model digest/input scope/선택6 ID/source_facts6이 유지됐고 하드웨어 변경 금지 조건이 추가됐다. source_facts 각 facts는 빈 배열이며 출력에 남은 ID와 값의 보존을 확인한 것이다. 생성 당시 prompt나 provider 실제 입력 전체가 검증된 것은 아니다.

W1은 이 파일의 C06–C08 공개 값 미수신 범위를 해제하고 기존17/8행·CORE 판정을 재사용한 PR294의8범위/54필드 검수를 게시했다. W3는 의미 채점을 반복하지 않았다. 결과 생성은 CORE 보완 전이며 현행 수정 효과, Gold, PM 승인·병합·부모 Done은 미확인이다.

요청한 원1f83/754268은 선언 SHA·일부 보고만 수신했고 실제 JSON/생성 로그/whole-input은 미수신이다. 기존 sender ZIP은11106bytes/11entries/SHA e73d3393…로 준비됐지만 승인 경로·정확수신자·PC 대응·input-only 범위와 receiver 원파일은 미수신이어서 전송0이다. Gold/최종 채점자 결정은 입력 ZIP 인수 조건과 별개다. 실제 HTTP/MCP 원envelope·동일 운영 DB 행·같은 DB 재시작 전후 원캡처도 미수신이며 공개 결과와 격리 검사를 대체 증거로 쓰지 않았다.
