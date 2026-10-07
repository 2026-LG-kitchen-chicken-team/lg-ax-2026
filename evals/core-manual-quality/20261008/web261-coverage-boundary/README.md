# CORE-C4-WEB-CONSUMER-BOUNDARY-01a10729-01

2026-10-08 KST, 황대겸/unknownamed. WEB [6046105781](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/234#issuecomment-6046105781)와 PR261 `eed222989abd74156fe3ccb01514470a9a2073bc`의 실제 원 `researchCoverage.ts`를 SHA 고정해 source-only Docker/Node22.23.3에서 직접 호출했다. [원 모듈](researchCoverage.before.ts), [경계 재현기](probe.mjs), [원 protocol 입력/출력10개](probe.json), [고정 수신/담당 인계](consumer-receipt.json)를 보존한다. 새 후기·실제 모델 응답을 만든 것이 아니며 기존 실제 ID를 사용하는 집계 protocol-only 검사다.

정상0/1·유효0분모/null·부재/invalid 승계·bool 건수·허용 오차 밖 비율은 정의대로 처리됐다. 허용 오차 안의 -5e-10(N=M=1,C=0)와 1+5e-10(N=M=C=1)이 state ok가 되는 불일치2개를 재현했다. 원 비율 조건은 finite/C÷M 오차만 확인해 명시 0~1 범위와 다르다. [CORE6046183340](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/234#issuecomment-6046183340)에 finite/type 뒤 명시 범위 검사와2반례 확인을 WEB 담당자에게 인계했다. CORE/WEB 제품파일 중복 편집·원 값 보정·새모델0이며 WEB 수정 head/실제 함수 재검수·PM API 같은저장 전달·의미품질/PM 인수는 미완료다.

[앞선 CORE→API·WEB 집계 정의](../summary-public-handoff/README.md)를 사용했다. 재현은 두 코드 파일만 readonly /source, 출력 /out, network none/read-only/UID65534/cap-drop ALL/no-new-privileges의 기존 고정 이미지에서 `node --experimental-strip-types /source/probe.mjs`로 수행했다. 실제 UI/HTTP/MCP·전체 WEB606검사를 실행한 것으로 확대하지 않는다. 실모델/기존6AI채점0이며 WEB 자기보고 ACCEPTED는 운영 보고 수신이고 PM 품질승인이 아니다.


## CORE-C4-WEB-RANGE-RECHECK-01a10729-01 — WEB 수정 수신과 같은 입력 재검수

WEB6046232299가 비율 범위 검사를 추가한 head `c0116fb026eabd24a6d2276451cea86070205ee4` 원 모듈을 고정했다. [수정 원 모듈](researchCoverage.after.ts), [수정 후 재현기](probe-after.mjs), [같은10입력/원응답](probe-after.json), [재검수 수신](after-receipt.json)을 앞선 원 실패와 별도로 보존한다. 실제 함수10개 모두 기대 상태에 일치하며 두 범위 밖 값은 malformed, 정확0/1·유효0분모/null·미제공/invalid승계 등8경계는 유지된다. 원 입력 배열은 이전과 정확히 같아 입력 보정 없이 확인했다. [CORE6046284517](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/234#issuecomment-6046284517) exact 게시로 수정 수신을 전달했다. 기존 before 원자료의 당시 owner_fix_pending은 과거 상태로 유지하고 이 후속 수신이 현재 비율 경계를 갱신한다.

모델0·WEB 제품파일 편집0이다. WEB608 vitest는 담당자 실행 보고이며 CORE 실제10경계와 구분한다. PM API의 같은 저장 HTTP/MCP·실제 UI 전달, PM 검수·병합·전체 품질 승인은 미완료다.
