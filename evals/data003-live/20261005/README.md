# #14 검색·재정렬·OCR 실제 비교와 검토

사용자가 지정한 환경 확인→실제 비교→검토 자료 작성을 로컬에서 수행했다.
입력은 기존 질문15개·사실 요약27개와 원문6페이지의 수동 인식 영역14개다. 개발 평가이며 #13 통합·독립 최종 평가·PM 완료와 구분한다.
사용자 추가 지시에 따라 PR·이슈·push·상태 보고 등 원격 게시를 하지 않았다.

## 환경·모델 확인

기존 PC Python3.11 환경에는 실모델 패키지가 없었고 연구실 live SSH 연결 정보도 없었다. 작업 공간의 private/model-runtime에 전용 CPU 가상환경2개와 가중치를 준비했다.
기존 환경/시스템 패키지·GPU·다른 작업 공간은 변경하지 않았다. 공식 HF API의 revision/라이선스와 모든 내려받은 파일의 공식 LFS/Git 해시를 대조했다.
Windows의 초기 HF 캐시 심볼릭 링크 권한 실패는 일반 파일을 쓰는 local_dir로 해결했다. 관리자 권한·개발자 모드를 바꾸지 않았다.
Paddle 첫 import의 공용 dataset 캐시 쓰기 제한과 Windows native reader의 한글 절대경로 실패는 각각 호출 범위의 tilde 캐시 격리와 같은 파일의 ASCII 상대경로로 해결했다. HOME/USERPROFILE·설치된 라이브러리 코드·가중치·crop은 바꾸지 않았다. 초기 실패 로그도 private에 보존한다.

| 모델 | revision | 라이선스 |
|---|---|---|
| [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3/tree/5617a9f61b028005a4858fdac845db406aefb181) | 5617a9f61b028005a4858fdac845db406aefb181 | mit |
| [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3/tree/953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e) | 953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e | apache-2.0 |
| [PaddlePaddle/korean_PP-OCRv5_mobile_rec](https://huggingface.co/PaddlePaddle/korean_PP-OCRv5_mobile_rec/tree/c02ecaf1f22bfd1c618cce154fd19185b47e663a) | c02ecaf1f22bfd1c618cce154fd19185b47e663a | apache-2.0 |

CPU Intel64 Family 6 Model 140 Stepping 1, GenuineIntel, RAM 15.68GiB, Python 3.11.17. torch 2.8.0+cpu/Transformers 4.57.1, CPU4threads/FP32.
BM25는 Python float64/1thread다. 모델 로딩과 임베딩 인덱스 구축은 질의 지연에서 분리했고, 공유PC 외부 부하는 통제하지 못했다.
환경별 전체 의존성 freeze와 설치 로그는 연결된 근거에 보관한다. 연구실 서버 연결 성공을 주장하지 않는다.

## 검색 비교

같은 모델·정확한 문서 개정으로 필터한 뒤 검색한다. 모든 방법15문항×5회, warmup2회 별도. 순위 평균은 gold11문항이며 무gold4문항의 최종 의미 답변은 평가하지 않았다.

| 방법 | Hit@1 | Recall@3 | MRR@3 | median ms | p95 ms | 실패/75 |
|---|---:|---:|---:|---:|---:|---:|
| BM25 | 0.9091 | 0.9091 | 0.9091 | 0.634 | 0.926 | 0 |
| BGE-M3 | 1.0000 | 1.0000 | 1.0000 | 316.221 | 365.049 | 0 |
| BGE-M3 + 재정렬 | 1.0000 | 1.0000 | 1.0000 | 6006.497 | 9531.883 | 0 |

BGE-M3의 BM25 대비 첫순위 개선 문항: MW-01; 악화: 없음.

BGE-M3 + 재정렬의 BM25 대비 첫순위 개선 문항: MW-01; 악화: 없음.
재정렬을 더해도 이번 개발셋의 Hit@1이 늘지 않았다. 지연과 구현 복잡도를 추가하는 재정렬의 채택 근거는 아직 부족하다.

실제 tokenizer 최대 길이 119/256, truncation 없음. 모델·버전 혼입은 각 방법 원시 반복에서 검사했다.
모델 load: BGE 3444.7ms, 재정렬 1985.4ms; index 14486.3ms.
프로세스 전체 peak working set 4206.1MiB: 두 모델을 함께 올린 benchmark 프로세스의 값이며 방법별 메모리로 해석하지 않는다.
작은 curated corpus·수동 개발 질문의 결과라 전체 매뉴얼/운영 처리량/독립 모델 우열로 확대하지 않는다.

### BM25 MW-01 실패 분석

질문: ‘수동조리에서 선택할 수 있는 출력은 몇 W야?’ / 정답 근거 M11: 선택 가능한200/400/600/800/1000W.
Unicode word tokenizer에서 질의는 수동조리에서·선택할·수·있는·출력은·몇·w야로 나뉜다. M11과 정확히 일치하는 token이0개다.
M06 ‘최대 고주파 출력1000W’의 조건 문구에 있는 ‘수’만 일치해 점수2.1444로1위가 됐다. 나머지0점의 ID 정렬까지 겹쳐 M11이 상위3개 밖으로 밀렸다.
따라서 단순 ‘출력’ 중복보다 한국어 조사·어형/단위 결합과 의미 없는 공통 token에 의존한 것이 직접 원인이다. 기존 gold/corpus/tokenizer를 정답에 맞춰 고치지 않았다.

| 방법 | MW-01 상위3 근거 | Hit@1 |
|---|---|---:|
| BM25 | DATA003-MW23FDI-M06 / DATA003-MW23FDI-M02 / DATA003-MW23FDI-M03 | 0 |
| BGE-M3 | MW23FDI-MANUAL-M11 / DATA003-MW23FDI-M13 / DATA003-MW23FDI-M12 | 1 |
| BGE-M3 + 재정렬 | MW23FDI-MANUAL-M11 / DATA003-MW23FDI-M13 / DATA003-MW23FDI-M12 | 1 |

## OCR 실측과 PDF 추출 대조

Paddle은14영역×5회=70회, warmup2회 별도. 오류 0회.
NFC/공백 정규화 exact 8/14, macro CER 0.0690, micro CER 0.0687.
숫자값 15/15, 숫자 필드 전체일치 10/11, crop에 보이는 명시 단위 12/12.
warm 인식 median 309.342ms / p95 513.435ms, 모델 load 3188.9ms.
원문에 있는 ×/소수점/괄호/각주를 CER에서 삭제하지 않았다. 숫자 채점에서만 원문의 명시적 *1 각주를 값에서 구분했다.
오류를 결과에 맞춰 정규화하지 않았다. 실제1000 W∗1의 ∗는 원문 gold의 *와 달라 CER 오류이며, 고정 ASCII 각주 분리 규칙이 ∗1을 분리하지 못해 숫자 필드 전체일치도 실패했다. 본값1000이 맞다는 것과 각주/값 분리가 정확하다는 것을 구분한다.
MW 외형의 mm은 표 머리글에 있어 해당 crop의 단위 점수에서 제외했다. 모델/열 자동 연결 정확도는null이다. 수동 crop 좌표가 올바른 열을 지정했다는 것을 자동 layout 성능으로 바꾸지 않았다.

| 영역 | 원문 짧은 정답 | 실제 인식 | CER | 숫자 필드 일치 | 명시 단위 정답/전체 |
|---|---|---|---:|---|---|
| OCR-FR-LINE-01 | 선반 위에 있는 식품을 치운 후 | 선반 위에 있는 식품을 치운 후 | 0.0000 | None | None/0 |
| OCR-FR-NUM-01 | 10 cm | 10 cm | 0.0000 | True | 1/1 |
| OCR-FR-NUM-02 | 2.5 cm | 2.5 cm | 0.0000 | True | 1/1 |
| OCR-DW-LINE-01 | 높이를 3단계로 조절 | 높이를3단계로 조절 | 0.0909 | None | None/0 |
| OCR-DW-TABLE-01 | 598 mm X 815 mm X 567 mm | 598 mm X 815 mm X 567 mm | 0.0000 | True | 3/3 |
| OCR-DW-TABLE-02 | 45 kg | 45 kg | 0.0000 | True | 1/1 |
| OCR-DW-TABLE-03 | 14인용 | 14인용 | 0.0000 | True | 1/1 |
| OCR-DW-TABLE-04 | 1600 W | 1600W | 0.1667 | True | 1/1 |
| OCR-MW-LINE-01 | 버튼을 누를 때마다 30초씩 | 버튼을 누를 때마다30초씩 | 0.0667 | None | None/0 |
| OCR-MW-TABLE-01 | 476 × 272 × 369 | 476×272×369 | 0.2667 | True | None/0 |
| OCR-MW-TABLE-02 | 23 L | 23L | 0.2500 | True | 1/1 |
| OCR-MW-TABLE-03 | 13 L) | 13 L) | 0.0000 | True | 1/1 |
| OCR-MW-TABLE-04 | 1570 W | 1570 W | 0.0000 | True | 1/1 |
| OCR-MW-TABLE-05 | 1000 W*1 | 1000 W∗1 | 0.1250 | False | 1/1 |

문자 불일치 영역: OCR-DW-LINE-01, OCR-DW-TABLE-04, OCR-MW-LINE-01, OCR-MW-TABLE-01, OCR-MW-TABLE-02, OCR-MW-TABLE-05. 원시 인식과 실패는 위 표/JSON에 그대로 보존했다.

pypdf는 원문14구절 모두를 추출 전문에서 찾았다. 이는 구절 존재 검사이며 CER·필드/단위·열 연결 정확도가 아니다. Paddle crop CER와 같은 분모의100% parser 성능으로 비교하지 않는다.
텍스트가 있는 현3개 PDF는 parser 우선이 합리적이다. OCR은 텍스트가 없거나 추출이 실패하는 페이지의 대체 후보로 두되, 실제 스캔/기울임/잡음/전체 페이지 검출·표 열 연결은 추가 검증이 필요하다.

## 검토 의견과 남은 일

검색은 BM25 기준선을 유지하고 위 질문별 dense/reranker 순위 차이를 PM이 원문과 대조해 검토한다. 이번 개발 평균만으로 운영 모델을 확정하지 않는다.
이번 자료셋의 #13 개발 연결 후보는 BGE-M3 dense다. BM25가 놓친 MW-01을 회복했고 다른 gold 질문은 악화하지 않았다. 재정렬 포함 전체 질의 중앙값은 약6초이고 같은 첫순위 정확도여서 현 조건의 기본 연결 후보에서 보류한다. 별도 자료·하드웨어에서는 다시 검증해야 한다.
BM25 개선은 형태소/단위 처리와 일반적인 불용어 정책을 별도 protocol에서 설계하고, 현재15문항을 튜닝 전용으로 전환한 뒤 새 독립 질의로 검증해야 한다. 이번 비교 중 tokenizer를 변경하지 않았다.
남은 정식 #14 작업: #13 실제 처리 출력 연결→실제 근거/조건·무정답 의미 검토→PM 인수·검수·병합·통합 확인. 원격 게시는 사용자가 요청할 때 수행한다.
현재 사용자 직접 해야 할 일은 없다. 연구실 결과를 별도로 재현하려면 접속 환경이 추가로 필요하지만 이번 CPU 실측은 로컬에서 수행했다.

## 재현·증거

- [검색 원시 결과](retrieval-v1/results.json)
- [OCR 원시 결과](ocr-v3/results.json)
- [파일·공식 모델 hash](downloaded-models.json), [환경 확인](online-preflight.json), [BM25 원인 계산](bm25-mw01-analysis.json)
- [실행/검사 기록](execution-checks.json), [무결성 검증](verification.json)

전용 retrieval-venv의 Python으로 scripts/run_data003_models.py retrieval --output 새-evals폴더, ocr-venv의 Python으로 같은 script ocr --output 새-evals폴더를 실행한다.
실측 runner는 offline/local_files_only이며 자동 추가 모델 다운로드가 없다. 기존 결과를 덮어쓰지 않는다.

## 검사 결과

입력·원문·모델 파일·실제 지표/CSV·실패 보존 무결성 216항목 PASS. 신규9시험·기존BM25 8시험·새 코드Ruff·계약·phase2 validate·동일 지침 검사가 통과했다.
전체 검사는 처음 공유 venv의 다른 checkout editable 코드를 읽어 실패했으며, 실제 module 경로를 확인하고 현재 worktree PYTHONPATH로 바로잡았다. 해당 초기 시도도 로그에 보존했다.
현재 worktree 전체492시험은491통과/Windows CI helper의 실패 경로 cleanup1실패였다. 코드 변경 없이 해당7시험만 단독 재검사해 모두 통과했다. 전체 첫 실행을 전부 통과했다고 표시하지 않는다.
웹 브라우저/build·MCP·독립 최종 평가·#13 실제 출력 통합은 이번 검사의 완료 범위가 아니다.
전용 환경의 전체 고정 패키지: [검색 requirements](retrieval-requirements-freeze.txt), [OCR requirements](ocr-requirements-freeze.txt). 설치 때 PyTorch CPU 공식 index를 사용한다.
