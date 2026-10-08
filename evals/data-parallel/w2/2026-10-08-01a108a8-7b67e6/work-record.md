# DATA-W2-01a108a8-7b67e6 작업기록

담당: 신진하 / ginaginaring. 수행 AI: 현재 Codex 대화 01a108a8. 한국시간 날짜: 2026-10-08.

## 현재 사용자 지시

LGAX 저장소 최신 main, 개인 README, 기존 OCR 검수표, PR270/272 및 인계 기록을 먼저 읽고 별도 worktree/`codex/data-w2-<고유ID>`/새 `evals/data-parallel/w2/<날짜-고유ID>/`에서 작업한다. #14의 실제 자동 table graph·승인 adapter pin을 인수해 원 PDF의 셀·행·열·모델·숫자·단위·각주·위치를 대조한다. 자동 출력이 없으면 검증 불가로 남긴다. #16/#148의 141행 초안을 재사용하고 PM 승인 버전/지적 Source ID의 해당 행만 보완한다. 15모델 설명서 후보, 정확 구매 SKU·구매시점 판본, 날짜 있는 실사용 후기/Q&A의 부족한 근거를 보완하되 새 자료는 별도 후보에 보존한다. 기존 파일/README/CSV/코드 및 다른 창 파일은 수정하지 않는다. 모델/OCR·기존 수집을 재실행하지 않는다. 모델결과·DB/API·ZIP·독립평가·메일은 다른 창 담당이다. 막힘은 #14/#148에 이 고유 marker로, 부분 PR과 정식 보고는 #16에 남긴다.

## AI 해석·명시한 가정

이 창의 완료 범위는 원문/고정 산출물에 대한 자료 검수와 후보 보완이다. 파일 존재·읽기 수신·자기 검수·PM 승인·운영 성공을 분리한다. 기존 결과를 새 자동 실행 결과로 재명명하지 않는다. PM 분류 승인이 없을 때 141행 전체를 재분류하지 않는다. 날짜/구매 SKU/판본 근거가 없으면 null/미확인 상태를 그대로 유지한다.

사용자의 개인 README 변경 금지 및 새 출력 폴더 지정이 일반 기록 README 갱신 규칙보다 우선한다. 상세 기록을 이 새 폴더에 두고 동일 commit의 PR/Issue 보고에서 직접 연결한다. 메일 점검은 3창으로 위임되어 이 창에서는 실행하지 않으며, 이 창이 메일 전체를 확인했다고 표시하지 않는다.

## 착수 확인과 원 실패

- 개인 GitHub Credential Manager 인증을 메모리에서 확인: ginaginaring. PM 인증 파일/메일/독립 평가 정답을 읽지 않았다.
- 공식 main fetch 후 `eab85d48385f965eef48c07a6cdd8f6fd9851c62`에 고정. 다른 worktree의 미커밋 파일은 보존했다.
- Codex 앱 worktree 생성은 대화의 바깥 Git 저장소에 해당 commit이 없어 `fatal: invalid reference`로 실패했다. 실제 LGAX 중첩 저장소를 명시한 Git CLI로 별도 worktree/branch를 생성했다. 실패 후 기존 checkout 초기화나 전역 safe.directory 변경은 하지 않았다.
- 최신 공통 지침·문서 입구·개인 README owner 요약·PM 수동 R9 안내 및 PR270/272/Issue14·16·148를 읽었다. PR272 CI billing 제한과 실행 단계0은 그 PR의 관측이며 이 새 작업의 테스트 결과로 사용하지 않는다.
- 온라인 Project status 직접 조회 성공: main pin 일치, DATA005 Ready·이전 자기보고는 오래됨. Ready와 실제 전체 완료를 구분한다.
- 중앙 status: global off, 네 개인 off, 예약0. 새 본인 예약 `manual-data-w2-01a108a8-7b67e6`을 신규 출력 경로/본인 CPU 자료검수 resource로 수신했다. 다른 세션 lease 변경0.

## 예정 행동·검수 기준

- 실제 graph/adapter와 PM 승인 분류의 필요 pin을 #14/#148 댓글로 구체 요청한다.
- 원 PDF를 새로 수집하거나 OCR하지 않고 고정 PDF SHA/기존 native text/render·수동 검수표를 재사용한다.
- 141행 Source/인용/원ID·partition·date-only 고정 출력을 정적 대조한다. 제품 collector/운영 API를 재실행하지 않는다.
- 15모델 후보/PR270의 고정 sidecar와 공개된 별도 신규 후보를 검토한다. 개인 작성자 정보/후기 전문은 Git에 복제하지 않는다.
- 기존 tracked 파일의 SHA/바이트와 신규 파일 범위, JSON·링크·분모/null·출처 pin을 확인한다. 실제 제품/모델/OCR 검사를 했다고 표시하지 않는다.

## 실제 수행·수정과 자기 검수

- #14/#148에 본 고유ID로 자동 표/adapter 및 분류·Source ID·SKU/판본/날짜 인계 요청을 게시하고 작성 계정·본문 해시를 대조했다. 2026-10-08 11:30 KST 이후 댓글 재조회는 24/13개 전체 댓글 대상으로 완료했고 새 답변0이었다. 승인 미수신을 유지한다.
- 기존 PDF2개·native page text·렌더·5셀/1각주 수동 sidecar와 D03/M06/M07의 canonical 연결을 다시 대조했다. 기존 OCR 결과를 재사용했으며 자동 표 출력/adapter 없이 자동 정확도나 오류수를 산출하지 않았다. 상세54행에서는 숫자 셀이 아닌 각주의 해당5축을 미확인으로 구분했다. 이 구분을 추가하기 전 같은 새 실행의 결과/유틸리티를 private `inspection-attempt-01-output`에 보존하고 두 번째 정적 검수를 수행했다.
- 141행 원 Source/원ID/판본/locator/원문 hash와292인용 codepoint 구간/hash, 24주제별 membership의 union, 원238개 partition의 상호 격리, 날짜 미상 제외141개, 기존36개 빈 집계의 분자0/분모0/ratio null을 확인했다. PM 승인·지적 Source ID 없이 기존 분류 행을 바꾼 수0이다.
- 기존15모델19원문 참조를 다른 창의 고정 private PDF 경로에서 읽고15고유 SHA 일치를 확인했다. 기존 후보/PR270의 실제 판본과 공통·정확 모델 범위 조건을 보존했다. 다른 창 원 파일 변경0·새 PDF 수집0·OCR/모델 호출0이다.
- 기존 모델 후보와 연결되는 공개 판매처 후기4건의 원ID·상세 페이지·본문 연결·날짜 표시·판본 날짜와의 선후 관계를 확보했다. 공개 HTTP GET6건은 제한된 신규 자료 조회이며 기존 수집 작업/제품 collector를 실행한 것이 아니다. 4후기의 전문 정규화 일치를 기존238개 및 후보끼리 확인했고 겹치는 전문0을 기록했다. 이 검사는 더 넓은 재게시/독립 고객 인증을 대신하지 않는다.
- 상세4후기 중2건은 기존 현재 설명서 판본 날짜보다 빠르다는 추가 공백을 확인했다. 표시 모델은 구매SKU와 구분하고 게시/수정일 의미를 승인 전 확정하지 않았다. 기존 집계에 추가0·승인 날짜0·구매SKU/구매시점 판본 확인0·신규 사용 Q&A0이다. MW20GDN의 공개 초기 HTML에서 개별 고객 사용 Q&A 연결은 받지 못했다. 제조사 FAQ3은 고객 분모0으로 유지했다.
- 제품/모델 코드나 현재 branch 수집기를 가져오지 않는 저장 자료 전용 독립 유틸리티로 구조 검사1,101개 PASS를 관측했다. 첫/두 번째 결과의 원 로그와 실행 소스 SHA는 private 새 폴더에 보존한다. 자동 표/분류 의미/운영 API/독립 평가 PASS로 확대하지 않는다.

## 추가 원 실패와 복구

- PR270 자료를 원 경로 그대로 private에 저장하려던 시도는 Windows 긴 경로 제한으로 실패했다. 부분 수신 파일을 지우지 않고 원 head/path/SHA를 index에 남기는 짧은 해시 파일명 폴더로 수신을 마쳤다. 소스/모델/기존 수집을 재실행한 실패가 아니다.
- 인증 보고 연결 문서용 두 번째 예약은 HTTP409 `manual work conflicts with an existing running/orphaned owner`로 거절됐다. controller status와 읽기 전용 코드 확인에서 자기 active 예약도 owner 단위로 충돌함을 확인했다. 다른 창 lease를 해제하지 않고 최초 본인 예약만 해제한 뒤 출력 경로+신규 연결 문서2개를 한 개 본인 예약 `manual-data-w2-final-01a108a8-7b67e6`으로 수신했다. 자동화는 팀/4개인 OFF 그대로다.
- 별도 Python 부모 프로세스가 이름만으로 `gh`를 찾는 시도는 WinError2로 실패했다. 인증 실패로 해석하지 않고 이미 검증한 개인 portable gh의 절대 경로를 사용해 댓글 재조회에 성공했다. 원 오류를 숨기거나 PM 인증을 복사하지 않았다.
- 최초 staged diff 검사는 보존한 Windows CRLF의 CR을 trailing whitespace로 처리해 실패했다. 원 출력을 private에 보존하고 기존 저장소의 불변 실행 근거와 같은 방식으로 **새 출력 폴더의 JSON/CSV/실행 소스 보존본만** `-text -whitespace`로 지정했다. 기존 `.gitattributes`는 바꾸지 않았다. 실제 행 끝 공백은 CR을 제외한 줄 단위 검사로 따로 확인하고 실행 소스/검수 JSON/CSV의 staged blob가 원 실행 바이트와 같은지 대조한다.
- Codex 앱 worktree 생성 실패, PR272의 billing CI/실행 단계0, 이번 자료 정적 검사 성공은 각각 출처와 범위가 다른 사건이다. PR272 또는 새 PR CI가 성공했다고 추정하지 않는다.

## 보고·인수인계 및 마지막 안전한 상태

신규 자료와 상세 기록은 이 출력 폴더에만 있다. 인증 #16 보고 정책이 허용하는 개인 신규 세션 경로에는 상세 파일을 가리키는 연결 문서2개를 추가한다. 사용자 지시대로 기존 개인 README/호환 목차와 자료·코드·8열 CSV는 갱신하지 않는다. 기준 main의 tracked4,741파일 전체 SHA 보존과 신규 파일 범위는 게시 전에 별도 [scope-preservation.json](scope-preservation.json)으로 확인한다. Git commit/PR/정식 보고·ACK·CI 상태와 최종 예약 해제는 게시 후 실제 수신을 확인하여 #16 및 private 게시 receipt에 연결한다. 이 문서가 그 이후의 미관측 사건을 성공으로 예고하지 않는다.

막힘: 실제 자동 graph/승인 adapter pin, PM 승인 분류/지적 Source ID, 정확 구매SKU/구매시점 판본/고객 Q&A, 후기 날짜 의미 승인. 부분 PR은 이 자료 검수·후보만 검수받기 위한 것이며 부모 전체 Done/선행 의존 해제는 아니다. 메일은3창 담당이고 이 창의 메일 읽기/발송0이다.

다음 작업 하나: PM의 승인 pin 또는 지적 Source ID를 받으면 해당 연결/행만 보완한다. 현재 사용자가 직접 해야 할 일은 없다. 새 예약도 끝나면 본인 것만 해제한다.
