# DATA-REMAINING-INTAKE-20261008-01a1100e

## 직접 지시와 경계

사용자는 D1·D2/PR246, 관리 근거 소비, 나머지15모델 설명서·사용Q&A·게시일 확인 후기, #13 운영 무결성, #14 자동 표 검수를 진행하되 현재 작업 중인 창에 지장이 있으면 보류하고 필요한 인계를 역할 담당자에게 GitHub로 요청하라고 지시했다.

- 담당 신진하 / `ginaginaring`, 수행 AI 조정 창 `01a1100e-bff9-7b81-b245-c9d0f56986e2`.
- 고정 main `ef29aa8ff80e9ca3f4e344c48c9acec62ad8769f`.
- D1·D2 새 PR254 고정 head `94b560de72f91795cfd50aada9e17d6773383ae1`.
- 기존 원문 감사 PR252 고정 head `78a1906369479eb2336cecc3a134895a814f95b1`.
- 새 별도 worktree `data-remaining-01a1100e-20261008`, branch `codex/data-remaining-intake-20261008-01a1100e`.
- managed worktree 도구는 umbrella 저장소에서 고정 commit을 찾지 못해 실패했다. 실제 팀 저장소의 Git으로 새 worktree를 만들었고 기존 checkout·branch는 변경하지 않았다.

## 중복 보류

기존 「LGAX #12」는 D1·D2 PR254 생산/제출을 담당한다. 「컨설팅 질문 준비하기」는 D3·D4 제출을 마치고 직접 사용자 지시로 #14 table-grounding 및 #16/#148 draft annotation·동향 인계를 진행한다. 이 창은 해당 생산 파일·D4 검사·표 sidecar·annotation/집계를 수정하거나 반복하지 않는다. #14 별도 인수창의 기존 요청6030460971도 보존한다.

## 이번에 수행할 독립 범위

1. PR254 care14를 기존 PR252의 원문/ID/판본/SHA/locator/조건에 읽기 전용으로 연결 대조한다. CORE 실제 소비 결과는 별도 인계로 기다린다.
2. 공식 지원페이지/PDF의 나머지15모델 적용성·판본 경로와 확인 가능 사용Q&A/실제 게시일 후기 후보를 새 reference 자료로만 조사한다. 기존238 원문·분할·승인 topic/자료팩을 바꾸지 않는다.
3. #13 새 ResearchBundle·운영 run DB 경로에 맞는 원응답/재시작 인계 요청을 갱신한다. PM 기존 실제 실행 보고는 보존하고 원 export 미수신과 구분한다.
4. #14 자동 graph/adapter 실제 수신을 확인한다. 미수신이면 오류 수/정확도는 null로 유지하고 현재 담당 창에 연결한다.

기존 코드·자료·개인 README는 읽기 전용이다. 새 모델/OCR·수집기 재실행·운영 등록·DB 생성·배포/재시작·자동화 ON은 하지 않는다. 검수 결과·한계·게시 receipt와 다음 담당 행동을 종료 시 연결한다.

## 실제 수행·결과

- 최신 본인 작업기록/작업근거 README 및 main의 현재 배정·문서 정본, GitHub의 PM PR245·PR254·#13/#14/#16을 읽었다. 본인 README/누적 문서는 수정하지 않았다. GitHub 확인 계정은 `ginaginaring`이며 상세 기록은 이번 날짜/고유ID에만 작성했다.
- 「LGAX #12」가 PR25494b를 제출·CI4개 성공까지 완료한 보고를 수신했다. 「컨설팅 질문 준비하기」는 PR2466f63을 제출한 뒤 #14 원문 표 근거 sidecar와 #16/#148 개발 주제·동향 인계를 진행한다. 상대 생산/검수/annotation 경로는 보류했다.
- [원 관리14 연결 대조](../../../../evals/data-remaining-intake/20261008-01a1100e/care-source-bridge.csv): ID/한글 원문/판본/전체PDF SHA·발췌SHA/쪽·문자 locator/미확인 조건 **14/14 일치**. 같은 절의 단계 연결 기대값보다 다른 절까지 포함한 continuation metadata5개를 WARN으로 분리했다. 생산 metadata의 의미나 실제 모델에서의 오사용을 확정하지 않았다.
- [설명서 원본 수령](../../../../data/reference/data-remaining-intake/20261008-01a1100e/manual-reference.md): 정확15모델 지원페이지의 후보19행·공개 URL16개 수령, 서로 다른 원본 PDF SHA15개. 전15모델에 실제 원PDF가 연결되고 표지 판본을 읽었다. 표지 정확SKU 명시는5모델, 공용/패턴10모델·전체 기능/구매시점판은 미확인. 원PDF를 새 local/private에 보존하고15표지·원URL·SHA를 reference로 인계한다. 다중 판본/같은URL/같은SHA를 분리했다.
- [Q&A·실제 후기 후보](../../../../data/reference/data-remaining-intake/20261008-01a1100e/qa-review-candidates.md): 공식 사용Q&A3의 원 HTML응답 bytes/SHA를 별도 수령했다. 고객 후기1은 원ID/날짜 미확인으로 보류, 제휴/구매검토 글1은 제외. 신규 확정 게시일 후기0. 기사 표시일/구매일을 후기 날짜나 정확 구매SKU로 승격하지 않았다.
- [#13 인계 요구](../../../../evals/data-remaining-intake/20261008-01a1100e/runtime-intake.md): 새 file-backed ResearchBundle/운영 runDB/연구 landingDB의 구별과 필요한7항목을 작성했다. PM의 실제12모델호출·저장5회/API·MCP 조회 보고는 보존했고, 이 감사에 실제 raw DB/API/restart export가 미수신인 것을 UNCONFIRMED로 구분했다.
- #14는 실제 자동 graph/adapter pin 미수신이다. 수동 원문 sidecar를 만드는 다른 창에 연결하고 자동 오류수/정확도는 null로 유지한다. 새로운 자동 예상값/공통 계약/adapter를 생산하지 않았다.

## 원 실패·수정

새 비교기의 최초 실행은 PR252 JSON을 object로 잘못 가정해 TypeError/exit1이었다. 원본은14행 list이며 새 reader의 실제 필드명으로 수정했다. 생산/원본 오류로 집계하지 않고 [원 실행 이력](../../../../evals/data-remaining-intake/20261008-01a1100e/execution-history.json)에 보존했다. 수정 후14일치/경고5/원문오류0·exit0, metadata 해석 한계를 추가한 같은 고정 입력 재확인도 exit0이다. 모델/OCR·D1생산·D4 전수검사 재실행은0이다.

웹 읽기 도구의 공식 PDF3개 접근 오류는 원 다운로드 실패와 구분했다. 정확 지원페이지에서 수신한 실제 공개16URL을 Python 표준 HTTP GET으로 각1회 받았고 전16HTTP200/PDF서명/판본/전체SHA를 확인했다. PDF native 표지16회 외 OCR0이다. 세 Q&A의 HTML도 각1회 받았으며 기사 최초 게시vs수정/정확모델 적용 승인은 별도다.

Q&A 원HTML 재대조에서 최초 후보1의 짧은 인용이 줄여 쓴 표현임을 확인했다. 새 후보 파일에서 연속 원구절로 정정하고 최초 관측 문자열/취득 당시 불일치false를 그대로 남겼다. 현재 원구절3개는 태그/공백 정규화한 원HTML과 전부 일치하고 정정한 문구도 고정238에서 일치0이다. 원 생산 자료/후기/SKU·날짜·분할은 수정하지 않았다.

[파일 보존 검수](../../../../evals/data-remaining-intake/20261008-01a1100e/artifact-checks.json)에서 원4,232파일/178,400,766bytes의 Git blob 불일치0, 새 JSON/CSV/Python AST/문서 내부 링크와 local원PDF16/서로다른SHA15/표지15/QA원HTML3의 SHA를 확인했다. Python AST는 문법 읽기만이고 생산기/기존 테스트 suite는 실행하지 않았다. 새 text는 저장소 LF이며 원 한글 문자열·실패 이력은 유지했다.

## 인수·남은 행동

이번 새 별도 branch의 [검수 README](../../../../evals/data-remaining-intake/20261008-01a1100e/README.md)에 결과별 표·고정 입력·미확인·담당·검증법을 인계한다. 부분 PR을 만들고 #5/#13/#14 및 정식 #16에 GitHub로 태그 보고한다. 실제 게시/원격 bytes/CI 수신증은 workspace의 별도 `gpt_setup/reports/data-remaining-intake-20261008-01a1100e/`에 저장한다.

- D2/PM: continuation5개의 정의 확인·필요한 별도 생산 수정 및 신규 설명서/Q&A의 구간·공용 적용·등록 인수.
- CORE: care14를 실제로 소비한 기존 고정 input/output/trace·Source ID·판본/해시 수령 뒤 결과별 인용/기능·관리/빠진 근거 대조.
- PM: 새 loaded bundle/consumer pin·비밀 없는 API/MCP/DB export·원파일·같은DB 재시작 전후쌍 및 운영 인수.
- 다른 사용자 창: #14 두 페이지 sidecar·#16/#148 주제 초안/분모 인계 계속. PM/생산자가 실제 automatic graph/adapter pin을 제공하면 해당 창에서 독립 PDF 검수.
- 기존 독립 평가 Gold/독립성/최종 채점자·무Gold4 고정 의미응답·실제 후기 게시일 provenance와 topic승인도 남아 있다. 완료된 검색11문항/225회는 반복하지 않는다.

이 작업은 부분 원문/참고자료 인계이며 PM 승인·병합/통합·부모 Done·운영 무결성·자동 OCR 성능·실제 독립 평가 완료로 기록하지 않는다. 새 비용/유료 API/설치·서비스/예산/보호규칙/자동화 변경은0이다.
