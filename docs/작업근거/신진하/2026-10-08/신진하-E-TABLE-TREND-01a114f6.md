# 신진하-E-TABLE-TREND-01a114f6

- 기록: ../../../작업기록/신진하/2026-10-08/신진하-20261008-TABLE-TREND-01a114f6.md
- 요청 출처: 직접 사용자 DATA14/16/148 후속 지시와 “하던거 다시실행해”.
- source pin: ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f, D1후보94b560de72f91795cfd50aada9e17d6773383ae1.
- PDF 원본: DUE6BGL2E ff60f78ab8326c40b9a3446f11b49531b8f0c823a310ba98366716b633ba63f5 / MW23FDI 3ceec78295d02352fd467309bc613cf59c9bf7bce0bae3e9d5de3ad4bae2f7bc.
- CORE 원범위 요청: https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/14#issuecomment-6030572022
- WEB 동일버전/분모 요청: https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/227#issuecomment-6030715222
- 최신 생산 인계: https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/254

원 지시·기존 parser/runtime/Git/source와 새 source-derived sidecar·독립 검사·메시지 수신을 구분한다. 실제 산출물/코드/판본/SHA·검사·실패·한계를 업무별 evals에 고정한다.

## 고정 완료 근거

- 표 sidecar 파일SHA `7b0d6ae500aeabc093600cdd950df4fe9903e2f1d0800234ea7526c7c559af99`, 첫게시d58c23b, [PR258](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/258).
- CORE 실제 수신: unknownamed [6042666462](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/258#issuecomment-6042666462). 파일 읽기/SHA와 수동 소비 사전검토 보고이며 runtime는미적용. 인증된 GH댓글 조회로 작성자/본문/대상head를 확인했다.
- 후기 annotation `r8-development-topic-draft.20261008.01a114f6.v1`, 파일SHA `871c4618737f380e24725854aa8f37c665c3a8de8eca9775c3e65ca679211409`.
- 원Source141 snapshot SHA `e47f77303b83597a9c146e96f10cd1ff505d480e9f53abb80448178e481a1162`,65source/code pins SHA `f3b7a8d510988c954bfea965384562688567be74855dfca0481f0409a5614bd1`.
- 날짜sidecar 파일SHA `d34c2bd32b89f96718ad4ab278e797c004611c88b4107780ee23e9dbc34239ee`, canonical annotation SHA `d387b3a02c366d04a0b1afb3e1f41436b782a70d687b2a7d464dc19d6e17dded`. byteSHA/canonicalSHA 구분.
- [고정 출력검수](../../../../evals/data-trend-handoff/20261008-01a114f6/fixed-output-verification.json):141원Source/equality,292인용,12반례,36collector재생,97제외/141미상/분모0/ratio null PASS. 작성자자기검수이며 의미Gold승인 아님.
- 자기실패2회·통과3회 로그와6개의metadata변조거절은같은evals에있다. 실제일반형본문/필드부재/판본출처와빈원문결속을보존한다. 개인정보DOM/원private캡처를추가로읽거나배포하지않았다.

## 실제 WEB 수신 근거

- B고정head `e52cd06dc790328dd29f1e4c0d2ba3498fe7c63b`, 정식인계[6043082548](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/16#issuecomment-6043082548).
- 실제WEB읽기수신choigilung [6043200182](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/16#issuecomment-6043200182):해당head/version/SHA·Source141/equality·인용292/반례12·분할/null을보고. 인증된댓글작성자·고정head·SHA식별자/버전·본문SHA와원문을[recipient-receipts.json](../../../../evals/data-trend-handoff/20261008-01a114f6/recipient-receipts.json)에고정한다.
- [원격 게시검증](../../../../evals/data-trend-handoff/20261008-01a114f6/remote-publication-e52cd06.json):31fileGit blob대조, 중요4file실제GitHubbyte/SHA일치. e52headCI4SUCCESS. review요청은정이량이며승인/병합미확인.
- 웹검증스크립트/receipt파일은WEB의로컬commit이며공개파일미수신이다. 댓글수신을실제운영/차트/의미승인·자동graph성공으로기록하지않는다. 이번후속은문서/수신증만바뀌며고정Source/draft/date/table SHA는동일하다.
