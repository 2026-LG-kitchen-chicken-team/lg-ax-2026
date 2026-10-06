# 정이량-E045-INTEGRATION — 원문 보존·작은 인수·실제 통합 검증

수행 AI: 정이량 PM의 현재 Codex와 독립 검수 보조 AI. 사용자4개 작업/새 PR/문서 재구성 지시를 [010 의도·진행](../../../작업기록/정이량/2026-10-06/정이량-20261006-010-INTEGRATION.md)에 별도 기록했다. 작업 비용·실패/모델 의미품질·실행검사·부분 인수·전체 완료를 분리한다.

## 고정 검증과 실제 원본

| 근거 | 실제 확인·원 위치 | 한계 |
|---|---|---|
| 문서 재구성 | `docs/history/project/20261006/manifest.json`, validation/validation-3sources, links/audit. 원5개161753B·제목104·링크169·이관당시 보호374. [허브](../../../README.md)·scripts/check_document_navigation.py 및 반례4개 | 개인330 상세·공식/Skill/고정근거는 이동하지 않음. protected는 이관 당시대조, 이후 정상owner갱신금지 아님 |
| 실제 PR 인수 | `docs/pm/pr-intake-queue-20261006.json`, Github actual head/CI/merge + 각 PM 댓글 | Draft168/140 보존. 모델성공·부모Done 아님 |
| WEB181 | `private/runtime/pm-four-fast-6599f761145f4a76837d58bf27c17661/receipt.json`, sourcef8f6d80. 514PASS/skip5·Node4·tsc/build | base갱신 뒤 sourcepin/CI와 비교. 원WEB scope 그대로 |
| WEB185 | `private/runtime/pm-four-fast-80a78724dfb74d0badcb21f641b842ac/receipt.json`, source114f651. 516PASS/skip5·Node4·tsc/build | 저장 선언/내보내기이며 독립 의미검수 아님 |
| DATA183 | `private/runtime/pm-four-fast-6e26546dd6bf461f8c8b1f91061faca0/receipt.json`, sourced5b3ee7. Python1469실행/실패0/skip3 | 실제운영 주입·별도preview브라우저 미완료 |
| prompt v2 | `private/runtime/pm-four-fast-f678a14ffa42455ea717613029cac6c3/receipt.json`, source70e208c. 144PASS·source변경0. 실제full실패fixtureSHAad5387cf…/468551B 보존 | 파생 annotation값의 가역 table. semantic단계 추가초과 남음 |
| PDF·API/MCP | [runtime-validation](../../../../evals/pm-data-integration/20261006/runtime-validation.json). `C:/LGAX-execution/pm-data-integration-b7a12ee97aa74228ae3ab12d15fe9d8e/`, executorSHAe6b6fe0a… | 원PDF3등록/검색/restart + MCP sameID8통과. 광역84 중 SDK환경실패1을 보존하고 정상guestvenv publicstdio1 별도통과;84동시통과 주장 안함 |
| same run replay | [이전 원 실행 연결](../../../../evals/pm-integration/20261006/same-run/README.md), `private/runtime/pm-same-run-replay-c70a3d6343304c34a8280c22eefdc726/receipt.json` | 27held/8failed 원snapshot 재생. 신규 모델호출0·정상completed 아님 |
| current 실제 브라우저 | [current proof](../../../../evals/pm-integration/20261006/trend-browser-current/README.md), source79f31a. API/MCP20/20·Browser4/4·40.063초·source_changed[]·model0, receiptSHA100ae8a916b85b1a1fb020f249addd5a0ae0bf9121d9a59b2bd5ee2766dce155 | dated1/3·33.3%/원001·sameaggregate·exports·textarea; undated0/10/null. LLM완주/운영배포 아님. 표시기대 첫실패도 보존 |
| 모델 실제 비교 | [원12출력/manifest](../../../../evals/pm-integration/20261006/model-quality/README.md), 47actual·155798tokens; 각 source/input/output/modeldigest/settings/zeroauth boundary | PM2review제한성공과 원10review실패를 분리. client attempt는 actualgeneration과 다름. 독립 평가/verified증가0 |
| 유실 호출 대조 | [gateway reconciliation](../../../../evals/pm-integration/20261006/core-r6-gateway-reconciliation.json). 같은 unknownamed·8Bdigest·promptSHA1928d852…, completion24.75초/2587+2457=5044 | gateway관측사용량과client응답전달 구분. 원 ledger/예약변경0·원client응답여전히없음 |

모든 제품 import/테스트/build/browser는 고정 Docker UID1000·read-only root·network none·capdropall·no-new-privileges·인증 profile/publisher mount없음 경계에서 실행했다. 호스트는 고정 메타데이터·Git·inert JSON·모델 allowlist 파일 중계만 수행했다. 모델은 tag/digest/schema/settings와 유한12generation/100000tokens 한도를 검증하고 임의 네트워크·GPU제어를 guest에 주지 않았다.

## 실패와 지지하지 않는 주장

- 오래된 WEB179 validation은 검사/빌드 후 source hashing 중 종료되어 whole receipt가 null인 상태를 보존했다. 최신181/185의 정상 수신증으로 대체 비교하지만 원 실패를 삭제하지 않았다.
- v2 GET tags-only ConnectError는 생성0이며 SSHforward 복구 뒤 별도ID실행을 했다. v2 actual5generation과6clientattempt의 마지막 semantic_review prompt guard는 적절한 자료보류가 아니다.
- 정적 검사·CI·fixture 재생·실모델·브라우저·사용자확인·공식요건을 구분한다. 제출/품질전체완료·효과수치·실제시장 수요·독립모델성능을 이 증거로 주장하지 않는다.
- 기존 AGENTS/CLAUDE 완전일치·문서이관·개인이관·계약·phase2·원source/정식증거 gate는 최종고정 source에서 재실행한다. 중앙 OFF·Project승인 main·메일Sent·Notion반영은 실제확인 뒤 별도 종료 근거에 연결한다.
