# 신진하 DATA 통합 R4 실행 근거

근거ID: `신진하-E-DATA-INTEGRATION-R4-01a1100e` · 2026-10-06 20:48 KST

[본인수행기록](../../../작업기록/신진하/2026-10-06/신진하-20261006-DATA-INTEGRATION-R4-01a1100e.md)은별도경로이며, [고정3팩인계/재현/한계](../../../../evals/data-integration-r4/20261006/README.md)에서상세파일로연결한다.

|근거|실제결과|
|---|---|
|[팩pin·원36/8열](../../../../evals/data-integration-r4/20261006/run-01a1100e-03/pack-audit.json)|세pack36문장·global dates0/31/9·unknown36/5/27 보존|
|[review/Evidence 연결108개](../../../../evals/data-integration-r4/20261006/run-01a1100e-03/review-bindings.json)|UTF8텍스트·모델·문서버전·source/locator·원review번호·KST날짜 대조|
|[query15개](../../../../evals/data-integration-r4/20261006/run-01a1100e-03/queries.json)|3팩×10월/빈기간/겨울/12월/1월:독립분모·membership·ratio·동일요청재생|
|[거절40개](../../../../evals/data-integration-r4/20261006/run-01a1100e-03/rejections.json)|모델/개정/ID/출처/원문SHA/date source SHA/팩교차·충돌중복 거절|
|[BM25 실제소비](../../../../evals/data-integration-r4/20261006/run-01a1100e-03/searches.json)|3팩scope/원문·재생·오모델/오개정거절.공개방법계약은불변|
|[실HTTP46·PDF3·근거21·재시작](../../../../evals/data-integration-r4/20261006/document-http-main-087bd53.json)|원문/검색소비를새본인socket/DB에서다시실행,raw receipt SHA보존·공개사본환경경로표식|
|[착수/선행수신](../../../../evals/data-integration-r4/20261006/r4-intent-receipts.json)|#13의도/#16현재까지보고실제게시|
|[준비실패2건](../../../../evals/data-integration-r4/20261006/setup-failure-history.json)|누락프로젝트필드·empty대신명시거절기대수정.공통제품/계약변경0|

코드main087bd534e5b400b05c2963341d07587c1ee70772와PM공개입력2d4ea07e078e99776d534a10f4ed43ab8fec7095를고정했다. 분류는candidate preview,날짜는synthetic구성이다. 모델생성0/운영주입false/독립평가false다. PR189의CI4/4는조회headc4d1ea9의별도원문보호수정증거이며이R4새PR의CI/검수/병합을대신하지않는다.
