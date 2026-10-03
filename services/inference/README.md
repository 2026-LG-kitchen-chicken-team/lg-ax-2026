# 연구실 모델 실행 기반

이 폴더는 제품 근거 검색과 작은 구조화 생성 실험을 재실행하는 연구실용 기반이다. 제출할 상품기획 Agent, 5개 Skill, 31개 요구사항, 3개 사용 예시 전체의 구현 완료를 뜻하지 않는다. 공개 MCP의 읽기 도구와 연결되어 있지 않다.

2026-10-04 실제 실행 결과는 `evals/bootstrap-models/`와 `docs/bootstrap/lab-report.md`에 있다. BGE 검색 품질이 BM25보다 좋다는 결론은 나오지 않았다. 제품 모델·문서 버전 필터는 세 방법에 모두 필요하다.

## 준비와 재실행

서버의 본인 전용 `~/lg-ax-2026`에 이 저장소의 `services/inference/`, `scripts/model_benchmark.py`, `data/demo/dataset.json`, `evals/bootstrap-models/queries.json`을 복사한다. 계정 비밀번호, 사설 호스트명, 모델 파일은 저장소에 넣지 않는다.

```bash
cd ~/lg-ax-2026
bash services/inference/lab_setup.sh
bash services/inference/run_lab.sh scripts/model_benchmark.py
```

설정은 Python 3.11.17, CPU용 torch 2.8.0과 버전이 명시된 의존성을 전용 tmpfs에 설치한다. 모델 다운로드도 `/dev/shm/lg-ax-${USER}` 아래로 제한한다. root 디스크 여유가 5GiB보다 작으면 설정을 중단한다. BGE-M3 및 reranker는 코드에 기록한 Hugging Face commit을 사용한다. BGE-M3의 공식 commit에는 safetensors가 없어, torch 2.8의 제한된 `weights_only` 로딩으로 공식 `pytorch_model.bin`을 읽는다. `trust_remote_code`는 사용하지 않는다.

이미 검증된 로컬 Ollama 실행 파일을 `LGAX_OLLAMA_BINARY`로 지정한다. 이 변수에는 실행 파일 경로만 넣으며 기존 추론 서버 주소를 넣지 않는다.

```bash
export LGAX_OLLAMA_BINARY=/absolute/path/to/verified/ollama
bash services/inference/ollama_start.sh
OLLAMA_HOST=127.0.0.1:18864 "$LGAX_OLLAMA_BINARY" pull qwen3:8b
bash services/inference/run_lab.sh services/inference/generation_benchmark.py
bash services/inference/lab_server_start.sh
curl --fail http://127.0.0.1:18865/health
```

Ollama는 CUDA GPU 0, loopback 18864, 자체 모델 캐시, 병렬 1개, 문맥 4096, cloud 비활성화로 실행한다. `qwen3:8b` 태그는 바뀔 수 있다. 생성 실험과 health/API는 확인된 manifest digest와 일치하는 모델만 사용하며, 다른 digest면 재검토 전까지 실행을 막는다. 태그를 내려받았다는 사실만으로 같은 모델이라고 판단하지 않는다.

서비스는 loopback 18865만 열며 별도 인증이 없다. 필요할 때 본인의 SSH 터널로 접속한다. 공용 프록시·Tailscale 공개 경로·공개 MCP에 이 서비스를 그대로 연결하면 안 된다. `POST /generate` 호출은 실제 GPU 작업을 수행한다. 본격 통합 전에 인증, 사용량 제한, 실행 기록과 프로젝트별 권한을 구현해야 한다.

`GET /health`는 검증된 모델의 다운로드 및 전용 endpoint 접근 상태만 확인한다. `GET /bootstrap/retrieval-results`는 완료된 검색 실험을 읽는다. Agent의 분석·검사·재시도·콘셉트 완성 여부를 health가 보장하지 않는다.

## 기존 서비스 보호와 종료

18864 또는 18865가 이미 사용 중이면 기본 실행은 중단한다. `--restart-own`은 UID·실제 실행 파일·전용 cwd·모델 캐시·endpoint 환경·정확한 포트 소유 PID를 모두 확인한 경우만 해당 LG 프로세스를 재시작한다. GPU 0에 다른 compute 프로세스가 있으면 Ollama 시작을 중단한다. 기존 LG 프로세스의 자식만 허용하며 다른 프로세스를 종료하지 않는다.

종료 후에는 프로세스와 포트가 실제로 해제되는지 확인한다. 새 프로세스가 정확한 포트를 소유하고 실제 HTTP health가 응답해야 PID 파일을 저장하고 시작 성공을 표시한다. 20초 안에 종료·bind·health가 확인되지 않으면 원인을 출력하며 성공을 표시하지 않는다. 실패한 신규 프로세스도 같은 identity가 확인되는 경우만 종료한다. GPU 메모리를 많이 쓴다는 사실은 성과 지표가 아니다.

중지 시 `runtime/ollama.pid` 또는 `runtime/lab.pid`의 PID가 여전히 LG 프로세스인지 `/proc/<PID>/environ`, `/proc/<PID>/cmdline`, `/proc/<PID>/cwd`로 확인한 뒤 그 프로세스만 종료한다. 전체 Ollama/Python 프로세스 종료나 GPU 전체 초기화는 하지 않는다.

모델 캐시·Python 환경이 tmpfs에 있으므로 서버 재부팅 후 사라진다. 코드와 결과 JSON은 `~/lg-ax-2026`에 남는다. 재부팅 뒤 위 준비 절차를 다시 실행한다. 현재 단계에서는 모델 가중치를 저장소 ZIP에 넣지 않으며, 재실행 Skill과 실행 README에는 이 다운로드 조건과 정확한 revision을 연결해야 한다.

## 모델 선택의 한계

- BM25는 작은 한국어 합성 corpus에서 빠른 기준선이다. 형태소 분석을 사용하지 않는 공백·문자 단위 tokenizer의 한계를 갖는다.
- BGE-M3는 normalized CLS dense 임베딩만 시험했다. sparse·multi-vector 기능과 GPU 처리량은 이번 실험 범위에 없다.
- reranker는 모델·버전 필터 이후 상위 10개에만 적용했다. 이번 6개 질의에서는 품질 향상을 확인하지 못했다.
- Qwen3:8b Q4_K_M은 4개 합성 입력에서 구조와 근거 ID, 모델 일치, 기능 존재 판정을 시험했다. 새로운 콘셉트·자체 검토·재시도·기획자 효용은 아직 시험하지 않았다.
- 한국어 PP-OCRv5 mobile text recognition을 CPU에서 실제 실행했다. 깨끗한 합성 한글 문장 이미지 2개는 정확히 인식했지만, PDF 전체·표·스캔 문서의 추출 및 근거 연결은 아직 검증하지 않았다. 전체 문서 수집 기능의 채택 완료를 뜻하지 않는다.

한국어 OCR 실험을 재실행하려면 별도 CPU 환경을 사용하는 아래 명령을 실행한다. 고정된 PaddlePaddle/PaddleOCR/PaddleX와 Hugging Face model commit을 사용하며, 시스템 패키지를 설치하지 않는다.

```bash
cd ~/lg-ax-2026
bash services/inference/ocr_setup.sh
```

그림은 시스템 Noto CJK 글꼴로 코드가 자체 생성하는 두 문장이다. 글꼴 파일을 재배포하지 않는다. 문장 crop 인식만 사용하며 검출·문서 방향·레이아웃 모델을 자동 다운로드하지 않는다.
