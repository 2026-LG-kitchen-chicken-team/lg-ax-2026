# DATA-OWNER-FOLLOWUP-01a1100e — 남은 본인 배정 수행

## 지시·착수 확인

사용자 직접 지시: 앞서 #12에서 정한 1~7단계를 진행 기준으로 삼지 말고, GitHub에서 정이량의 최신 배정과 본인에게 남은 일을 찾아 수행하고 보고한다. GitHub 게시·담당자 태그는 앞선 사용자 지시에 포함된다. 자동화 OFF, 다른 세션 예약·모델 생성·CORE 판단 코드 변경은 하지 않는다.

본인 계정 ginaginaring으로 GitHub와 온라인 Project를 읽었다. 착수 전 본인 LG 관련 메일 10개를 읽었으며 메시지 ID는 1a110b11b58e3ce7, 1a110aadf710053f, 1a110aa46fa085d8, 1a110aa231df1b3a, 1a110a7a1511c739, 1a110a2cbf28557c, 1a1109d14b61f6af, 1a1107f8994fb22d, 1a11076aef739611, 1a11075ef7486916이다. 메일 발송·읽음·라벨 변경은 없다. GitHub 알림의 원문 Issue/PR을 대조했고 계정 주소·원 MIME은 게시하지 않는다.

- 최신 배정: [DATA-SOURCE-R3](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/13#issuecomment-6011538542).
- [PR176 PM 검수](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/176#issuecomment-6013905470) 및 19:09 KST 실제 main 병합 `cefe23ee77ac775467a6432d7ad668a171859fe4` 확인. 부분 자료·collector 인수이며 전체 Done이 아니다.
- [CORE 후속 원문 확인](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/13#issuecomment-6013158664): 기존 대조 오류 인정, unmentioned/unsupported는 SUPPORT_BASIS_MISMATCH이며 insufficient_evidence로 구분한다. 새 R4 3건은 실제9호출 failed, 재생성 없이 고정 결과만 대조한다.
- [WEB176 소비 검증](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/176#issuecomment-6013852904): 날짜 없는 원36건에서 drilldown이 비어 있음. 별도 합성 날짜 자료·7개 주제 표시명 인계가 필요하다.
- PR167은 16:12 KST 실제 병합 확인. PR168은 여전히 전달용 Draft이며 구현 결과가 아니다. 기존 단계 기록은 보존한다.
- 온라인 Project 19:13:46 KST: #12~#16 및 개발 #109~#114/#148 본인 배정. #16 report 미접수·adoption_required=false를 확인했다. 이번에는 실제 새 결과·공개 PR·같은 commit 개인 목차를 정식 보고한다.

## 해석·수행 범위

새 branch codex/data-owner-followup-20261006에서 공개 설명서 3개/근거21의 별도 로컬 등록→검색→재시작, 모델/버전/ID/원문 변경 거부, 누락 개발 자료 카탈로그·BM25·비교·CSV/PDF 연결을 수행한다. 공통 EvidenceSearchResponse는 literal_token_count 고정이므로 기존 응답을 유지하고 BM25의 내부 개발 결과를 별도 방법명으로 제공한다. PM의 API 계약 채택을 대신하지 않는다.

원36개 리뷰와 CSV8열을 보존하고, 원 날짜 없음 집계와 새 합성 날짜 시연을 별도 annotation_version으로 분리한다. 날짜를 원문에 있던 것처럼 표시하지 않는다. 공개 정답 중복8개인 #15의 비공개 독립성 인수·평가는 PM/독립 검수자에게 남는다. 다른 사람 기록·원 비용·실패 결과는 변경하지 않는다.

실제 실행·검사·산출물과 미완료는 [이번 근거](../../../작업근거/신진하/2026-10-06/신진하-E-DATA-OWNER-FOLLOWUP-01a1100e.md)에 갱신한다.

## 실제 수행·검사 — 19:43 KST

최신 main `fdb0ea2667c80ead07b38fbcf5ca58df292bc7e9`를 정상 fast-forward로 반영했다. #178의 기존 API/MCP/WEB 날짜 없음 확인을 읽었고 WEB 파일·타인 기록은 수정하지 않았다. 기존 1~7단계와 Deferred 상태를 현재 실행 순서의 gate로 삼지 않았다.

- 공개 PDF3개·근거21개: 실제 소켓 HTTP46요청으로 등록/ID·모델·버전 거부/조회/검색/원본 다운로드/재시작/원본 변경·삭제 거부를 통과했다. 구현 전후 별도 저장소에서 각각46요청을 비교했다. 기존 동작 검증과 새 모듈 연결 검증을 분리했다. 고정 pypdf6.10.0 휠을 이 프로세스/자식 파서에서만 로드했고 활성 환경 설치·OCR·중앙 예약·모델 호출은 없다.
- #111 카탈로그: 자료집/모델/문서버전/자료 성격 필터, 전역 ID 충돌·승인 출처 누락/폐기·해시 혼선과 현재 원본 재검증을 구현했다. 합성 demo의 승인된1.0리뷰/2.0설명서 동시 보존을 별도 회귀로 확인했다.
- #112 BM25: 결정적 한국어 인덱스(원문 수정 없음), 필터 선적용, 안정적 ID 정렬, 빈/무관 결과, 설정 검사를 구현했다. 현재 공통 API는 literal_token_count를 그대로 반환하고 내부 search_ranked_evidence만 bm25로 표시한다. 새 공통 계약 채택은 PM 담당이다.
- #113 비교: 동일 입력/자료 카탈로그/모델·버전·필터를 고정해 BM25와 주어진 BGE-M3/재정렬 artifact를 비교한다. 미제공 모델 latency/호출/성적은null이다. 공개 근거21개에서 개발4질의(라벨3·무관1) CPU 측정 top3 recall/MRR/nDCG=1.0, 합계12.513ms이며 작은 개발자료 점수다. 기존45/225행 비교·독립 검색 성능·모델 우위를 대신하지 않는다.
- #114 연결: 새로운 승인 CSV의 바이트/한글 NFD/BOM/개행·인용부호를 보존해 가져오기→카탈로그→조회→검색→재시작을 연결했다. 동시 중복 등록은 한 건으로 직렬화한다. PDF는 source_ranges의 정확한 위치 확인을 실제 등록에 사용한다. 기존 frozen36 transport는 별도 정책을 유지한다.
- 새 R4 결과3개: 원 입력/데이터/출력 및9개 prompt/raw 해시,11/11·11/11·10/10 원문을 재생성 없이 대조했다. 인용·누락·문맥 차이를 결과별/Need별 표로 남겼다. 세 건 모두 failed/HOLD_WITHOUT_QUESTIONS/질문[]이며 기능·gap·concept 단계 의미 평가는 불가능하다.
- #148/#16: 원36리뷰와CSV8열·원 날짜unknown은 그대로다. 별도36건 합성 날짜 source/dataset/sidecar에 고유 source ID·리뷰/근거 ID·자료집 버전·구성 날짜 표시를 부여했다. 새 source JSON에 text와 구성 날짜가 함께 있어 provenance 해시는 그 파일을 가리킨다. 원 CSV에 있던 날짜로 표시하지 않는다. 7주제 한국어 표시명을 preview로 인계한다.
- 새 집계 실제 API→MCP stdio→비어 있지 않은 원문 조회→재시작이 같은 aggregate ID로 통과했다. 원자료 date-less 분모0/ratio null과 별도 합성 시연의10월 분모4/날짜누락1/청소 언급1/비율0.25를 구분한다. 이 청소 원문006은 긍정이므로 불편비율로 읽을 수 없다. 계절 겨울2건, 빈 분모null, KST경계/윤일/중복/오류 회귀를 보존했다.
- 집중 회귀85개와 계약/지침동기화/기존기록 바이트 보존/phase2 무결성/기존 inference manifest 검사 전부exit0. 실패한 로컬 시연 준비(잘못된role·demo 버전 정책·MCP옛 checkout 환경)와 잘못된 검색 테스트 기대도 별도 이력으로 보존했다. 새 원문/계약/판단 오류를 숨기거나 모델을 반복 호출하지 않았다.

## 남은 일·담당자

|본인 부모 작업|현재 실제 범위|미완료·담당 다음 행동|
|---|---|---|
|#12 자료팩|기존 공개 설명서3·근거21의 실제 등록/원문 보존 확인|실고객 리뷰0, 선택 기능의 SKU 적용·자료 인수·독립 품질은 미완료. @jeongiryang이 채택 범위 확인, DATA는 새 승인 원문을 이어 받음|
|#13 원문/검색|21원문 실HTTP46·재시작 + 카탈로그/새CSV 연결 + R4 원문 대조|@jeongiryang 신규 코드 검수/운영 반영·이전409 소유 세션 최종 확인, @unknownamed R4 의미·질문 없는 보류 수정. 다른 실행 잠금을 해제하지 않음|
|#14 검색 비교|BM25·동일 입력 artifact 비교 개발 구현과 CPU4질의|실등록 원문과 고정45/225행 BGE-M3/재정렬 비교·독립 성능은 미실행null. @jeongiryang이 공통 방법명/실측 배정·고정 응답 인계|
|#15 독립 평가|PR167의156자료검사·공개heldout8입력 중복 보고/병합 확인|독립성false. @jeongiryang 자료교체 또는 진단용 처분·독립검수자·승인 비공개 수신경로 지정, @unknownamed 의미 판정 기준. 본인 답안을 새로 읽거나 게시하지 않음|
|#16/#148 동향|collector 병합176 + 별도 구성 날짜 원문 API/MCP·재시작 성공|@jeongiryang dated demo/taxonomy 승인·운영 주입·PR검수, @choigilung 7표시명과 같은ID 원문/차트/내보내기 WEB 재검증. 실제 고객 월별/계절 수요·전체 Done 아님|

현재 사용자가 설치·로그인·모델 선택을 다시 할 필요는 없다. 게시 PR의 CI·PM 인수와 인증 보고 수신은 실제 응답으로 별도 기록한다. 18:00는 이미 지난 팀 내부 목표이며 이번 완료시각을18:00 이전으로 소급하지 않는다.

## PR 게시·검수 요청 — 19:53 KST

[PR183](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/183)을 실제 게시하고 Ready for review(open/non-draft), 본인 assignee, PM jeongiryang reviewer 요청을 확인했다. 구현 게시 commit은 `342cfb32a881b04a3fb729e0945438458eb516e7`이며 PR176의 과거 CI를 새PR 통과로 사용하지 않았다. 해당 head의 CI4개가 실행 중이며 PM review/승인·병합은 아직 없다. 현재 날짜 기록과 README의 이 게시 사실을 먼저 push한 뒤 #12~#16 자기보고·#148/개발111~114 및 PR168 인계 댓글을 실제 수신증과 연결한다. 로그의 원시 출력 끝 공백은 hash로 보존한 실행 artifact이며 코드/Markdown whitespace 검사는 별도로 확인했다.

## 최종 인계·승인계획 변경 회귀

#12/13/14/15/16 자기보고와 #16/148·개발111~114·PR168 담당자 태그 인계를 실제 게시했다. [#16 정식보고](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/16#issuecomment-6014743458)의 [접수 수신증](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/16#issuecomment-6014745439), [역할별 현재성과·막힘·다음행동](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/16#issuecomment-6014864082), [148 날짜 인계](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/148#issuecomment-6014864356)를 확인했다. 접수는 품질/PM 승인·병합·전체Done이 아니다.

최신 main1c344df의 CORE R5/WEB180·181을 반영한 head d5b3ee742b481543df7cc9d1ca44b795f2bd7a5e에서도 CI4/4 SUCCESS를 직접 조회했다. DATA변경 파일은8db2bad와 동일했다. 이후 자기검수에서 caller가 constructor에 넘긴 plan 객체를 바꾸면 승인되지 않은 모델·문서개정으로 등록되는 문제를 기존 PDF 회귀에 추가해 재현했다(수정 전1FAIL, fixture파싱/실모델0). DocumentRepository가 검증 전에 deepcopy한 계획만 index/hash하도록 수정했다. 원본PDF/원문/중앙예약/판단/계약은 변경하지 않았다. 새 변경·원문 연결·CORE/WEB 최신 main을 포함한 집중85회귀와5무결성 명령은 다시 전부exit0이다. checks-plan-freeze와plan-freeze-regression.json에 근거를 보존했다. 새 수정 commit의 CI/PM 인수는 이전 d5성공과 구분한다.

당장 DATA에서 수행 가능한 새 자료 모듈·원문 대조·시연 연결은 제출했다. 운영 주입·dated demo/taxonomy 승인·독립 평가자료 처분/수신은 PM, 질문 없는 보류의 실모델 의미 품질은 CORE, 새 날짜 버전의 브라우저/내보내기는 WEB 인계 사항이다. 같은모델생성·원 비용/원 실패 초기화·부모Done 선언은 하지 않았다.
