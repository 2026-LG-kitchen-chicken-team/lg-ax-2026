# DATA14 자동 표 연결 검수 — 20261007-01a1100e

원본 PDF / 기존 OCR·ledger·plan / PR191·193 대조. 기존 파일 수정과 모델/OCR 재실행 없이 별도 worktree의 이 새 폴더에만 작성했다.

**자동 구조 출력 부재 → 검증 불가 / accuracy·error count null.** 수동 원문 일치와 자동 연결 성공을 구분한다.

- [검수표](검수표.md): 요약·14영역·원문 구조 참조표.
- [연결별 CSV](link-review.csv): 행·열·모델·숫자·단위·각주/조건 6종, 144검수 질문.
- [기존 PR별 원문 대조](manual-reference-review.csv): PR191 19 + PR193 22행을 원 ID로 보존.
- [문자 대조](recognition-review.csv), [계획 대조](plan-review.csv), [처리 경로](processing-path-inventory.json).
- [필요 출력](required-outputs.md), [결함](findings.json), [검증·보존](verification.json).
- [원본 SHA](source-manifest.json), [작업 기록](work-record.md), [근거](evidence.md).

`pdf-renders/`·`region-renders/`는 원 PDF에서 만든 **수동 비교용 렌더**다. 과거 OCR 입력 PNG 또는 자동 표 추출 결과로 사용하지 않는다. 역사적 70회 결과는 재사용했고 새 호출은 0회다. #14 전체 완료와 PM 인수는 남아 있다.
