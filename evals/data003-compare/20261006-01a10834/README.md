# #14 등록 원문 비교 입력·기존 실측 재검산·OCR 오류 인계

기존 요약 corpus와 실제 등록 원문의 본문이 달라 과거 검색 성적을 그대로 적용할 수 없다. 이번 변경은 기존225회 검색·70회 OCR의 재검산과 원문21개/동일질문15개의 새 비교 입력·빈 측정표를 전달한다. **새 모델/OCR 호출0, 새 corpus 성적 미측정, #14 전체 미완료**다. Refs #14. 자료 등록·출력 보존 코드는 #13, 판단 코어·웹·공통 API/Schema·운영 설정은 해당 담당 범위로 유지했다.

## 실제 기준과 중복 제외

- 준비 기준 main: `b477860b2612f51b7e81f37b635c05ba02338bfb`.
- 게시 기준 main: `d0e8f1d525360c8a03467d13b3b78fc76e8384e9`. 두 기준 사이 PM 자료팩/자료 소비 코드27파일의 Git blob은 모두 동일하다. [대조 근거](baseline-recheck.json).
- PR131·141은 고정 원본 보존·선택 인수 후 닫혔으며 전체 병합이 아니다. 실제 PM 판정과 원 head는 [인수 범위](prepared/PR-intake-scope.json)에 있다.
- **기존 원시 산출물75개·PM 등록팩·6개 근거·보존 패치를 다시 게시하지 않는다.** 원75개 해시는 [원본 보존 인덱스](prepared/historical-preservation.json)에서 확인한다. 검색/OCR의61개 비교 산출물은 current main의 원 경로에서 원bytes와 동일하고,14개 공개 개발 검토 산출물은 PR131/PM 원본 보존 자료를 참조한다. 이번 PR에 역사 원본 폴더를 복제하지 않았다.
- 새 파일은 모두 `evals/data003-compare/20261006-01a10834/` 아래에 있다. #13의 등록/보존 코드, 다른 담당 소스와 공유 개인 기록/목차는 변경하지 않는다. 새 날짜별 개인 기록의 중앙 경로 소유권 거부422를 보존하고, 승인된 평가 폴더에 전체 고유 세션 기록을 남겼다. 정책을 바꾸거나 거절된 경로에 쓰지 않았다.

## 이번 결과

| 항목 | 결과 | 성격 |
|---|---|---|
| 원문 corpus 대조 | 요약27 ↔ 원문21, 공통ID15개 본문 모두 변경·개발전용12·현재전용6 | 입력/출처 대조 |
| PM 추가 근거6개 | 현재 PM 버전에서 ID·모델·개정·원문·hash 동일 확인 | 조회 확인, 재등록0 |
| 검색 원225회 | BM25 10/11·BGE11/11·재정렬11/11, 중앙지연0.6337/316.2207/6006.4974ms | 과거 corpus 재검산 |
| OCR 원70회 | exact8/14·microCER6.8702%·숫자15/15·단위12/12·엄격필드10/11 | 과거 인식 재검산 |
| 새 비교 준비 | 원문21·동일질문15·세방법 공통조건·측정225행 | 전부 not_executed, 점수/지연null |
| 검사 | 원시 산술/문자45＋순위/숫자·단위528항목 일치 | 저장 결과 계산, 런타임시험/독립평가 아님 |

FR-01의 기존 정답ID F10은 현재 원문에서 선반 분리 방법이며 ‘식품 먼저 치우기’는 F10-FOOD에 있다. 원gold는 수정하지 않았고 [질문 대응표](prepared/question-evidence-map.json)에 PM 검토용 대응만 기록했다. ID존재11/11은 검색 적중률이 아니다. API `literal_token_count`를 BM25/BGE 결과로 사용하지 않는다. 냉장고 설치 간격 상충·DUE 제품 타입/열·MW 출력 각주와 소비전력 차이·전원분리 후 유지 미확인을 보존한다.

OCR 공백 누락5영역·각주기호1영역과 엄격필드 실패를 [오류표](prepared/ocr-error-ledger.csv)에 기록했다. 표 전체 추출·행/열/모델 연결은 null/미측정이며 수동crop 성공으로 대신하지 않았다. 같은70회 OCR을 반복하거나 새 레이아웃 모델을 설치하지 않았다.

## 인계 파일

- [공통 모델 입력](prepared/model-corpus.json), [같은 질문](prepared/model-queries.json), [원문/위치/해시 manifest](prepared/corpus-manifest.json), [corpus 차이](prepared/corpus-difference.json).
- [비교 조건](prepared/comparison-protocol.json), [새 측정표 CSV](prepared/retrieval-measurement-template.csv), [측정표 JSON](prepared/retrieval-measurement-template.json). 모델 입력에는 gold/기대 답변이 없다.
- [검색 재검산](prepared/historical-recalculation.json), [225회 진단표](prepared/historical-retrieval-attempts.csv), [70회 OCR 진단표](prepared/historical-ocr-attempts.csv), [OCR 문자/숫자/단위](prepared/ocr-error-ledger.json), [표 측정 준비](prepared/ocr-table-review-plan.json).
- [#13 인수 필드](prepared/13-handoff-contract.json), [모델환경·고정revision](prepared/model-environment-reuse.json), [6근거 확인](prepared/accepted-six-confirmation.json).
- [원 분석 보고서](original-analysis-report.md), [원 작업기록](original-session-work.md), [원 근거](original-session-evidence.md)는 11:55경 로컬 준비 당시 원bytes다. 그 안의 ‘게시0/예약활성’은 당시 관측이며 현재 게시 상태를 뜻하지 않는다. 역사폴더/로컬경로는 위 원본 인덱스 및 이전PR 참조로 연결한다. [이번 게시 기록](publication-work-log.md)과 [게시 근거](publication-evidence.md)를 함께 읽는다.
- 분석 소스2개는 inert `.py.txt` snapshot이며 활성 scripts/tests 구현으로 설치하지 않는다. 원 실행 시 로컬 원본을 참조한 조건을 보존하며 그대로 현재 서비스에 적용하는 코드가 아니다.

## 남은 범위

#13의 이번 실제 등록·파싱·저장·검색·원문·재시작 출력 인수 → FR-01 정답 대응 검토 → 승인된 격리 모델환경/자원 및 전체 tokenizer 길이 확인 → 새 동일 corpus 검색 실행 → PM 인수. 전체 #14 완료/Agent 불편판단·콘셉트 채점/최종 독립평가는 아니다. 11:45의 #12예약/13충돌은 역사 관측이고, 15:44 중앙조회에서는 예약0이었다. 이번 게시에서만 위 전용경로 예약을 정상 취득했으며 새 모델을 호출하지 않았다.
