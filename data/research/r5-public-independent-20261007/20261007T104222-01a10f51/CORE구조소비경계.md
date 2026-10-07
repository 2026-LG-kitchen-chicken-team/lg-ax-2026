# CORE 구조 소비 경계 — 실제 회신 인수

[황대겸 CORE 회신](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/14#issuecomment-6029193144)을 받았다.
회신의고정8b41fd4와현재main의7원파일바이트를추가대조했다. 자동표생산완료나새계약채택으로해석하지않는다.

- canonical Evidence.id가Need/Gap/Concept 및 source_quote의evidence_id로소비된다. cell_id는그대로이ID가되지않는다.
- model_id는가전모델이고OCR/추론모델이아니다. document_version은원문판본이다.
- Locator.row는텍스트줄이며표행·열·병합정보가아니다.
- Evidence.feature_ids↔Feature.evidence_ids 양방향·모델·판본연결을유지한다.
- bbox/row/column/병합/헤더·모델·단위상속/각주관계는현재Evidence/Locator에없다.
  additionalProperties:false라서기존객체에임의필드를추가해성공으로만들수없다.
- 외부caller_supplied_extraction의pdf_or_ocr_verified=false는SHA/substring검사로true가되지않는다.
- 새producer는원PDF/구조그래프와cell_id→Evidence.id·원문문자범위대응을별도인계해야한다.
  떨어진헤더/단위/각주를이어붙인텍스트를정확연속원문인용으로사용하면안된다.

신진하:원PDF의실제셀/모델/단위/각주독립검수.
CORE:ID/가전모델/판본/위치·실제소비독립대조.
PM/생산담당:실제구조원출력·고정producer/adapter/계약승인인계.
자동정확도/오류수는계속null이며실제producer출력은미수신이다.
