# 식기세척기 공식 설명서: 냄새·관리·문제 해결 독립 검수

기록 ID: `DATA-DISH-MANUAL-01a1100e`. 2026-10-07 착수, 완료 시각은 `visual-review.json`에 기록한다.

## 확인한 범위

[PM 추가 요청 #5](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/5#issuecomment-6039619781)에 따라 기존 공식 PDF와 R8 생산 결과를 읽었다. 고정 소비 commit은 `ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f`이다. 기존 D1·D2 자료 생산과 D3·D4 표본·중복·split 검수는 별도 창의 범위다.

- 기존 DUE6BGL2E 공식 manual 발췌 **6개**는 원문, facts, locator, 제품·판본·SHA, 기존 dataset/plan/ResearchBundle 연결 **36개 항목이 일치**한다.
- 발췌 페이지는 **20·23·24**이고 내용은 배열, 바구니 높이, 노즐 간섭 조건이다. 이 근거를 제품 내부/필터/노즐 청소법이나 냄새 해결 근거로 쓰면 **미지지**다.
- 원본 PDF에는 실제 관리 절 **39~43쪽**, 냄새 문제 해결 표 **49쪽**, 세척 성능 확인 표 **50쪽**이 있다. 현재 고정 R8 bundle의 DUE manual 근거6개에는 이 절이 포함되지 않았다. 따라서 원문 절의 존재와 소비 자료의 누락을 구분한다.
- 새 검수 전용 native text 발췌 **14개**와 Poppler 렌더 **14쪽**을 대조했다. 새 발췌는 검수 근거이며 ResearchBundle에 등록한 생산 자료가 아니다.
- 고정 source의 기존 추적 파일 **4,232개 / 178,400,766 bytes**를 실제 원바이트 Git blob identity와 대조해 불일치0을 확인했다. 코드·자료·개인 README를 보존했다.

## 원본 및 적용성

원본은 [기존 공식 PDF](../../../data/sources/lg-manuals-20261005/DUE6BGL2E-ff60f78ab832.pdf), 60쪽, 5,946,269 bytes다. [공식 다운로드 주소](https://gscs-b2c.lge.com/open/downloadFile?fileId=47eEeOZ5yQ3pVzw1uosMxg)는 기존 등록 plan의 주소이며 이번에 다시 수집하지 않았다.

- 문서 ID: `DUE6BGL2E-manual-ff60f78ab832`
- 판본: `MFL71959117 Rev.07_030626`
- PDF SHA256: `ff60f78ab8326c40b9a3446f11b49531b8f0c823a310ba98366716b633ba63f5`
- 표지 적용군: `DFE6**E`, `DFE6***E`, `DUE6**E`, `DUE6***E`, `DUE6****E`, `DEE6**E`
- 표지에 정확 SKU `DUE6BGL2E`는 없다. 기존 승인 제품→설명서 연결 및 `DUE6****E` 제품군 적용을 소비한다. 2쪽은 공용 설명서에 구입 제품과 다른 내용이 있을 수 있다고 밝힌다.
- 냄새 후기 `LGE-R8-REVIEW-752651`의 `page_model=DUE6BGL2E`, `purchased_model=null`, `published_at=null`을 유지한다. 현재 설명서 참조는 구매 당시 판본·실제 구입 SKU 검증이 아니다.

## 산출물

| 파일 | 목적 |
|---|---|
| [검수표](audit-table.md) | 기존 발췌·새 공식 절의 지지/미지지/미확인과 적용 조건 |
| [기계 검수표](audit-table.json) | 연결별 동일 판정의 구조화 기록 |
| [고정 원문·producer 연결 대조](source-inspection.json) | 입력6파일 바이트 일치 및 발췌6개의36연결 비교 |
| [새 원문 범위](manual-native-excerpts.json) | PDFium native text의 쪽·시작/끝 문자·excerpt/page SHA; OCR 아님 |
| [시각 검수 기록](visual-review.json) | 표지/목차/안전/배열/관리/냄새/성능 페이지와 실제 육안 판정 |
| [읽기 전용 조사 코드](inspect_manual.py) | 고정 PDF/자료를 읽어 기존 연결과 native 원문 범위를 대조 |
| [실행 이력](execution-history.json) | 첫 anchor 오류와 후속 수정, 모델/OCR0 |
| [원본 보존 대조](original-preservation.json) | 고정 source의 기존 추적 파일을 실제 원바이트 Git blob와 대조 |
| [산출물 SHA 목록](file-manifest.json) | 새 audit 파일의 SHA·bytes, manifest 자체 제외 |

PDFium native text의 줄바꿈과 문자 오프셋은 추출기별 표현이다. 원본 PDF 바이트 SHA가 정본이고 원문 의미·표의 행 연결은 렌더를 직접 확인했다. 최초 pypdf 표지의 문자 깨짐을 확인하여 native text/시각 대조를 사용했다. 43쪽 저장 안내의 `50 ℃`가 native text에서 `50 7`로 보이는 오류도 원문 렌더와 구분하여 기록했다. 바이트나 native 발췌를 교정해서 원본처럼 쓰지 않았다.

새 감사 문서/JSON/CSV는 저장소의 LF 정책으로 게시하며, 산출물 manifest는 게시하는 바이트로 다시 계산했다. JSON에 저장된 native 원문 문자열·원 PDF·기존 생산 자료는 변경하지 않았다.

## 필요한 다음 행동

1. **DATA D2 담당**은 이 검수의 p39~43·49~50 중 필요한 절을 기존 생산 파일을 덮어쓰지 않는 새 자료 버전에 넣고, 원문 문장/조건/판본/PDF SHA/쪽/절을 연결한다. 신규 자료 생산·공통 adapter 변경은 이번 검수에 포함하지 않았다.
2. **CORE @unknownamed**는 배열·높이 경고와 관리 지침을 구분하고, 원문에 있는 안내를 개인 고객의 원인 확정·효과 보장·지원 약속으로 확대하지 않는다. 새 고정 출력이 나오면 DATA가 독립 대조한다.
3. **PM @jeongiryang**는 새로운 관리 절의 소비 범위와 정확 SKU/공용 판본 적용을 인수한다. 실행용 shorthand `M11`을 쓰면 고정 원 source ID·판본·쪽·SHA를 함께 제공한다.

공개 R8 registry에서 확인된 `M11`은 **`MW23FDI-MANUAL-M11` / 전자레인지 / 출력 조절 p25**다. 이것을 식기세척기 근거로 전이하면 제품군 불일치다. 이번에 받지 않은 runtime 내부 `M11` 매핑을 공개 ID에서 추정하지 않는다.

## 미완료와 한계

실제 고객의 냄새 원인·호전, 구입 SKU/구매 당시 설명서, 기능 발견·이해·실행 난이도, 시장 불편 발생률과 효과는 미확인이다. 수동으로 원본 표를 읽은 성공은 자동 행·열·셀·각주 구조 출력의 성공이 아니다. 자동 구조 출력은 이번 입력에 없어 검증 불가다. 모델/OCR 재실행, 운영 HTTP, 기존 코드·자료·개인 README 수정은 모두0이다. 부분 검수는 PM 인수·부모 Done·제품 전체 승인이 아니다.
