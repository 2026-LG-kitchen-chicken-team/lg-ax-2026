# R5 실제 후기 독립 검수 — 첫3모델 및18모델 후보

- 담당: 신진하 / ginaginaring. 검수 시각: 2026-10-07T11:09:25.162727+09:00.
- 사용자 직접 지시 + [PM R5 배정](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/12#issuecomment-6028745109).
- 기준 main: `1f3f4ecb93fdd945850a1e9f790bc37766b2355c`. 새 독립 폴더만 사용했다.

## 현재 결론

|범위|확인|미완료|
|---|---|---|
|첫3모델 후기|정상 무쿠키 제품HTML의 JSON-LD 원문9건 검수. page_only8, 타품목quarantine1.|각10~20건 미달. 후기별 정확 구매SKU 확인0·판단투입0.|
|원문·날짜|URL/HTML SHA/JSONpointer/전체본문UTF-8 SHA와 제공datePublished 원값 기록.|정상 UI 전체보기 열림·후기ID·구매일/게시일 표시 근거 미수신. 실제published_at/purchase_date는null.|
|설명서|고정 원PDF3의바이트SHA와기존인수판본/표지 대조.|후기 구매SKU→정확설명서/옵션 적용은 미확인. 판본검수가 구매SKU를 증명하지 않음.|
|18모델|공식카탈로그6개씩,기존3파일럿+15후보 표 작성.|PM의 확정18목록·수집팩/DB·Excel 인계 미수신.|
|전역중복/평가분리|현재원후기와보존발췌가같은원문인3군 확인. 당시개발실행 사용근거 있음.|전18모델수집팩의전역중복·개발/독립평가/시연 분리는 미검수.|
|#14 자동표연결|병합PR205와현재source4파일/원OCR기록바이트 동일 확인. 자동구조없음 유지.|행·열·병합셀·모델·단위·각주 원출력 인계전이라정확도/오류수null.|

## 검수 방식과 중요한 범위

1. 냉장고T876MEE1H1,식기세척기DUE6BGL2E,전자레인지MW23FDI의 정상 공개 제품HTML을 각각1회 읽었다.
   로그인·쿠키·인증 헤더를 보내지 않았다. JSON-LD3건씩을 모두 검수했고 부정 후기만 선별하지 않았다.
   이9건은 featured/편의 표본이며 무작위·대표 표본으로 주장하지 않는다.
2. 브라우저에서도 정상 제품페이지와 리뷰 전체보기 버튼을 사용했다. 전체 후기 창/원목록이 표시된 것으로 확인하지 못했다.
   정상 동작이 확인된 원목록 URL 없이 숨은API·URL변형·로그인·접근제한 우회를 하지 않았다.
   표시 총리뷰수와 현재 검수9건은 다른 값이다.
3. 상위Product의model/sku와 하위Review의 구매SKU를 구분했다. 모든 하위Review에는 실제 구매SKU/itemReviewed가 없다.
   DUE6BGL2E의review[1]은 조리화력/하이라이트 전환내용이어서대상식기세척기입력에서quarantine한다.
   같은페이지의review[0]은식기세척기설치와인덕션배치를함께언급하므로단어'인덕션'만으로격리하지않고page_only다.
4. JSON-LD의datePublished 원값은 보존한다. 화면의구매일과게시일을직접대조하지못했으므로
   이값을구매일로바꾸거나검증된게시일로자동승격하지않는다.
5. 과거개발에서사용된3발췌와현재원후기의source URL/model/날짜/전체본문SHA가일치하며,
   지정문자범위의발췌SHA도일치한다. 서로다른발췌텍스트SHA/자료버전/로컬ID만으로독립평가에재배치하면안된다.
   12표현은9원문이며,새후기12건으로계산하지않는다. 나머지6건의독립성도자동승인하지않는다.
6. 원자료/기존코드/개인README와PM보조DATA의수집·DB/Excel 영역을수정하지않았다.
   원HTML·고객작성자정보·후기전체본문은Git에넣지않고해시/위치/검수판정만제출한다.
   새모델/OCR호출0이며공통판단/계약/API/정책변경0이다.

## 실제 인계 요청

- [#12 PM/보조DATA: 첫3모델10~20건·18명단·SKU/날짜·중복·고정head](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/12#issuecomment-6029129366)
- [#14 PM/OCR생산+CORE: 실제구조출력·소비경계](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/14#issuecomment-6029129674)

댓글의발송·원문SHA는role-request-receipts.json에보존했다. [CORE 소비경계 회신](CORE구조소비경계.md)은인수했고고정7파일을대조했다. PM수집팩·자동구조생산출력은아직미수신이며요청을완료로표시하지않는다.
지시된 `docs/pm/real-review-prototype-r5-20261007.md`와 `data/research/r5-public-reviews-20261007`는
이검수main에없다. 정확head를받으면샘플선택을고정하고무작위원문·전체분리/중복을재검수한다.
PM은모델당100건상한과공개UI범위를유지해수집/DB/Excel을인계하며,신진하는별도검수만담당한다.

## 산출물

- [18모델 검수표](18모델검수표.md), [기계 판독 CSV](18-model-status.csv), [JSON](18-model-status.json)
- [9후기 항목 검수](review-audit.csv), [후기 JSON](review-audit.json), [원문/PDF pin](review-source-pins.json)
- [3실제중복계보/분리반례](global-duplicate-lineage.json)
- [자동구조 필요출력](automatic-table-handoff.json), [수집담당 필요인계](supplier-handoff-needed.json)
- [현재 본인 남은 역할](남은역할.md), [조회·사용자권한](authority-observation.json), [기존파일 보존](preservation.json)

18모델확보/첫3모델10~20건/자동표성능/독립평가/부모Done은미완료다.
새구조출력없이PR205의수동정답·144질문을자동결과/성능분모로다시포장한PR을만들지않는다.
이번PR은실제원문검수9건·SKU혼선·개발노출중복3군·18후보/부족표라는독립검수단위다.
