# WEB W1 실제 출력 잔여 수정 — CORE

WEB PR268 `fe79561a85ad56466d6bb1d34e5250bdc8d4c913`의 기록071에서 정상 실행의 실제 job 응답과 조건 수정 실행의 복사된 일부 필드를 받았다. 신규 CORE 모델 호출은0이다. 실제 원응답·수정 필드·원 실패를 유지하며, 오프라인 stub 검사를 모델 품질 승인으로 바꾸지 않는다.

- [원 job 응답](run-5ccd95da.job-response.json): `run-5ccd95da25934e5789951fb1402e95ba`, 원 파일 SHA256 `f8fdcb43e5b8d3a433869be3678b01150086be21ed0a04651fa0d82ba5100e06`.
- [WEB 원 기록/수정 필드](results.json): `run-97dbc6493b964100ab0d0ff5037fa0ed`의 전체 응답은 아직 받지 않았다. 이를 정상 응답과 합쳐 실제 수정 응답인 것처럼 저장하지 않았다.
- [원문·결과 대조](source-result-review.json) · [입력 고정](bundle-source-pin.json). 입력은 `data/research/r9-public-runtime-20261008/fridge.research-bundle.json`, SHA256 `523dcf1ec8e4291dc73bd0b51cea0be4765912e9e5b7993cf1d55af389876655`다. 실제 선택6 facts와 결과의 facts6이 일치한다. 전체 번들58과 실행 선택6은 구분한다.

W1-F1: 수정 조건에 ‘하드웨어 변경 없이 개선’이 있는데도 mechanism과 proposed_changes가 냉동실 턱 구조 조정·대체 및 높이 재설계를 남겼다. 기존 생성/항목 수정 검사는 센서 추가·기기 제어 등을 확인하지만 구조 변경을 놓쳤다. 두 경로가 공유하는 명시적 구조 변경 검사를 보완했다. ‘새 부품 추가 없이’가 뒤의 턱 재설계를 가리지 않도록 부정 표현은 해당 변경 행동에 적용한다. 정상 이웃·실패 원 응답, 항목당 한 번·공유 수정 최대2는 유지한다. 일반 의미 판단이나 전자동 수정·승인이 아니다.

W1-F2: `existing_response`가 기존 해결 방식 대신 ‘슬라이드 용기 사용 불가’라는 불편을 반복했다. 관련 지침은 확인된 기존 대응·실제 대처와 남은 부담을 분리하고, 대응 자료가 없으면 미확인으로 표시하도록 보완했다. 사실을 새로 만들거나 출력 의미를 기계적으로 치환하지 않는다.

W1-F3: 797084의 ‘이전과 비교해 소음이 있다/소리가 들린다’를 ‘소음이 크다’로 강화하지 않는다. 801970의 설치기사 친절과 얼음 지연 관찰은 각 맥락을 보존한 혼합 의견으로 다룬다. 해당 지침을 보완했다. 767601의 문이 덜 닫힌 채 한 시간 지났다는 후기는 원문에 있지만 요약에서 인용되지 않았다. 집계3/4=.75는 정확하며, 집계 성공을 분류 승인이나 시장빈도로 확대하지 않는다.

X1 부분 검토: 정상 기획의 구조 변경은 미래 가설이며 정상 조건이 하드웨어 변경을 금지하지는 않았다. 수정 제목을 ‘가이드’로 바꿔도 구조 변경 mechanism은 해소되지 않는다. F08은 적용 모델에 한정된 냉장실 접이선반 안내이며 냉동실 턱 해결 근거가 아니다. F12는 일반 통풍 간격 안내이며 이 고객의 실제 설치 상태나 얼음 지연 원인을 입증하지 않는다. 구매 SKU 미확인·발췌 범위를 보존한다. 관계2개의 `inferred: true`는 인과·해결 확정을 뜻하지 않는다. 사용하지 않은 설명서를 억지로 인용하지 않는다.

WEB은 기획JSON/Markdown·스토리보드JSON/Markdown의 Blob 내용, 복원 및 canonical hash 일치를 보고했다. CORE는 원 결과 canonical SHA256 `dbb239d1dbe7aa91dec4b4da6903ed79a92ad1732497cc3cb74063b14c1f44bf`를 직접 대조했다. 실제 내보내기4파일·전체 수정 응답·동일 HTTP/MCP·PM 인수는 미수신/미검증이다. 공식 제품 안내서의 기존 별도34검사 근거는 재사용하며 새로 실행하지 않는다.

격리 검사와 원 실패는 `baseline.log`, `baseline-receipt.json`, `first-public-core.log`, `first-ruff.log`, `first-after-check-receipt.json`에 보존한다. 수정 전 실제 복사 필드가 accepted인 결함을 재현했다. 첫 수정 검사에서는 합성 정상 이웃의 필수 장면 필드 누락과 테스트의 loop-variable lint를 고쳤다. 최종 검사 수신은 같은 폴더의 별도 검증 파일로 기록한다. 테스트의 부분 재구성은 TEST ONLY이며 실제 수정 응답·새 모델 결과가 아니다.

최종 관련42검사(신규 회귀4 포함)와 Ruff PASS. [검사 수신](final-after-check-receipt.json) · [검사 로그](final-public-core.log) · [고정 소스/격리 조건](verification-context.json). 실제 모델 효과와 PM 채택은 미검증이다.

규칙 동등·문서 navigation PASS. 원 이관36 Git blob/현재 바이트를 읽기 전용 대조하고, 같은 바이트의231구간·818663B·세션28을 Docker에서 검증해 PASS했다. 최소 소스 복사에는 .git이 없어 첫 CLI --verify는 실행 경계 오류였다. [원 경계 실패](first-member-log-migration.log) · [고정 Git 원바이트 대조](source-git-byte-receipt.json) · [동일 원바이트의 최종 격리 검증](final-member-log-final-receipt.json).
