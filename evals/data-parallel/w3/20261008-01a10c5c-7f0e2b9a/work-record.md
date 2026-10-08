# DATA-W3-01a10c5c-7f0e2b9a — 지시·해석·수행 기록

담당 신진하 DATA, 수행 AI Codex, 사용자 수동 W3 지시. 작성UTC 2026-10-08T04:05:59.326213+00:00. 기준main `eab85d48385f965eef48c07a6cdd8f6fd9851c62`. 새 브랜치 `codex/data-w3-01a10c5c-7f0e2b9a` / 고유폴더 `evals/data-parallel/w3/20261008-01a10c5c-7f0e2b9a/`.

## 직접 사용자 지시

> W3 — 인계·운영 무결성. PM이 승인한 경로·수신자·열람 범위로 기존 비공개 입력 ZIP을 전달하고 수신 파일 해시 확인. 승인된 DB/API/MCP 및 재시작 전후 캡처를 받아 동일 결과·버전·근거를 대조. PM 인계 요청과 PR 검수 관리. Gold·독립 채점자·전달 경로 결정, 원본JSON·자동표·운영캡처 요청을 취합하고 메일 및 PM 인수 기록 관리.
>
> 1. 최신 main과 PM 배정을 읽고 별도 worktree·브랜치·고유폴더 사용.
> 2. 기존 코드·자료·개인 README·다른창 파일은 읽기만 하고 새 검수 결과 별도 작성.
> 3. 모델/OCR 재실행 없이 진행. 완료225회·11문항 재채점 반복 금지.
> 4. 인계가 부족하면 받은 범위부터 검수, 확인·상충·미확인 구분, 부분PR 제출.
> 5. Gold 승인·최종 채점자 결정은 PM 담당. 메일은 W3만 관리.

AI 해석: 현재 대화의 W1 수행 결과는 PR279로 보존하고 이 지시부터 W3로 전환한다. 자료/코드/Gold 작성이나 최종독립점수·운영 재시작은 맡지 않는다. 사용자 승인된 PM 인계 연락만 기존 스레드에서 새 근거로 보완한다. 입력만 보내는 경로 승인이 있으면 원ZIP 전송부터 가능하며 다른 미완료를 선행조건으로 만들지 않는다.

## 실제 확인과 분리한 상태

본인 Gmail/신진하와 GitHub/ginaginaring 확인, 최신main/AGENTS/개인기록·근거README/PM 배정·수동큐와 Issue13/14/15/16/148/234·PR267/272/273/274/275/277/279/280 인계를 읽었다. 기존 개인README의10/6 미완료 문구를 최신 장애로 승격하지 않는다. 온라인 Project13/15는10/6 보고가 남았고16은W2 PR280 중간보고가 있어 실제 최신Issue/PR 기록을 함께 사용한다. 보드/공통 문서 변경0.

기존 PM메일5/CORE메일2는 모두 SENT·첨부0이며 확인한 스레드 직접수신0. 두 지정 발신자의10/7 이후 직접메일 검색도0건/추가page없음. 이는 조회 범위 관측이다. GitHub CORE 댓글6051070034와6051149074/6051149643은 별도 실제 공개 수신 근거로 읽었다. 메일·PR 게시를 원ZIP 수신으로 세지 않는다. 메일 원문·주소·IDs는 control/private에만 보존했다.

고정 sender 원ZIP 전체SHA/bytes를 현재파일에서 계산해 일치 확인했다.11-entry 원검수는 재사용했으며 private 입력/Gold/reviewer-only 답안 본문은 열지 않았다. 현재 승인된 전송 방법·수신자/PC·읽기 범위 및 실제 recipientZIP/SHA는 미수신이다. 실제 전송0. ZIP은 공개 PR에 포함하지 않는다.

R9-OPS-01..07은 원 producer commit3219307의 명세를 원바이트로 인수했다. 신규 실제원JSON/wire/DB/같은DB 재시작쌍0으로 데이터 대조 결과와 생성commit/원usage는 null. 선언SHA와 실제 파일SHA를 구분하고 PM의 실제 실행/저장/복원 보고는 보존한다. W1/2의 CORE부분인수도 PM승인/실모델효과로 승격하지 않는다.

PR267/279/280 정확head와 실제job/annotation을 조회했다.267기존4SUCCESS,279/280은8job steps0·결제 실패 OR 지출한도 annotation. 계정 원인을 둘 중 하나로 단정하거나 test 실패로 분류하지 않았다. 새 CI재실행·보호/한도/예산/결제/merge0.

## 관측한 진행 경계·오류

앱 관리worktree는 invalid reference eab85d4로 실패, 같은확인commit을 보유한 nativeGit에서 새 worktree/브랜치 생성. 다른창 checkout/파일은 수정하지 않았다. 초반 filename 탐색의 없는client/server/명세경로는 검색오류로 보존했고 운영자료 부재나 제품 실패로 해석하지 않았다. Project CLI의 한글 jq shorthand 오류는 ASCII 필드/원JSON 읽기로 해결, 원자료/보드 변경0.

첫 수동예약은 dated 개인문서 경로로422거부됐다. 현재 registered owner 정책의 자기 session 경로로 수정한 두번째예약은 W2 같은계정 active예약 동안409거부됐다. 최신main state._conflict는 같은owner reservation이면 경로와 무관하게 충돌한다. 다른창예약을해제하거나 정책을변경하지 않고 control/prepared에서 수신 근거만 준비했다. 실제repo 게시 전 owner release와 자기예약 성공을 재확인한다.

## 종료·재개

확보한 범위의 새 검수근거는6sourcepins·2CORE부분수신·7운영항목·9담당/미확인조건·현재3PR/12job 관측이다. 기존 결과/코드/자료/개인README·다른창 파일 변경0. 새 모델/OCR/기존225·11/기존DBHTTP 검사0. 산출물·validation·publication·메일의 실제 결과는 별도 후속 수신증과 연결한다. PM 전체인수/Gold/독립성/실제운영/부모Done 미완료.

다음 하나는 승인된 전송 결정 뒤 동일원ZIP을 전달하고 CORE 원파일 수신SHA/bytes/entry 수신증을 대조하는 것이다.

## 수신자료 audit v1→v2 정정

첫 격리 자료audit는 원스레드의 실제 PM메시지5개를 검사 기준에서6개로 잘못 기대해 실패했다. 원 mail-request-coverage.json은 처음부터5/2로 맞았다. 실제 메일/body/수신 근거는 그대로 두고 작업기록의6 표기를5로 정정하고 audit 기대값만 수정했다. v1 원로그/receipt/실패와 원검사 소스는 보존한다. 이는 W3 검수 기준 오류이며 모델/제품/기존 실험 실패가 아니다.

첫 정정 후 v2의 개인정보 문자열 검사는 v1 receipt에 보존한 검사 코드 자체의 Gmail URL 탐색 needle을 실제 메일URL로 오인해 실패했다. 원메일/새산출물에 실제주소/메일URL이 있었던 실패가 아니다. v1/v2 full argv/receipt는 control에 보존하고 공개 history는 실행 metadata와 원receipt/검사코드SHA를 연결한 축약 표현으로 명시했다. 현재 검사의 개인정보 탐지 기준은 바꾸지 않았다. v3에서 같은 자료검사와 아직 미실행인 지침일치 검사만 수행한다.

v3는 보존한 audit실패로그의 .log 확장자를 산출물형식 검사에서 누락해 실패했다. 보존로그 경로/파일명만 명시 허용하고 원로그·sourcebytes·진단·개인정보 탐지 기준은 유지한다. v3 원자료와 full검사코드/receipt도 control 및 공개 metadata+SHA로 보존했다.

2026-10-08 13:13:47 KST에 기존 PM 스레드로 새 CORE부분수신·PR279/280 CI·W3예약상태만1메일 보완 발송했다. SENT/같은스레드/검증수신자/제목/새본문 exact를 원메시지로 재조회했고 첨부0이다. [메일 수신증 요약](mail-delta-confirmation.json). 받은6sourcepins·4댓글body·운영7항목·9담당조건·12기존job의 격리자료audit와 AGENTS/CLAUDE 일치 PASS, 실제운영/모델품질 승인 아님. [검증근거](verification.json). [현재 예약 경계](coordination.json).

## 13:22 이후 새 후속 인계

W1후속PR281/head978f64d와CORE6052144975, W2후속PR282/headce4032c와producer6052164420를읽어해시/본문/정확head와계보를연결했다. 이는원raw/ZIP/실제운영인수가아니다. 두PR의8개job도실제steps0/동일결제·지출시작제한annotation을읽었고재실행0이다. W2설명서후보2개/Source경계는미승인후보이며기존15모델·238/141·집계에추가하지않는다. 자동graph/PM분류승인/원답변은여전히필요한세부항목만미확인이다. [새후속인수](followup-intake.json). 초기3PR/12job 관측은원시각으로보존하고새2PR/8job를분리한다.

새후속PR281/282 및추가댓글2개의source pin수신으로바뀐자료범위만v5에서최종검수했다. 실제8sourcepins/6댓글body/20기존job·7운영항목·9담당조건PASS. 기존source의미/225/11/producer모델검사재실행0, AGENTS/CLAUDE동일성은변경없는v4PASS를재사용했다.

## 게시 전 경계 확인

다른 창이 자기예약을 정상해제한 뒤 같은계정active예약0을 확인하고 W3의 새고유폴더/자기session문서2개만 정식예약했다. 다른창의파일/예약·controller정책을변경하지 않았다. 공개6pin·전체JSON·상대문서링크·원문보존·메일/개인정보비노출 확인후 신규파일만 추가한다. 이 작은자료인수의 PR/commit은 원모델/운영/Gold/PM전체 인수를 대신하지 않는다.

게시 직전 새session문서2개에 root text속성의CRLF→LF Git정규화가 적용돼 indexSHA와 filesystemSHA가 다름을 확인했다. 해당 신규문서2개만 실제index와같은LF로 맞췄고manifest를현재실제bytes/SHA로갱신했다. 원source2/댓글6·기존파일/README·자료/코드 변경0. 원실패와전후filesystem/indexSHA는 control/publication-newline-repair.json에 보존했다.
