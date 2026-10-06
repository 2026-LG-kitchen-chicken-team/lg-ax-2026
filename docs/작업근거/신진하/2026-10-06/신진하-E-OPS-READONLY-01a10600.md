# 신진하 — E-OPS-READONLY-01a10600

확인시각 2026-10-06T21:04:56.286422+09:00. 기준 자료 PR183 `8fbe6ded37f7e515ce66c24d3dc8558f8281a9fc` / 비교 코드·자료 main `b160c18a643c362dcf3923ac49742a05f7bb537d`. 이 문서/새 결과의 정확 게시 commit은 해당 PR HEAD에서 확인한다. 원자료와 과거 실행은 수정하지 않았다.

| 실제 작업 | 명령·입력 | 출력·판정 |
|---|---|---|
| 고정 자료 읽기 | `git cat-file blob <git-blob>`; reference/main의7파일 | 원바이트 SHA와 blob 동등, 3묶음 분리 |
| 메타데이터 생성 | 승인 Python3.11의 자체 stdlib `build_report.py`(저장소 코드 import 없음), PR183 JSON | 원문 제외177행; 모델/버전/리뷰-근거/text SHA·dated provenance 대조 |
| 기존 연결 조회 | `probe_get.py`; 문서의6 URL에 GET만 | [원 요청](../../../../data/research/P2-DATA-002-ops-readonly-20261006T1140Z-01a10600/query-evidence.json); 응답 확보0, URLError5·HTTP502 1 |
| 산출물 검사 | 자체 stdlib 정적 검증; rows/JSON·CSV·해시·정확 변경 경로·기록 보존 | [실제 검증](../../../../data/research/P2-DATA-002-ops-readonly-20261006T1140Z-01a10600/verification.json). 운영 성공 증거가 아님 |
| GitHub 읽기 | 공식 기존 gh 계정 확인·main/PR183/187/186/167/184·Issue12~16/148 조회 | 183/187 실제 병합, 부모 Issue open; PM R4와 다른 DATA 세션 착수 보고 구분 |

원문 위치는 입력파일 JSON pointer와 문서 page/section·리뷰 row/section 둘 다 보존한다. 공식PDF SHA는 PR183 plan의 pin을 읽은 것으로 이번 원PDF 재해시 증거가 아니다. text SHA는 UTF-8 재계산. 날짜팩 dataset canonical SHA와 annotation canonical SHA·source raw bytes SHA를 각각 재확인한다. 운영 response가 없으므로 metadata 동일·검색 원문 일치·배포 SHA·전체 연결 성공을 주장하지 않는다.

새 문서등록/프로젝트/집계/예약/설정/배포/재시작/모델/메일발송/Issue댓글0. controller/PM/admin/테스트 자격증명 전용0, token 전송0, 인증 생성/변경0. 사용자 직접 승인에 따라 이 자료 조회 결과만 새 PR로 게시하고 최종 URL/HEAD/CI는 로컬 게시 수신증과 PR에서 확인한다. 자료 버전·runtime 버전은 자동 일치로 간주하지 않는다.
