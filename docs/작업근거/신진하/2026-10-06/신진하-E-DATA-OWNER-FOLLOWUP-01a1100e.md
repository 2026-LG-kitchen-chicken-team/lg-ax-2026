# DATA-OWNER-FOLLOWUP-01a1100e — 수행 근거

착수 main `cefe23ee77ac775467a6432d7ad668a171859fe4`, 최신 main `fdb0ea2667c80ead07b38fbcf5ca58df292bc7e9`, branch `codex/data-owner-followup-20261006`. 이전 PR176 결과와 이번 새 결과를 구분한다.

[작업 지시·해석](../../../작업기록/신진하/2026-10-06/신진하-20261006-DATA-OWNER-FOLLOWUP-01a1100e.md)

## 실제 실행·원문 보존

산출물 공통 폴더: [DATA-owner-followup](../../../../data/research/DATA-owner-followup-20261006-01a1100e/README.md).

|수행|실제 결과·근거|
|---|---|
|원문 HTTP baseline|[구현 전46요청](../../../../data/research/DATA-owner-followup-20261006-01a1100e/document-http-before.json): 실제 PDF3/SHA·다운로드 byte 일치·21근거 exact·검색·재시작, 잘못된 ID/모델/버전·변경/삭제 거부|
|새 모듈 연결 뒤 HTTP|[구현 후46요청](../../../../data/research/DATA-owner-followup-20261006-01a1100e/document-http-after.json): 동일 원문/21근거 유지, 새 원문 위치/카탈로그 검증 경로 소비|
|R4 독립 원문 대조|[결과별·Need별 표](../../../../data/research/DATA-owner-followup-20261006-01a1100e/r4-original-audit.md) · [전체 해시/ID](../../../../data/research/DATA-owner-followup-20261006-01a1100e/r4-original-audit.json): 세 입력/데이터/출력 SHA 및9prompt/raw,11/11·11/11·10/10 exact. 세 건 failed/questions[] 그대로|
|작은 개발 검색 실측|[CPU4질의](../../../../data/research/DATA-owner-followup-20261006-01a1100e/retrieval-development-measured.json): 라벨3·빈질의1, top3 recall/MRR/nDCG1.0,12.513ms. BGE-M3/재정렬 미실행null; 독립 성적/225행 아님|
|합성 날짜의 실제 provenance|[구성 날짜·원문 source](../../../../data/research/DATA-owner-followup-20261006-01a1100e/source.synthetic-dated-demo.v1.json), 새 dataset/annotation 버전. 원36개의 text는 동일하고 출처/ID/자료집 버전은 별도다|
|동일 ID의 API/MCP/원문/재시작|[실제 경로 수신증](../../../../data/research/DATA-owner-followup-20261006-01a1100e/dated-api-mcp-restart.json): TREND-ad3a67beb2e979ebae85c393bc5cc9ba4b189aaaa61c81ef6017475eba1fb414, 6항목 true. 전용 임시 token/DB/소켓, 자체 서버 종료·token 삭제; PM 운영 주입 아님|
|회귀·무결성|[검사 manifest](../../../../data/research/DATA-owner-followup-20261006-01a1100e/checks-final/checks.json):85검사, 계약/동기화/기록 바이트 보존/phase2/기존 manifest6명령 모두exit0. 원시 로그SHA 연결|
|준비 실패 보존|[4개 로컬 실패·수정](../../../../data/research/DATA-owner-followup-20261006-01a1100e/setup-failure-history.json): 오류를 보존했고 실제 모델 호출0|

현재 원 JSON raw SHA `97fe4b6badd54f3b64daf5e34f71033732e0e0b9d696d8bfc67b03b981512cf0`, 원8열 CSV SHA `3c7560aec2d3fa855590baf097b3514aa348ee40a77037c69ef358b413f488b9`를 보존했다. DATA collector의 원자료 canonical SHA `8cbc9a492bd41f1112907a166744972501095aca49325630afbabe27b43b2c03`와 raw 파일 SHA는 구분한다. 기존 source/CORE output/heldout/private 파일은 이번 git 변경에 없다. pypdf 휠 SHA `90005e959e1596c6e6c84c8b0ad383285b3e17011751cedd17f2ce8fcdfc86de`, version6.10.0을 검증한 후 부모 프로세스/자식 파서에만 사용했다.

## 재현

repo 루트에서 Python3.11 및 현재4package src를 PYTHONPATH로 설정하고 다음 명령을 실행한다. 출력은 새로운 소유 폴더여야 하며 기존 결과는 덮어쓰지 않는다.

```text
python -B -X utf8 data/research/DATA-owner-followup-20261006-01a1100e/run_document_path.py --output <새 전용 출력 폴더>
python -B -X utf8 data/research/DATA-owner-followup-20261006-01a1100e/run_dated_trend_path.py --output <다른 새 전용 출력 폴더>
python -B -X utf8 services/inference/retrieval_benchmark.py --dataset data/research/PM-DATA-intake-20261006/generated/dataset.json --cases evals/retrieval/development-cases.json --output <새 JSON>
python -B -X utf8 data/research/DATA-owner-followup-20261006-01a1100e/run_checks.py --output <새 검사 폴더>
```

전달 한계: 실제 socket/API/MCP를 검사했으나 사용자 운영 서버나 PM 중앙에 배포하지 않았다. new BM25는 내부 개발 방법이며 공통 계약 literal_token_count를 바꾸지 않았다. 구성 날짜와 주제 preview는 실제 고객 게시일·감정·불편비율·시즌 수요가 아니다. 독립 평가자료 교체/수신/의미 검수와 CORE의 accept/적절한hold, WEB 최신 날짜 시연, PM 검수·병합·전체 Done은 미완료다.
