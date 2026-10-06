# BM25 개발 기준선 실제 실행

기존 27개 사실 요약, 15문항 중 근거가 있는 11문항의 검색 지표다.

- Hit@1: 0.9091
- Recall@3: 0.9091
- MRR@3: 0.9091
- 실제 측정: 75회, 실패 0회; warmup 2회 별도
- 모델/버전 혼입 ID: 0/0개

| 질문 | Hit@1 | Recall@3 | MRR@3 | 반환 근거 |
|---|---|---|---|---|
| FR-01 | 1 | 1.0 | 1.0 | T876MEE1H1-MANUAL-F10 / DATA003-T876MEE1H1-F12 / DATA003-T876MEE1H1-F13 |
| FR-02 | 1 | 1.0 | 1.0 | T876MEE1H1-MANUAL-F11 / DATA003-T876MEE1H1-F13 / DATA003-T876MEE1H1-F12 |
| FR-03 | 1 | 1.0 | 1.0 | DATA003-T876MEE1H1-F13 / DATA003-T876MEE1H1-F12 / T876MEE1H1-MANUAL-F10 |
| FR-04 | None | None | None | 없음 |
| FR-05 | None | None | None | DATA003-T876MEE1H1-F12 / DATA003-T876MEE1H1-F13 / T876MEE1H1-MANUAL-F10 |
| DW-01 | 1 | 1.0 | 1.0 | DUE6BGL2E-MANUAL-D09 / DUE6BGL2E-MANUAL-D13 / DUE6BGL2E-MANUAL-D12 |
| DW-02 | 1 | 1.0 | 1.0 | DUE6BGL2E-MANUAL-D12 / DUE6BGL2E-MANUAL-D14 / DUE6BGL2E-MANUAL-D13 |
| DW-03 | 1 | 1.0 | 1.0 | DATA003-DUE6BGL2E-D03 / DATA003-DUE6BGL2E-D04 / DUE6BGL2E-MANUAL-D09 |
| DW-04 | 1 | 1.0 | 1.0 | DUE6BGL2E-MANUAL-D14 / DUE6BGL2E-MANUAL-D12 / DUE6BGL2E-MANUAL-D13 |
| DW-05 | None | None | None | DATA003-DUE6BGL2E-D02 / DATA003-DUE6BGL2E-D03 / DATA003-DUE6BGL2E-D04 |
| MW-01 | 0 | 0.0 | 0 | DATA003-MW23FDI-M06 / DATA003-MW23FDI-M02 / DATA003-MW23FDI-M03 |
| MW-02 | 1 | 1.0 | 1.0 | MW23FDI-MANUAL-M14 / DATA003-MW23FDI-M13 / DATA003-MW23FDI-M02 |
| MW-03 | 1 | 1.0 | 1.0 | DATA003-MW23FDI-M06 / DATA003-MW23FDI-M12 / DATA003-MW23FDI-M07 |
| MW-04 | 1 | 1.0 | 1.0 | DATA003-MW23FDI-M13 / MW23FDI-MANUAL-M11 / DATA003-MW23FDI-M06 |
| MW-05 | None | None | None | MW23FDI-MANUAL-M11 / DATA003-MW23FDI-M06 / MW23FDI-MANUAL-M15 |

None은 순위 평가 제외다. 무정답 질의의 최종 답변·추가 조건 요청·금지 주장 준수는 미평가다.
FR-04의 미지정 과거 문서 버전은 별도 runtime input에서 null로 고정해 현재 문서 검색을 하지 않았다.
기존 tokenizer/BM25 공식과 점수 ID 순 정렬을 유지했다. 형태소 분석·질문/정답 기반 튜닝은 없다.
실패·반환 점수·질문별 반복 시간은 results.json에 있다. 개발 기준선이며 실제 고객 수요나 독립 평가 우위를 뜻하지 않는다.
Python BM25는 한 스레드/float64로 실행했다. FP32/4threads는 이후 tensor 모델 설정이며 두 종류를 동일하다고 표시하지 않는다.
새 출력 폴더 인자로 scripts/run_data003_bm25.py를 실행해 재현한다. 기존 준비/기존 bootstrap 결과를 덮어쓰지 않는다.
