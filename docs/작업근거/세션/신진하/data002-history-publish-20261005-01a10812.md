# 신진하-E-DATA002-PUBLISH-01a10812 — 원 실행·미완료·게시 무결성

- 관련 기록: 신진하-20261005-DATA002-PUBLISH-01a10812. 담당 신진하/ginaginaring, 2026-10-05 KST. 근거 종류는 기존 실제 HTTP 실행, 고정 소스/입력/결과, 공식 LG 사양 읽기, 기존 모델 실측의 읽기 재계산 및 이번 게시 메타데이터다.
- 원 입력: 합성 CSV36건/가상5모델과 공식 냉장고40쪽 PDF의 등록 인용1건. PDF SHA d009424463187ba55982fdc1f3ef94f4f30687758bf4f6b6dbec291e249d3815. 실제 고객 리뷰0. 전체 PDF·DB·추출문/비밀은 private 원본으로 보존하며 이 PR에 포함하지 않는다.
- 정확한 실행 argv·코드 commit·artifact/원본/응답 hash·실패는 아래 원 단계별 JSON과 실행 source snapshot을 따른다. 실행 소스는 원 단계의 고정 commit이며 새 게시 base7652048에서 재실행하지 않았다.

| 근거 | 원 위치 | 지지하는 주장 |
|---|---|---|
| STEP1/E008 | data/research/P2-DATA-002-step1-20261005 | 입력/예상 레코드/원문 위치의 준비와 보존 |
| STEP2/E009 | data/research/P2-DATA-002-step2-20261005/runs/verified/registration-checks.json | 실제 HTTP20/35검사 등록·조회·재시작·오류 차단 |
| STEP34/E010 | data/research/P2-DATA-002-step34-20261005/runs/initial | 주130+새 저장8, 실제 추출/원문/원자성 검증·HTTP29; 전체 회귀 실패도 보존 |
| STEP5/E011 | data/research/P2-DATA-002-step5-20261005/runs/verified | HTTP122/220검사 검색·scope·원문 연결 및 관련23회귀; 전체회귀 timeout240/whole_suite_passed=false |
| 단계6 준비 | data/research/P2-DATA-002-publication-20261005/model-applicability-read-review-20261005T062615KST.json | PDF3/SHA 일치와 인용15개의 유일 span, 기능9개의 별도 적용성 판단; 통합 실행0 |
| #14 재계산 | data/research/P2-DATA-002-publication-20261005/retrieval-live-read-audit-20261005T062615KST.json | source_result aa9d09b0e1637cf2ee39af6231cbb3b88952f9a358190ed42dc86d81f7226cde의 225회 원시 기록 재계산 일치; 이번 새 모델0 |
| 원 지시·상세 행위 | data/research/P2-DATA-002-publication-20261005/historical-intent-and-evidence.md | 원002~005/E008~E011 기록의 발췌 보존; 다른 작업 기록 제외 |
| 게시 감사 | data/research/P2-DATA-002-publication-20261005/delivery-manifest.json | 원 바이트/Git LF bytes/경로/파일 해시와 이번 metadata 무결성 확인 |

단계5 검색은 literal token 방식이며 자연어 검색 품질 점수가 아니다. #14는 27요약·15수동 개발 질문 중 gold11문항의 비교이며 무gold4개 의미 판단/독립 최종 평가 미실시다. BM25 Hit@1 10/11, BGE-M3와 재정렬11/11이고 CPU 중앙값0.6337/316.2207/6006.4974ms다. 해당 별도 실제 모델 실행과 이 대화의 결과 읽기를 구분하고 #14 전체 원시 실행을 이 PR에 복제하지 않는다.

SKU 확인: T876MEE1H1 공식 제품 사양의 접이선반(1단)은 적용성 보완이며 선반 수량1개가 아니다. DUE6BGL2E는 높낮이 O(3 Level), MW23FDI는5단 출력/자동데우기3개를 공식 제품 사양으로 보완했다. PDF 원문과 기존 조건을 수정하지 않았고 개인 조리 설정 저장 지원 여부는 미확인이다. 실기기·고객 수요·효과·판단 품질을 지지하지 않는다.

예약/준비의 한계: 이 대화의 구 client에서 당시 private 경로422 및 status401을 확인했고 PM 문의5984379838/5984679995를 본인 계정/전체본문/SHA 대조했다. 이 오류를 최신 PC 전체의 인증/Worker 실패로 단정하지 않는다. 최신 #13 자동 배정5991958336/5992248482·Docker/예약 규칙은 새 실제 개발/재실행의 별도 경계다. 이번 게시에는 새 예약·모델/문서 API·tests·운영 전환이 없다.

게시 전 확인은 metadata/파일 보존·JSON 읽기·비밀정보 패턴·허용 경로·manifest/git blob 대조다. CI의 새 실제 결과, authenticated report의 ACCEPTED, PM 승인·병합·통합은 PR/Issue 및 게시 수신증에서 구분한다. parent pending와31요구 verified0을 이 게시가 변경하지 않는다. 이 문서 자체의 hash는 자기 참조로 포함하지 않는다.
