# 정이량-E053-UPSTREAM-WEB

2026-10-07 KST · [작업006](../../../작업기록/정이량/2026-10-07/정이량-20261007-006-UPSTREAM-WEB.md)의 실제 실행·독립 검수 근거. 아래 검사들은 zero-auth/network-none/UID1000/읽기전용 source의 고정 Docker에서 실행했고 source_changed=[]·모델0이다.

| 대상 | 고정 source/실행/판정 |
|---|---|
| CORE upstream | source `297c65a48c81137adddd317e194a68b335ae27c1`; receipt `pm-r6-upstream-core-3b864e5708bf4e888b54e2fb164636af`, SHA `214c22ca5da9d3dcaebcf31471f3107cc122e3f79245ba94779958c5648765d3`; 검사181/Ruff7 PASS |
| CORE 제출 근거 | [upstream-validation](../../../../evals/pm-prototype/20261007/r5-core/upstream-validation.json) SHA `c2ed079831acda8eadb849493b387710929eccd906f8b74bdfb06b523a5ad5d0`; [반례](../../../../evals/pm-prototype/20261007/r5-core/normal-8ec-upstream-counterexample.json) SHA `e2c5539485a8e4d62d7284cfeca12bd00b607be4ea150c6344a4a9c881d9dd6b` |
| 통합 Python | source `3da67be`; receipt `pm-four-fast-f3bd3a10021f4848bebd9c8d20153f3a`; ran1597/pass1593/skip4 + launcher6 PASS |
| 앞선 지침/규격/문서 gates | source `ab21d40`; receipt `pm-four-fast-dd8212bb690d4399ab9fbf35e556d8d1`; sync/contracts/phase2/원문이관/문서탐색/모델manifest/MCP stdio/시나리오 검사 PASS |
| WEB F2–F5 | source `57f49c04989e6cbcc413ca1ba6f63849d0a9ca73`; receipt `pm-r6-web-followup-e1c2ade251b348c48fd45d06c071a6cf`, SHA `d2e4946a3adc802bc05bc3cfd92b18a98c6b998a5049ecf8ec2ead41ed9ca01f`; 관련47 PASS/실서버 opt-in1 skip/TypeScript·Vite PASS |
| PR217 | approved9448→updated `ffd6f8200611645e65bfd0012ff1ac75309d9957`; 실제 merge `4f11e85f196fa19148a7fe97e6ddda4b77707636`; headCI4/mainCI 실제 성공 |
| PR219 | approved07c0→final `2b42254dcc2254d53c5f538d73274b926a3565be`; 실제 merge `4e2bec4b6b6c65cf6f94347968a3e3a88281cec3`; headCI4 성공, 원20ADD 바이트 일치 |

실제 PM 검수: [217 승인](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/217#pullrequestreview-5437110035), [219 승인](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/219#pullrequestreview-5437071188), [220 승인](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/220#pullrequestreview-5437225626), [221 두 P2 수정 요청](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/221#pullrequestreview-5437222152), [222 승인](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/222#pullrequestreview-5437225724).

원 실패/전송 불명/이전 audit/CRLF projection과 시간축 정정은 [E052](정이량-E052-R5-NATIVE-QUALITY.md)에 보존된다. 새 upstream 필수18행은 고정 합성 정상 반례의 지원 배선 검사다. 실제 새 의미 판정·강한 일반LLM 비교·3제품 전체 품질·최종 운영/제출 완료는 미측정이다. 기존 비용259840/상한326603·자동화OFF·원21상태는 그대로다.
