# R9 DATA 무결성·원문 위치 독립 검수

기록 ID: DATA-R9-INTEGRITY-20261008-01a11628-90a402 · 담당 신진하/ginaginaring · 기준 main `dc0ccc05916c637b2e0c2cc268a061dfa655c0b7`.

## 결과와 범위

**입력/인용 무결성 PASS.** PR246의 기존 238건 감사·원문 보존·Excel·가드 검사를 재사용했다. 해당 감사 5파일 및 당시 생산 membership/manifest가 현재 main과 원바이트로 같다. 전체 DB·Excel 감사를 다시 실행하지 않았다. PR254 고정 입력부터 R9 변경분만 확인했다.

| 대상 | 이번 직접 대조 |
|---|---|
| 냉장고 | Source58 / 개발 후기48 |
| 식기세척기 | Source73 / 개발 후기48 |
| 전자레인지 | Source53 / 개발 후기45 |
| 합계 | Source184 / 개발 후기141, ID 중복·새 분할 혼입 없음 |
| R9 변경 | bundle ID3개 + 식기세척기 continuation_pages5곳만 변경 |
| 관리14 | 원 PDF SHA·native 본문·페이지/문자 위치·판본·기존 감사 발췌 모두 일치 |
| 설명서 참고5 | 원 PDF4개 실제 bytes 수신, 표지/쪽12·본문/위치/hash·선택 catalogue·PM PDF 수신 receipt 일치. 개발184와 별도, 후기0 |

ID·본문·facts·판본·분할·미확인 값은 위 선언된 변경 이외에 동일하다. 141 후기는 기존 development ID 집합과 정확히 같으며, 구매 SKU/리뷰 게시일 null·노출/보류 사유가 유지된다. 238건의 분할141/36/49/12는 기존 감사의 고정 membership과 일치한다.

검수 결과 [result.json](result.json), [184개 Source 대조표](source-delta.csv), [19개 인용 대조](citation-checks.json), [실제 로컬 수신 bytes](input-receipt.json), [실행 및 최초 실패 보존](execution.json), [시각 검수](visual-review.json), [GitHub 병합 조회](github-receipt.json).

## continuation_pages 5곳

이 필드는 **같은 절차가 이어지는 다른 페이지**를 뜻한다. 단순히 이웃한 관리 페이지를 포함하지 않는다.

| Source ID 끝부분 | 정정 | 원문 대조 |
|---|---|---|
| INTERNAL-CLEAN-P39 | [40] → [] | 내부 청소는39쪽에서 끝난다. 40쪽은 음식물 필터4~6단계다. |
| TUB-CITRIC-P41 | [42] → [] | 구연산1~5단계는41쪽에서 끝난다. 42쪽은 식초2~5단계다. |
| TUB-VINEGAR-P42 | [41,43] → [41] | 식초1단계는41쪽, 2~5단계는42쪽이다. 43쪽은 노즐/보관이다. |
| NOZZLE-P42 | [41,43] → [43] | 상단 노즐1~5단계42쪽, 6단계43쪽이다. |
| STORAGE-P43 | [42] → [] | 보관은43쪽의 별도 절이다. 42쪽은 보관의 앞부분이 아니다. |

기존 Poppler 렌더39~43쪽을 재사용해 직접 보았고 SHA/크기를 기존 receipt와 대조했다. 본문·locator·PDF hash는 바뀌지 않았다. 생산 metadata를 수정하지 않았다.

## 적용 범위와 미확인

- 관리14는 `MFL71959117 Rev.07_030626` 공용 설명서다. 표지의 DUE6 계열 패턴과2쪽 공용 안내를 확인했으며, 정확 구매 SKU나 구매 시점 판본은 확정하지 않는다.
- 49쪽 냄새 표는 조건별 가능한 원인과 안내다. 특정 고객의 원인·청소 실패·호전 증거가 아니다. 43쪽 시각상 `50 ℃`와 기존 native `50 7` 차이는 기존 주의 문구를 유지하며 숫자 fact를 만들지 않았다.
- 참고5는 MW20GDN/MW30EDN/MW25B/MWJ25E/MWE25HD 기본 모델의 공식 청소 주의 발췌다. MW25B 표지에는 MW25B.CKOR가 있으나 실제 구매 SKU 확인으로 확장하지 않는다. 4개 PDF의 표지와12쪽 전체를 보았고 발췌는 '제품 청소하기/주의' 부분에 한정됨을 확인했다.
- 게시 catalogue의 날짜와 문서 Rev, 고객 구매일은 서로 다르다. 원 catalogue의 과거 `cover_version: null`은 그대로이며 실제 native 표지 관측 필드와 원 PDF로 판본을 대조했다.
- R9 manifest의 `runtime_registered: false`는 준비 단계 기록이다. 이후 PR262의 운영 보고가 없었다고 해석하지 않는다. 이 감사는 파일 수신과 입력/인용 범위만 확인한다.
- **실제 운영 API/MCP·저장 run·같은 DB 재시작은 별도 후속 검수다. 의미 품질 승인·PM 승인·#12/#13/D4 부모 Done은 미확인이다.**

## 기존 완료 범위 재사용

PR246/252/254/259는 PR262의 main에 원 commit이 포함되고 GitHub merged 상태도 확인됐다. PR246은 생산 DB/Excel 독립 감사, PR252는 관리14 원문, PR259는 관리 연결/설명서 후보/운영 export 요구 범위다. PR262 통합과 테스트 보고를 이 기록의 새 실행으로 세지 않는다. PR263은 조회 당시 open이며 WEB의 모델OFF E2E 보고다. 이번 원문 무결성의 선행 완료로 간주하지 않았다.

수동 큐 `docs/pm/manual-queue-20261008.json`의 D4 state는 통합 완료인 반면 follow_up은 'PR246 independent audit has not run'으로 남았다. 실제 PASS 산출물과 불일치하는 과거 안내다. 공유 큐는 읽기 전용이므로 PM의 정정 대상으로 남긴다.

## 재현과 실행 경계

1. [input-receipt.json](input-receipt.json)의 git_blob은 지정 commit/path의 `git show` 원바이트를 `.scratch/input/{staged_path}`로 준비한다. PDF는 receipt의 공식 URL/원 SHA로 식별되는 기존 로컬 파일을 읽기 복사한다. 원 PDF 전체를 새로 Git에 복제하지 않는다.
2. PDF native 문자열은 설치된 pypdfium2 5.13.0의 `PdfDocument → page.get_textpage().get_text_range()`로 얻었다. Python code point 기준 `text[start_char:end_char]`와 UTF-8 SHA를 사용한다. 5 PDF/19 page 스냅샷의 SHA·크기는 execution에 고정했다. OCR/정규화/교정은 없다.
3. [audit_delta.py](audit_delta.py)를 source/receipt/input 읽기 전용, 출력만 별도 마운트한 Docker에서 실행한다. `python -B /audit.py --input /input --receipt /receipt.json --out /out`. image·UID·network=none은 execution을 따른다. repository import와 인증 mount는0이다.
4. 기존 관리 렌더를 재사용했고 참고 PDF는 Poppler `pdftoppm -f 1|12 -l 1|12 -r 95 -png -singlefile`로 읽기 렌더했다. 로컬 scratch와 원문 렌더 receipt를 남겼다.

최종873개 데이터 assertions PASS. 이는 회귀 테스트 수나 제품 품질 점수가 아니다. 초기863개 PASS 뒤 catalogue/receipt10개 대조를 추가했고, 두 번째 실행에서 자체 검사기가 과거 nullable 필드를 읽어3개 실패했다. 원자료를 바꾸지 않고 관측된 표지 판본 필드로 검사기를 고친 세 번째 실행이873/873 PASS다. 최초 실패와 코드 SHA는 execution에 보존했다.

새 모델/OCR/운영 HTTP/재시작/자동화 ON/생산 파일 변경0. 외부 읽기는 GitHub 상태 조회만 수행했다. PM 수신·운영·승인을 대신 기록하지 않는다.
