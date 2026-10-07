# #14 FR01 사후 정답 정정과 11문항 재채점

확인 시각: 2026-10-07T11:43:43.862923+09:00. [PM 정답 승인](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/14#issuecomment-6029600741)에 따라 PR200의 고정 225행을 오프라인 재채점했다. 새 검색 모델·LLM·OCR 호출은 0회다.

FR01은 선반 분리 전 식품 제거를 묻는다. 원 F10(선반 고리 분리)을 보존하고, 19쪽 식품 제거 조건인 `T876MEE1H1-MANUAL-F10-FOOD`로 정답 연결을 정정했다. 판본은 MFL71401557 Rev.00_032526이며 text SHA는 `11212c8d4c0a986100451a8693f76ddc93b5a6de5b5b0ee2ecd502bb5cd48a5b`다. 원 위치 대조는 [PR206](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/206), 원 순위·입력·모델 해시는 [PR200](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/200)에 연결된다. 다른 10문항 Gold와 순위·입력·모델·설정은 유지했다.

| 검색 방식 | Hit@1 | Recall@3 | MRR@3 |
|---|---:|---:|---:|
| BM25 | 7/11 (63.6364%) | 86.3636% | 0.757576 |
| BGE-M3 | 7/11 (63.6364%) | 100% | 0.803030 |
| BGE-M3 + reranker | 7/11 (63.6364%) | 90.9091% | 0.757576 |

분모는 11개 고유 질문이다. 5회 반복을 55개의 독립 질문으로 세지 않았다. 실제 실패행은 0개이며 실패 0점·다중 Gold의 기존 규칙을 유지했다. [33개 문항별 점수와 주지표](approved-rescore.json), [승인 수신증](verified-PM-approval.json), [고정 입력 해시](approved-rescore-source-pins.json), [실행](lgax-01a10600-free-rescore-approved-1137.execution.json)을 확인하면 된다.

원 파일의 미확정 점수는 덮어쓰지 않았다. [승인 전 null 결과](approval-gate-result.json)와 제안 Gold도 보존했다. 기존 4개 toy 회귀 검사와 실제 재채점은 같은 scorer SHA를 사용한다.

정답 없는 FR04·FR05·DW05·MW05는 검색 목록/필터 결과와 의미상 거절·질문·보류를 구분한다. 이 4문항의 실제 의미 응답은 미실행이며, 새 11문항 평균에 포함하지 않았다. 재채점은 독립 평가나 모델 성능 개선 실험이 아니다.
