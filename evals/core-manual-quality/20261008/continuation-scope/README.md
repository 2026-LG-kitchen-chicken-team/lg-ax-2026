# 참조 쪽 표시 보완과 기존 관리 자료 소비 결과

`CORE-X1-CONTINUATION-SCOPE-01a10729-01`, 2026-10-08 KST, 황대겸/unknownamed.

[DATA PR259](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/259)의 고정 head `9516caa27f05330830aa91d725d4bd8902bf4d9e`는 관리14개 중5개의 `continuation_pages`가 같은 절의 작업 순서를 뜻하지 않을 수 있다고 보고했다. CORE 기존 렌더도 이를 “연속 페이지”로 표시했다. HTML/Markdown 라벨을 “자료에 표시된 참조 쪽 · 같은 절/단계 미확인”으로 바꾸고, 같은 작업의 순서·이어지는 단계로 확정하지 않는다는 안내를 추가했다. 페이지 값·원 source·원문·판본·locator·facts·null은 수정하지 않았다. 생산 메타데이터의 정의와 정정은 D2·PM 인수 항목이다.

## 고정 소비 결과

[consumer-receipt.json](consumer-receipt.json)은 DATA254 식기세척기 bundle `LGE-D1-D2-dishwasher-20261007-01a10600-v2-care`, SHA `e922c51dd7f1f805953fd8e4df4ea1a75479ad8da0e2ba500b541acd720e84d0`, 수정 전 CORE `3e2214920162f8725ce4f29c554ca932086e26c9`에 연결된다. [기존 소비 대조](../d2-reference-consumer/consumer-audit.json)와 [기존 출력](../d2-reference-consumer/references/dishwasher.json)의 24개 source 객체 전체가 같고, 관리14개가 모두 보존된다. 기존 출력 JSON SHA는 `bfca53d9ab18632882ec38f3b76b16118c85b025096b19c5fae8c800d463992d`다. 새 JSON은 notice만 다르고 HTML/Markdown은 notice와9개 라벨만 다르다.

| source ID 끝부분 | 유지한 참조 쪽 | 같은 절·작업 단계 확정 |
| --- | --- | --- |
| DW-INTERNAL-CLEAN-P39 | 40 | 미확인 |
| DW-TUB-CITRIC-P41 | 42 | 미확인 |
| DW-TUB-VINEGAR-P42 | 41,43 | 미확인 |
| DW-NOZZLE-P42 | 41,43 | 미확인 |
| DW-STORAGE-P43 | 42 | 미확인 |

[HTML/Markdown 원바이트 ZIP](reference-exports.zip) · [새 JSON](dishwasher-reference.json). 원문 줄 끝 공백·native CRLF는 ZIP 안에 그대로 보존하며 Git 공백 검사를 끄지 않는다. 각 출력의 바이트/SHA와5개 원문 SHA·문서판·locator는 소비 수신증에 있다. 원 관리14개 전체 대응은 기존 consumer-audit에 있다. `MFL71959117 Rev.07_030626`, p43 native `50 7`, 구매 모델 미확인과 원 추출 주의도 유지한다.

## 검증과 재현

[verification.json](verification.json), [7개 관련 검사](tests.log), [Ruff3파일](ruff.log)은 통과했다. [첫 소비 실패](consumer-initial.log)는 복사본에 아직 병합되지 않은 DATA254 입력이 없었던 `FileNotFoundError`다. 이미 수신한 고정 입력을 연결한 뒤 소비만 재검증했고 소스/검사를 바꾸지 않았다. [재현기](verify_continuation_scope.py)는 원 입력·기존 출력 SHA와 전체 source 동등 및 표시 변경 범위를 검사한다.

재현 시 코드와 고정 기존 출력이 있는 source-only 복사본에 DATA254 위 고정 head의 `data/research/r8-public-research-20261007/d1-d2-01a10600/agent-input/dishwasher/research-bundle.json`을 같은 경로로 연결한다. 입력을 다시 생성하지 않는다. credential-free/network-none/read-only Docker에서 packages/core/src·packages/contracts/src를 PYTHONPATH로 설정하고 `python -B evals/core-manual-quality/20261008/continuation-scope/verify_continuation_scope.py --output /out`을 새 출력 폴더로 실행한다. 호스트에서 저장소 코드를 import하지 않는다.

[화면 수신증](visual/render-receipt.json)은 화면 header1·5개 경고 source 카드의 print-media PNG를 기록한다. 6개 이미지 직접 판독에서 새 라벨·쪽값·원문이 보이고 겹침/잘림 관찰0, 가로 overflow0이다. 실제 paginated A4 검사를 이번에 반복한 것은 아니며 이전33쪽 근거는 당시 고정 출력으로 보존한다.

이 결과는 deterministic 참고자료 생성·소비 trace다. 새 실모델/OCR/기존6사례 채점0, 실제 기획 run=false, model version/digest/usage=null. 실제27B 기획에서 관리14개를 소비했다거나 메타데이터·정확SKU·고객 원인/호전·PM 인수가 확인됐다는 뜻이 아니다. 새15설명서/FAQ 후보는 읽기 인수했으며 기존 canonical 입력이나 생산 선택으로 자동 편입하지 않았다.
