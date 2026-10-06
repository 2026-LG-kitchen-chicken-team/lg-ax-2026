# DATA #190·#196·등록 원문 검색 실측 후속

기록 ID: `신진하-E-DATA190-CORE198-INTEGRATION-01a1100e` · 2026-10-06 22:40 KST

## 사용자 지시와 의도

사용자는 PR190 불확실성/보류/질문 유실 및 web CI, PR196 운영 대조, 현재 등록 원문 BGE-M3/재정렬 비교를 실행하고 준비된 단위를 본인 판단으로 PR 게시하라고 지시했다. 본인 관련메일3건을 실제 읽고 PM190 검수·CORE11/WEB25·PR198 고정 정책·본인 최신 README를 대조했다. 자동화OFF·원 출력/실패/비용/예약을 보존하며 같은모델 생성/판단 코드 중복을 피한다.

## 실제 변경·실행

CORE의[PR198](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/198) 고정de2332d를 수정 없이 소비했다. judgement metadata의정본은CORE envelope이며두표현이상충하면어느쪽도선택하지않고거절한다. uncertainty의 원reason/questions/missing_information은기존hold_reasons/questions/unresolved로전달한다. DATA need_extraction의무조건conflicting거절을기존complaint/conflicting 허용으로맞췄다. positive/irrelevant/uncertain을확인된불편으로바꾸지않는다.

실제Skill schema를바꾸거나모델을호출하지않고전체PlanningAgent까지4개회귀를추가했다. 정상uncertain/conflicting의held/hold·원질문/사유/미상정보·원응답·상충선언거절/수정2회종료 및positive/irrelevant 불편화를검사한다. 고정오류7개의한국어설명을추가했고기존reasonText coverage검사는유지했다. 핵심71회귀는network-none/uid1000/readonly-root/인증비마운트Docker에서통과했다. 전체1498개는격리snapshot 환경문제(쓰기임시폴더/자식MCP site path/git marker)를보완해최종재검사중이며앞선실패원로그도지우지않는다.

검색실측은이미실행중인같은사용자의DATA회기를인수해중복호출0이다. [PR200](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/200)의등록원문21/질의15/3방법/5회225행을고정입력·runner SHA·실제읽기전용모델weights SHA에대조하고Docker독립재계산했다. 실패/모델·개정혼입0, 무잘림(최대154/31/181≤256), 공식pinned CPU모델이다. FR-01 gold미확정은제외한10개개발질문에서Hit@1은세방법0.7, Recall@3는0.85/1.0/0.9, MRR@3는0.8/0.8333333/0.7833333. 지연중앙값은지원55시도0.195/390.29/6621.96ms. reranker 향상/독립성능/시장효과를주장하지않는다. 원225/원gold는PR200에보존하고이PR에는독립audit만둔다.

운영은승인문서의18867bootstrap/18869health/공개health를read-only 재조회했고로컬2곳URLError·외부502였다. 토큰/인증조회/설정변경0이며성공·서버OFF·자료불일치로추정하지않는다. PM승인읽기주소/본인viewer 또는비밀없는version/ID/hash응답이필요해[196인계요청](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/196#issuecomment-6016751886)을남겼다.

## 근거·남은 일

[동일단위 실행근거](../../../../evals/data190-core198-integration/20261006-01a1100e/handoff.json)·[검색 독립audit](../../../../evals/data190-core198-integration/20261006-01a1100e/retrieval-independent-audit.json)·[운영read-only원결과](../../../../evals/data190-core198-integration/20261006-01a1100e/ops-requery.json)를참조한다. 실제전체Python/웹 결과·고정head/CI·PR190 재검수는완료시각과수신증으로추가한다. #196 실제운영은PM인계부족으로미확인, FR-01gold·독립평가·실모델품질/부모Done은후속이다. 현재새설치/로그인/모델생성을사용자에게요청하지않는다.

## 최종 검사·게시 준비 — 2026-10-06 23:16 KST

Docker 전체Python1498개통과(기존skip3), 원PM상충반례/uncertain/conflicting과실제DATA schema71핵심회귀통과. 한국어reason registry5검사·safe-ci4검사·TypeScript/Vite build, Ruff/계약/지침동기 통과. local전체web은제한시간에걸린실패를보존하고전체PASS로표시하지않는다. 원source/Skill·원6품질결과·모델응답/비용/예약은재작성0이다. GitHub의실제새head 전체web gate와PM재검수는별도다.

준비실패는본문과checks.json의원로그SHA에보존했다: tests경로/틀린module명, snapshot쓰기/SDK자식site path/git marker, 읽기전용Ruff cache 및Windows0777실행비트, 전체web시간초과. 마지막Ruff는같은원bytes의Linux0644사본에서동일규칙을검사했고규칙을끄지않았다. 동작/코드계약완화로오류를감추지않았다.
