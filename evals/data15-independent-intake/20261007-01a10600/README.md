# #15 독립평가자료인계검수

확인일시 2026-10-07T00:59:59.563092+09:00. 신진하/ginaginaring. 새평가자료/정답/평가자/자료처분을만들거나선정하지않았다. 기존PR167 준비자료와현재PM 공개reference를검수한부분인수물이다.

## 직접검수한범위

기존비공개r2의 `pm-inputs.zip`(12entry)와 `pm-review-private-r2.zip`(98entry)을찾아현재원바이트SHA가PR167 인계pin과일치함을확인했다.110개entry의ZIP/원파일바이트도일치한다. ZIP·원문·답안·draft·개인정보는이PR에추가하지않았다.

6유형primary+보조2입력=8입력,16source출현을현재main `9cd2d56be52588764c18c109c9ffca4c104bd48c`의입력schema로검사했다.8/8PASS.근거ID/sourceID/모델/문서버전/논리page·row/그대로의text UTF-8 SHA를메타데이터로연결했다. 이자료는합성fixture이고위치는논리위치다. 실제LG제품사양·실제PDF물리위치·실고객수요/독립정답의증거가아니다.

검수코드 `9a64a1409494ac6882d0e82bc20fbb3f0c5362fb` / 입력원자료PR167 `406319b4fae86fce5ea1fa6ff6d2a98093f02bb4` / 현재main `9cd2d56be52588764c18c109c9ffca4c104bd48c`. networknone/UID1000/readonly·zeroauth Docker에서검수했다. 공개metadata에서request본문도hash로대체했으며첫검수원출력/코드를로컬에보존했다. #14 검수에는평가자료/답안을전달하지않았다.

## 개발중복과공개노출

|대조범위|이번결과|판정한계|
|---|---|---|
|같은개발JSON10파일|8입력의ID/text/full-input 중복0|확인범위밖학습/튜닝·의미독립성은입증하지않음|
|같은공개heldout7파일|8입력모두ID또는원문이겹침|기존공개8입력노출문제유지;independence=false|
|현재PM public semantic reference6개|6유형/material/schema/request파일hash확인|manifest의독립flag=true를새교체승인/평가자승인으로바꾸지않음|

공개PM reference의manifest request와material.input.request는다른컨테이너의전체객체hash다.차이를자동오류로판정하지않고키구성/공유필드비교를남겼다. 실제소비요청·전체자료인계는PM이고정해야한다. 여섯reference를기존공개8입력의문제를해결한새평가자료로선정하지않았다.

## input-only/reviewer-only 분리

입력ZIP에는primary/supplement/manifest/schema만있고draft·review·fixture-output·scorecard·방식키entry는0이다.검토ZIP에는검토/보존자료가별도로있다. 검토ZIP은호스트에서entry바이트hash만확인했고답안본문을검수모델입력으로읽거나평가/개발/검색튜닝에넣지않았다.검수컨테이너에는입력자료와공개reference/schema·검토ZIP의이름/hash metadata만마운트했다.

이검사는포장/메타데이터분리이며OS권한격리·암호화·새외부전송완료를뜻하지않는다. 현재수신된새평가자/비공개채널·자료처분승인은없다. 원인계의 `external_transfer=false`와원입력manifest `independent_from_development=false`를유지한다.

## 미수신과필요한입력

1. PM의공개8입력처분결정:진단용재사용또는미노출교체의정확승인근거. DATA가대신결정하지않는다.
2. 승인새input-only bundle:6유형manifest·전체입력/자료/source/model/document/위치/SHA·고정출력계약·노출/변환provenance.
3. 별도reviewer-only 인계manifest:허용받는사람/역할·답안/rubric파일SHA.내용을개발/모델생성에혼합하지않는다.
4. 독립평가자와승인비공개전달경로:PM 지정/권한근거.개인토큰을Git에붙이지않는다.
5. 같은조건의실제Agent/강한기준선전체결과:코드·모델·샘플링/예산·입력/자료/schema SHA·전체전달/미잘림·원실패/호출/토큰을포함한다.

[필요인계JSON](required-intake.json)에서received=false를명시했다.자료가들어오면그인계범위만검수하며현재자료를독립평가정답으로승격하지않는다.

## 근거와완료구분

[8입력/16근거](input-and-source-audit.json) · [17파일중복대조](development-and-public-exposure.json) · [110entry/role/hash](archive-role-and-hash-audit.json) · [PM6reference](public-PM-material-reference-audit.json) · [source pin](source-pins.json) · [검수체크](audit-checks.json) · [실행](execution.json) · [원로그](audit-original.log).

기존156검사는원자료검수기록으로보존했고이번8schema/110entry 등과합산해새점수를만들지않았다. 이번자료인계검수단위는완료지만독립성인수·실제Agent/기준선실행·독립채점·PM검수/병합·#15전체완료는아니다. 모델/OCR/독립채점0. 기존개인README와원자료/답안/실패/비용은변경하지않았다.

재현은권한있는r2 입력ZIP(답안ZIP본문제외)·현재공개17reference/schema/PM6자료와source-pins의metadata를 `/input`에준비하고 `python audit.py --input <고정입력폴더> --output <새폴더>`로실행한다. 원비공개자료는GitHub가아닌승인된경로로만인계한다.

게시 전 검수: 지침 동일바이트·기존계약 검사PASS. 로컬 전체phase2validate는Git이력없는worktree마운트에서실패했고 원로그를#14에보존했다. 고정실행기의로컬Git복제금지를바꾸지않았다. #15에서는같은실패를반복하거나PASS로승계하지않았고실제GitHubCI의이력gate를별도로확인한다. 자료감사결과와전체하네스gate는구분한다.
