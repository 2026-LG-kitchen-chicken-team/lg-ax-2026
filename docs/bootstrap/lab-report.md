# 연구실 모델 실행 기반 검증 — 2026-10-04

**실제 서버에서 검색 모델 2종, 생성 모델 1종, 한국어 OCR 모델 1종을 실행하고 전용 API까지 확인했다.** 이것은 개발에 필요한 실행 기반 검증이다. 제출한 Agent의 5개 Skill·31개 요구사항·3개 사용 예시 전체가 완성됐다는 뜻이 아니다. 운영 모델의 최종 채택도 아직 결정하지 않았다.

## 확보된 환경과 분리 범위

Ubuntu 22.04.5에서 전용 Python 3.11.17 환경을 만들었다. CPU 검색은 torch 2.8.0+cpu와 Transformers 4.57.1, 생성은 Ollama 0.34.0을 사용했다. 한국어 OCR은 별도 환경에 PaddlePaddle 3.0.0·PaddleOCR 3.2.0·PaddleX 3.2.0을 설치했다. Python·패키지·모델 파일은 전용 `/dev/shm/lg-ax-${USER}` 아래에 두었고 시스템 Python·시스템 패키지는 변경하지 않았다.

2026-10-04 04:18 KST 기록에서 A6000은 4장, 각 49,140MiB다. GPU 0은 LG Qwen service smoke에 5,672MiB를 사용했다. GPU 1의 기존 작업은 18,510MiB로 유지됐으며, GPU 2·3은 할당하지 않았다. root 디스크 여유는 15,215,292,416바이트(약 14.2GiB), tmpfs 여유는 약 106GiB다. root 공간을 아끼기 위해 16GB BF16 모델 대신 약 5.2GB Q4_K_M 모델을 사용했다. 임의로 기존 작업을 중지하거나 다른 프로젝트의 모델 캐시를 재사용하지 않았다. 자세한 관측값은 [server-inventory.json](../../evals/bootstrap-models/server-inventory.json)에 있다.

## 실제 실행한 모델

| 용도 | 모델 | 실행 형식 | 확인한 라이선스 | 고정 revision |
|---|---|---|---|---|
| 근거 검색 | BAAI/bge-m3 | CPU normalized CLS dense | MIT | `5617a9f61b028005a4858fdac845db406aefb181` |
| 근거 재순위 | BAAI/bge-reranker-v2-m3 | CPU, 필터 후 상위 10개 | Apache-2.0 | `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` |
| 작은 구조화 생성 | qwen3:8b | CUDA GPU 0, Q4_K_M, 4096 문맥 | Apache-2.0 | Ollama manifest digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41` |
| 한국어 문장 OCR | PaddlePaddle/korean_PP-OCRv5_mobile_rec | CPU, 문장 crop 인식 | Apache-2.0 | `c02ecaf1f22bfd1c618cce154fd19185b47e663a` |

라이선스와 사용 형식은 [BGE-M3 모델 카드](https://huggingface.co/BAAI/bge-m3), [reranker 모델 카드](https://huggingface.co/BAAI/bge-reranker-v2-m3), [Qwen3-8B 모델 카드](https://huggingface.co/Qwen/Qwen3-8B), [한국어 OCR 모델 카드](https://huggingface.co/PaddlePaddle/korean_PP-OCRv5_mobile_rec)를 확인했다. Qwen digest는 양자화된 Ollama 배포물을 식별하며 Hugging Face 원본 commit과 같은 값이 아니다. 모델 카드의 공개 성능을 우리 프로젝트의 성능으로 인용하지 않는다.

BGE-M3 공식 commit에 safetensors 파일이 없어 최초 safetensors 로딩은 실패했다. 공식 `pytorch_model.bin`을 torch 2.8의 제한된 `weights_only` 로딩으로 읽도록 바꾸고 정상 실행했다. `trust_remote_code`는 사용하지 않았다. 최초 Ollama 과정에서 Vulkan이 여러 장을 탐색하여, **LG 전용 프로세스만** 재시작하면서 Vulkan을 비활성화하고 CUDA GPU 0으로 제한했다.

## 검색 비교 결과

모든 입력은 자체 합성 자료다. 제품 5개·리뷰 36개·근거 42개에서 한국어 질의 6개와 수동 정답 근거 ID를 고정했다. 같은 corpus·질의에 BM25, BGE-M3, BGE+reranker를 적용했다. BM25 tokenizer는 공백·문자 기반이며 한국어 형태소 분석기는 사용하지 않았다.

| 방법 | 평균 recall@3 | 상위 3개 모델 혼입률 | 버전 혼입률 | 평균 질의 지연 |
|---|---:|---:|---:|---:|
| BM25, 필터 없음 | 0.667 | 0.500 | 0.111 | 0.83ms |
| BM25, 모델·버전 필터 | 1.000 | 0 | 0 | 0.83ms |
| BGE-M3, 필터 없음 | 0.667 | 0.333 | 0.111 | 161.42ms |
| BGE-M3, 모델·버전 필터 | 1.000 | 0 | 0 | 161.42ms |
| BGE-M3 + reranker, 모델·버전 필터 | 1.000 | 0 | 0 | 707.38ms |

**이번 자료에서는 BGE나 reranker의 품질 우위가 확인되지 않았다.** BM25도 같은 필터를 적용하면 동일한 recall을 얻었다. 모델·버전 혼입을 줄인 핵심은 구조적 필터다. 필터 효과를 임베딩 성능 향상으로 해석하면 안 된다. 검색 지연은 다운로드·모델 로딩·corpus 임베딩 생성 시간을 제외한 CPU 측정이다. BGE의 sparse·multi-vector 검색이나 GPU 처리량은 시험하지 않았다. 원문별 순위와 로딩 시간은 [retrieval-results.json](../../evals/bootstrap-models/retrieval-results.json)에 있다.

구현에서는 BM25를 기준선으로 유지하고, 더 넓고 독립된 자료에서 dense/retrieval 및 재순위의 개선을 확인한 뒤 운영 경로를 고르는 것이 적절하다. Agent 전체와 일반 LLM을 비교하는 제출 평가의 기준선 실험은 별도로 남아 있다.

## 생성과 한국어 OCR 결과

Qwen3:8b에는 냉장고·식기세척기·전자레인지·문서에 없는 기능의 4개 합성 입력을 주었다. JSON 필드 형식, 입력에 존재하는 근거 ID만 인용했는지, 제품 모델이 일치하는지, 기능 존재 여부가 fixture와 맞는지 확인했다. 4개 입력이 이 제한된 검사들을 통과했다. 문서에 없는 기능은 `null`로 남기고 질문을 작성했다. 지연은 각각 5,507.71ms·1,171.82ms·1,356.10ms·1,214.93ms다. 첫 입력에는 모델 로딩이 포함되어 있다. 토큰 수·원문 prompt·실제 출력·load_duration은 [generation-results.json](../../evals/bootstrap-models/generation-results.json)에 기록했다. 새로운 콘셉트 생성, 반박·수정 루프, 다회차 기억, 일반 정확도, 기획자 시간 절감은 이 시험으로 입증되지 않는다.

서버에 Tesseract가 없음을 확인한 뒤 시스템 설치 대신 공식 한국어 mobile 모델을 별도 CPU 환경에 설치했다. 내려받은 모델·설정 파일 합계는 13,885,563바이트다. 시스템 Noto CJK 글꼴로 자체 생성한 문장 이미지 2개에서 원문과 정확히 같은 텍스트를 얻었다. 문자 오류율(CER)은 두 건 모두 0, 인식 지연은 304.75ms와 124.03ms다. 그림을 직접 열어 한글 문장이 정상 표시되는 것도 확인했다. [ocr-results.json](../../evals/bootstrap-models/ocr-results.json)과 [첫 문장 이미지](../../evals/bootstrap-models/ocr/korean-text-1.png)에 근거가 있다. 깨끗한 문장 crop 결과이며, 전체 PDF 검출·페이지 레이아웃·표·사진·기울어진 스캔·제품 근거 연결은 아직 검증하지 않았다.

## 실제 서비스와 프로세스

- `ollama serve`: loopback `127.0.0.1:18864`, GPU 0, cloud 비활성화, 병렬 1개. 관측 PID 593597.
- `llama-server`: 위 전용 Ollama의 자식 생성 runner. 관측 PID 593856, 임시 loopback port 43573. 유휴 5분 뒤 내려갈 수 있으므로 PID와 포트를 고정값으로 사용하지 않는다.
- `python services/inference/server.py --port 18865`: private API. 관측 PID 593802, loopback `127.0.0.1:18865`.

PID는 04:18 KST 관측값이며 재시작 후 달라진다. 모델 다운로드·검색·구조화 생성·OCR 실험 프로세스는 완료됐고 상주 작업은 위 LG 서비스들이다. 이번 launcher 수정에는 고비용 모델 비교를 다시 실행하지 않았다. 기존의 다른 프로젝트 서비스는 변경하지 않았다.

전용 API의 실제 `health`, 검색 결과 조회, 생성 호출은 200으로 응답했다. 생성은 실제로 “전자레인지”를 반환했고, 빈 prompt는 422로 거부했다. health와 생성은 확인한 Qwen digest가 다르면 실행을 막는다. 실행 중인 API 소스 해시도 응답에서 확인했다. [service-smoke.json](../../evals/bootstrap-models/service-smoke.json)은 이 결과를 보존한다.

현재 API에는 인증이 없으며 loopback만 허용한다. 공개 MCP·공개 프록시에는 연결하지 않았다. 공동 사용 경로를 열기 전에 인증·프로젝트 권한·사용량 제한·실행 기록을 구현해야 한다. health의 ready는 모델 접근 상태이며 Agent 작업 완료 상태가 아니다.

## 재실행과 종료

실행은 [services/inference/README.md](../../services/inference/README.md)를 따른다. 코드와 결과는 전용 `~/lg-ax-2026`에 남지만 Python 환경과 모델 캐시는 tmpfs라 재부팅하면 사라진다. 재부팅 후 전용 설정과 모델 다운로드를 다시 수행해야 한다. 원본 가중치를 제출 ZIP에 포함한 상태가 아니다.

`lab_server_start.sh`와 `ollama_start.sh`는 기존 포트가 점유됐으면 중단하며, UID·실행 파일·전용 cwd·캐시·endpoint 환경·실제 포트 소유 PID를 모두 확인한 경우만 `--restart-own`을 허용한다. GPU 0에 외부 compute 프로세스가 있으면 Ollama 시작을 거부한다. 종료·포트 해제·새 프로세스의 bind와 실제 HTTP health가 확인된 뒤에만 PID를 저장하고 시작 성공을 표시한다. 20초 이내 확인되지 않으면 실패 원인을 반환한다. 전체 Python/Ollama 종료나 GPU 초기화는 하지 않는다.

최초 LG Ollama가 계정 home을 cwd로 사용하던 상태를 새 guard가 실제로 거부했다. 최초 LG PID 588883만 별도의 1회 migration에서 UID·실행 파일·원래 cwd·전용 캐시·endpoint·실제 포트 소유·GPU 점유를 모두 확인해 종료했다. 이후 전용 cwd에서 시작하고 두 서비스의 own restart를 실제로 검증했다. 기본 중복 start 거부, legacy cwd 거부, migration, 두 서비스의 시작/재시작, 실제 API smoke·inventory 등 9단계가 통과했다. [launcher-execution.json](../../evals/bootstrap-models/launcher-verified/launcher-execution.json)에 원시 결과가 있다.

실패 조건 회귀검사 6개는 stdlib mock으로 GPU·서비스·SSH 없이 실행되며 Windows와 서버 Linux에서 통과했다. CI에서는 `uv run python -m unittest discover -s services/inference -p test_launcher_guard.py -v`로 실행할 수 있다.

## 근거 일치 확인과 다음 작업

[models-manifest.json](../../evals/bootstrap-models/models-manifest.json)은 모델 revision·라이선스·형식, 실행 소스, 실제 입력 snapshot, 출력 artifact의 SHA-256을 묶는다. 서버의 실제 입력을 [input-dataset.json](../../evals/bootstrap-models/input-dataset.json)과 [input-queries.json](../../evals/bootstrap-models/input-queries.json)으로 회수했다. 입력 dataset SHA는 `97fe4b6badd54f3b64daf5e34f71033732e0e0b9d696d8bfc67b03b981512cf0`이며 현행 합성 demo·검색·생성·서비스 smoke의 입력 SHA가 일치한다. 각 실험 소스 SHA와 현재 코드도 일치한다. 파일은 LF로 보존했다.

```text
uv run python services/inference/build_manifest.py --check
```

이 검사는 CPU·GPU 모델을 재실행하지 않고 입력·소스·결과의 일치를 검사한다. models.lock 및 phase2 server/model 체크 등록은 PM가 담당한다. 자동 검사 통과와 실제 Agent 요구사항 완료는 분리한다.

수정 전 manifest·소스·launcher·입력·원시 실측 결과·보고서를 [원본 snapshot index](../../evals/bootstrap-models/history/20261003T190903Z-before-launcher-repair/snapshot-index.json)로 보존했다. 원본 모델 manifest SHA는 `4cd05d12151ffe236bee208983ae20567c0bcd4d30589995f07d3b97b6e084ba`이며 최초 Git commit `752edad170c8a20f95a761ddb5876e5ff10f862c`도 남아 있다. 새 manifest 검사는 원본 byte 해시까지 확인한다. 검색·구조화 생성·OCR 실측은 원본 그대로이며, launcher 수정 이후 서비스 smoke와 inventory만 새 실행으로 갱신했다.

다음 구현은 모델 라이브러리를 프로젝트 저장 상태·5개 Skill과 연결하고, 근거 부족·제품/버전 혼입·중복 기능·지시문 오염 등 실패 사례를 평가하는 일이다. PDF 자료 수집과 원문 locator, Agent의 검사·수정, 3개 사례 전체 실행, 일반 LLM 기준선 비교, 기획자 효용 측정, 웹·MCP 동일 코어 연결은 남아 있다. 이번 실험 결과를 제출 기능 완료로 바꾸지 않는다.
