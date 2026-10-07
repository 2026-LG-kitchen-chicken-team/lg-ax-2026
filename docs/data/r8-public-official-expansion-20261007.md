# R8 D3 실제 공개 공식 자료 확장 인수 기록

2026-10-07 현재 채팅의 수동 지원 구현으로 정상 공개 페이지 6곳을 확인했다. 공식 FAQ 5개와 실제 고객 Q&A 한 쌍을 별도 역할로 나눠 **7개 ResearchSource**로 고정했다. 합성 후기·가상의 질문·추정 답변은 추가하지 않았다. 기존 D1/D2 수집, 238건 통합, DB·엑셀 검사를 반복하지 않았다.

## 실제 확인한 범위

| 항목 | 공개 출처 | 보관 역할·범위 | 모델·날짜 연결의 한계 |
|---|---|---|---|
| LG 린스 설정 진입 | [LG 공식 지원](https://www.lge.co.kr/support/solutions-20152003192763) | FAQ / official_answer. 전원이 꺼진 상태에서 설정에 진입한다는 짧은 안내 | DUE6*** 계열 표기만 확인. DUE6BGL2E는 접두어 연관 후보이며 정확 SKU 적용 확정 아님. 표시 날짜 2025-12-18의 최초 게시/수정 의미는 미확인 |
| LG 건조 조건 | [LG 공식 지원](https://www.lge.co.kr/support/solutions-20151571626779) | FAQ / official_answer. 문 열림 뒤 환경·재질에 따라 수분이 마르는 데 시간이 걸릴 수 있다는 조건 | 공용 제품군 안내. 1~3시간을 모든 식기의 완료 시간으로 일반화하지 않음. 표시 날짜 2026-05-29는 최초 게시일 미확인 |
| 삼성 플라스틱 식기 건조 | [삼성전자서비스 공식 지원](https://www.samsungsvc.co.kr/solution/1085788) | FAQ / official_answer. 소재의 열 유지 차이에 관한 자막 발췌 | 제품군 자료이며 특정 삼성·LG SKU의 성능 입증 아님. 표시 날짜 2025-01-06은 최초 게시일 미확인 |
| 삼성 컵 배치 | [삼성전자서비스 공식 지원](https://www.samsungsvc.co.kr/solution/4227974) | FAQ / official_answer. 컵을 기울여 바닥 물고임을 줄일 수 있다는 안내 | 바구니·컵 형상 및 실제 사용성을 확인하지 않음. 표시 날짜 2025-09-03은 최초 게시일 미확인 |
| LG 전자레인지 설치 공간 | [LG 공식 FAQ](https://www.lge.co.kr/story/faq/microwaves-faq) | FAQ / official_answer. 본체 치수와 통풍 공간을 구분하는 설치 맥락 | 상단 20cm, 뒤·좌우 10cm 정도의 공용 안내. 실제 SKU는 설명서로 확인. 페이지의 Q&A 표제를 고객 게시판 원문으로 분류하지 않음. 날짜 미상 |
| MW25S 재입고 질문과 공식 답변 | [LG 공개 고객 Q&A 원문](https://www.lge.co.kr/model/qna/qna-detail?modelId=MD08039646&questionNo=473510) | qa / customer_question **1개**와 qa / official_answer **1개**로 분리. 문의 번호 473510, 구매 문의 | 정상 Chrome UI에서 질문 작성일·답변 작성일 모두 2026-10-07, 제품 탐색 경로 MW25S 확인. 구매 SKU는 미상. 사용 불편 표본 **0개**, 구매·재고 기대 맥락으로만 사용 |

Q&A 질문 제목·본문은 구매 희망과 입고 알림 신청을 표현한다. 답변 발췌는 판매 확정 여부를 알려주기 어렵다는 부분이다. 이름은 마스킹 상태도 보관하지 않았다. 이 질문은 현재 18개 제품 페이지 목록 밖의 **추가 맥락 모델 MW25S**이며, 등록 모델 수를 19개로 변경하지 않는다. 답변을 실시간 재고 확인이나 미래 판매 약속으로 재사용하지 않는다.

## 원천 고정과 실행 입력

`data/research/r8-public-official-expansion-20261007/captured-sources.json`은 이번에 실제 확인한 짧은 원문 발췌다. 번호·불릿 같은 화면 서식은 제거하고 본문·모델 계열·의미 있는 조건을 유지했다. URL, 질문 번호·문서 구역 등의 locator, 수집 종료 시각 **2026-10-07T12:42:02Z**를 포함한다. 로그인·보안 경고 우회·비공개 호출은 사용하지 않았다.

`sources.json`은 같은 자료에 UTF-8 `text` 필드의 SHA-256과 명시적인 해시 범위를 더한다. **발췌 해시이며 전체 HTML, 전체 공식 문서, 원본 PDF의 해시가 아니다.** 짧은 발췌는 완전한 사용설명서나 안전한 작업 지침을 대체하지 않는다. 문서의 표시 날짜는 별도 `metadata.visible_page_date`로 보관하고, 최초 게시일이 확인되지 않은 FAQ 5개는 `published_at=null`·`date_kind=unknown`으로 둔다. 실제 Q&A는 질문과 답변의 명시적인 작성일을 각각 사용한다.

`scripts/extend_research_bundle.py`는 기존 R8 `files.json`과 모든 입력 파일 해시, 신규 수집 파일의 해시를 먼저 검증한다. 네트워크 요청과 모델 호출 없이 기존 제품군별 개발 번들에 자료를 덧붙이고 PM의 `validate_research_bundle`로 확인한다. 기존 리뷰 본문·원 ID·해시·split·hold·manual·FAQ·설치·경쟁 근거 필드는 그대로 보존한다. 계약 파일을 수정하지 않는다.

산출물은 제품군별 `bundles/*.development.research-bundle.json`, `sources.json`, `manifest.json`, `files.json`이다. 전체 자료의 원천을 다시 수집하거나 기존 R8 폴더를 출력으로 지정하는 것은 거부한다. 별도 임시 폴더에서 오프라인 재생성한 바이트와 커밋 산출물을 비교할 수 있다.

```powershell
$taskPythonPath=(Resolve-Path packages/core/src).Path+';'+(Resolve-Path packages/contracts/src).Path
$env:PYTHONPATH=$taskPythonPath
python scripts/extend_research_bundle.py
python -m unittest discover -s tests -p test_r8_official_expansion.py -v
```

## 유지된 경계와 남은 범위

- 저장 리뷰 **238건**, 개발 입력 **141건**, 기존 split **개발 141 / 독립평가 36 / 시연 49 / 격리 12**를 유지한다. 평가·시연 승인은 여전히 미완료이며 그 자료를 이번 개발 번들에 넣지 않았다.
- 공식 근거는 기존 **18개**에 신규 **7개**를 더한 실행 번들 맥락이다. 이 중 Q&A 질문 1개는 공식 문서가 아닌 고객 질문이다. 공식 문서·답변의 존재를 고객의 실제 이해·발견·수행 용이성 또는 불편 해결로 오판하지 않는다.
- 기존 DB·엑셀은 D1/D2 시점의 18개 공식 근거를 유지한다. D3는 별도의 JSON 확장 팩이며 운영 DB·서비스·자동화·중앙 큐를 변경하지 않았다. 동일 버전 통합과 운영 반영은 root 인수 후 진행할 범위다.
- LG·삼성의 건조 재질 안내와 수납 안내를 같이 볼 수 있지만, 동일 조건 비교 시험이 아니다. 제품 우열·결함 원인·빈도·시장 대표성을 주장하지 않는다. 출처는 그래프나 비교 카드의 탐색 근거로 사용하고 인과관계는 추가 확인한다.
- 실제 사용 불편에 관한 고객 Q&A는 아직 **0건**이다. 나머지 15개 모델의 설명서와 구체 SKU별 경쟁 기능·설치·재질 조건도 이번 소량 발췌로 충족되지 않는다. 새 제품군 전체 수집기와 전면 자동 수집은 구현하지 않았다.

검사는 신규 7개 원천의 역할·날짜·모델 한계, 원문 발췌 해시, 모든 기존 source 필드·리뷰 split 보존, 오프라인 재생성, 변경된 원천과 기존 폴더 출력의 거부를 대상으로 한다. 기존 전체 실험·엑셀 검수·운영 검수를 재실행하지 않는다.
