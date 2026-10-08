# D1·D2 실행과 자료 보존 근거

원자료 pin은 main58feb9c, 제출 base는3e2a19d다. 새 builder는 파일 SHA를 고정해 인증/Git/private 답안·네트워크 없는 기존 Docker에서 실행했다. 실제 AI·기획 API·운영 서버를 호출한 결과가 아니다.

| 확인 | 실제 결과·범위 | 근거 |
|---|---|---|
|연구 DB 생산|고유238·관측239·18모델, SQLite integrity ok, split141/36/49/12·원문·null 유지|[명령/격리/코드 SHA](d1-build.execution.json), [실제 출력](d1-build.log)|
|Excel 저장 대조|238원문/모델/판본/위치/분할/null·239관측·계산17값 일치,4시트와 최장933자 원문 시각 확인|[저장 후 결과](excel-readback.json)|
|기존 PDF 대조|3개 원PDF SHA,21연속 page/start/end/text SHA 일치,4개 페이지 시각 점검|[D2 확인](d2-verification.json)|
|코드·자료 버전|8고정 입력과 기존 landing writer는 제출 base에서도 같은 바이트|[버전/DB/XLSX](version-and-artifact-receipt.json)|
|P0 의존|현재 main에는 ResearchBundle 정식 schema/adapter 미인계. 문의를 실제 게시|[댓글 수신증](pm-coordination-receipt.json)|

## 실패와 한계

앱 worktree 생성은58feb9c invalid-reference였다. 이미 인증 조회·fetch한 같은 Git 객체로 별도 수동 worktree를 만들었다. 원 checkout은 변경하지 않았다.

첫 source 복사는 Git이 한국어 경로를 quoted string으로 반환해 path guard에서 거절됐다. `core.quotepath=false`를 해당 읽기 명령에만 적용했고, 가드/공유 Git 설정은 유지했다. 다음 복사는 Windows 경로 길이로 중단됐다. 이 불완전 복사본에서 먼저 실행한8검사는 missing tests/scripts로 실패했으며 제품 회귀 실패로 세지 않는다. 원 로그는 별도 실패 증거로 보존하고 짧은 source 경로에 전수 복사·SHA 재대조를 완료한 뒤 검사한다.

FAQ·설치 source_type을 legacy manual Evidence로 바꾸지 않았다. 공용6자료의 정확 SKU 적용·미확인 Q&A2·독립성·실제 ResearchBundle 소비·PM 인수/병합/통합은 이번 자료 생성 검사와 별도다. 자료등록→모델 판단 전체 성공·#12Done을 주장하지 않는다.

새 유료 API·설치·모델/OCR·배포/재시작/예약·자동화ON·예산/워크플로 변경은0이다. GitHub 비용은 PM의 당일 Actions budget0/prevent_further_usage=true 보고와 현재 무료 잔량/추가 과금 차단의 직접 조회를 구분한다.

## 마지막 검사 결과

기존 공개후기9검사와 리뷰수입10검사 모두 통과(같은3e2a19d 코드). 계약·공동지침·문서연결·P2-DATA-001 packet 읽기 통과. DB 새 생성과 덮어쓰기 금지 회귀는 output 전용 TMPDIR로 복구 후 통과했다. Git 없는격리 복사에서 원기록 migration·phase2 history 검증은 실행 제한으로 실패 로그를 보존하고 CI/PM 전체Git 환경의 확인을 남긴다. fixture·기록검사 통과를 실모델/ResearchBundle 소비 성공으로 표현하지 않는다.

[검사 요약](validation-summary.json) · [완전 source 검사](complete-source-checks/checks.json) · [9회귀 재실행](temp-recovery/checks.json) · [원 불완전 source 실패](failed-incomplete-stage/checks.json).

## P0 계약 수신 후 변경

첫 미게시6fd98c0 뒤 실제 PM PR245 병합·main ef29aa8과 새 ResearchBundle 계약을 직접 확인했다. 초기 P0미수신 기록은 당시 checkpoint다. 새 canonical 입력3개(58/59/53 Source, 리뷰48/48/45)를 별도로 준비해 Source141의 원문/모델/ID/split/null/hold와 질문/공식답변 role을 대조한다. 원DB238/XLSX는 재생성0·SHA 유지, legacy API/CORE 공통코드/계약·D3·D4 편집0, 모델0이다. 원19회귀는3e2a19d 결과로 유지하고 새 P0입력 검사는 ef29aa8 규격의 별도 증거로 보고한다. 실제 서버 등록/모델 실행/전체R03/PM인수·#12Done은 별도다.
