# W2 자료 검수 — DATA-W2-01a10600-9e2b7c

설치 Q&A470877의 발췌 밖 원답변을 이번 DATA 창에서 직접 확인해 PR282 W2-R2-06의 수치·조건 미확인을 보완했다. 개인 README·원자료·다른 창 파일을 수정하지 않은 새 검수 sidecar다.

- [설치 검수표 JSON](qa470877-inspection.json) · [CSV](qa470877-inspection.csv): 원 질문119~120mm, 안쪽600mm, 문 앞590mm, 조건부567~600mm·배관 눌림 위험·설치 엔지니어 확인. 질문 단위 해석과 특정 사용자의 설치 가능 여부는 null이다.
- 공식 원답변 위치는 `li[data-que-no="470877"] div.answer-content`. 캡처 `2026-10-08T13:42:09.694116+09:00`의 HTML SHA `1941dbeb99f2cab9a595240f3fcbe0576a71437e4699204119296877b0c7f487`는 CORE 보고 해시와 일치한다. DATA가 CORE의 원파일을 받았다고 주장하지 않고 직접 GET·계산한 SHA와 CORE의 보고를 구분한다. 원 HTML·본문 전문은 private 보존이며 공개 표에는 짧은 발췌와 URL·위치·SHA만 있다.
- [자동 표 인수](automatic-table-intake.json): 실제 graph/승인 adapter 추가미수신. 자동 비교 검증 불가, 정확도/오류수 null. 수동54축·기획 graph·경쟁 source adapter를 자동 표로 대체하지 않는다.
- [분류·날짜 인수](trend-approval-intake.json): 기존238/개발141·292인용·36빈집계는 기존 검사 재사용. 분류 승인/지적 Source ID·정확 구매SKU·구매 당시 판본·날짜 의미 미수신. 새 후보 합산0·월/계절 분모0·ratio null.
- [정확 Source ID·소비 receipt](source-consumer-receipt.json): 경쟁12/김치6/광파4/Q&A4 원 pin과 CORE의 읽기/참고 기록 인수를 연결한다. 새 PM PR284의 기존 `run-f0ebcae46f5e4bbd8f087161fd801ce5` 선택6 ID는 받은26 ID와 겹침0이다. 이 한 실행에 선택되지 않은 사실만 확인했고 다른 실행 전체의 소비0을 확정하지 않는다. W1의 답변 의미·W3의 DB/메일 검수는 수행하지 않았다.
- [공용 문서 조건](manual-condition-followup.json): CORE 추가 확인5쪽은 담당자 보고로 구분해 재사용한다. ML32 외부 표면과 조리실·법랑접시의 수세미 지침을 다른 대상으로 유지하며 정확 구매SKU/구매 판본·runtime 승인과 구분한다.
- [확인·상충·미확인](findings.json) · [고정 입력](input-pins.json) · [수행/원 실패](work-record.md) · [검수 실행](verification.json) · [보존·범위](scope-preservation.json).

원 main `eab85d48385f965eef48c07a6cdd8f6fd9851c62`, PR280/282의 기존1,101/53검사·225회 실험·11문항 재채점·PDF100쪽 반복을 실행하지 않았다. 새 모델/OCR·운영 서버/DB/API·ZIP·메일·자동화 ON·추가 비용0이다.

다음 작업 하나: PM/producer가 기존 #14 요청6050704556에 실제 graph와 승인 adapter pin의 첫2페이지 출력을 인계하면 해당 셀·모델·단위·각주·bbox 연결부터 원 PDF와 대조한다. 일부 인계가 다른 산출물 전체 완료를 기다릴 필요는 없다. PM 인수/병합/전체 Done은 미완료다.
