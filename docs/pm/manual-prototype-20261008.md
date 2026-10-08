# 실제 자료 시제품 수동 실행 — 2026-10-08

이 문서는 팀원이 실제 공개 자료 작업실을 로컬에서 재현하는 시작법이다. 저장소 루트에서 PowerShell 터미널 두 개를 사용한다. 자동화·worker·예약 실행은 OFF 상태를 유지하며, 아래 CLI는 이들을 켜거나 모델 서비스를 자동 시작하지 않는다.

시작 스크립트는 [`scripts/serve_research_prototype.py`](../../scripts/serve_research_prototype.py)이다. `--help`로 확인한 인자는 다음과 같다.

| 인자 | 의미 |
|---|---|
| `--credential-file` | 필수. `token`과 선택적 `principal_id`가 있는 비공개 JSON |
| `--state-dir` | 필수. 작업실 DB와 실제 기획 실행 DB를 보존할 폴더 |
| `--port` | API 포트. 기본 18969, 숫자형 loopback에서만 제공 |
| `--enable-model` | 명시적으로 붙인 실행에서만 새 기획·조건 변경·국소 수리 모델 호출을 허용 |

## 1. 실행 환경과 자료

Python 3.11·uv와 Node.js/npm이 필요하다. Python 의존성은 루트의 `uv.lock`, 웹 의존성은 `apps/web/package-lock.json`을 사용한다. 새 체크아웃에서만 최초 설치한다. 이미 실행 중인 웹과 같은 폴더에서 `npm ci`를 다시 실행하면 서버가 깨질 수 있으므로, 준비된 환경에서는 설치를 생략한다.

```powershell
uv sync --locked
npm ci --prefix apps/web
uv run --no-sync python scripts/serve_research_prototype.py --help
```

현재 CLI는 새 R9 기본 자료 3개·기존 저장 결과를 위한 legacy 자료 4개·설명서 참고 묶음 1개, 총 8개를 등록한다. 새 버전의 ID가 분리되어 있으므로 기존 입력 자료를 덮어쓰지 않는다. 웹 목록에서도 **R9 기본 자료 / 이전 보존 자료 / 설명서 참고·리뷰 없음**을 구분한다.

| 새 기본 자료 | 자료 / 리뷰 | 위치 |
|---|---:|---|
| 식기세척기 R9 | 73 / 48 | `data/research/r9-public-runtime-20261008/dishwasher.research-bundle.json` |
| 냉장고 R9 | 58 / 48 | `data/research/r9-public-runtime-20261008/fridge.research-bundle.json` |
| 전자레인지 R9 | 53 / 45 | `data/research/r9-public-runtime-20261008/microwave.research-bundle.json` |
| 전자레인지 설명서 참고 | 5 / 0 | `data/research/r9-public-runtime-20261008/microwave.manual-reference.research-bundle.json` |

legacy 4개는 `data/research/r8-public-official-expansion-20261007/bundles/*.json` 3개와 `data/research/r8-public-competitor-adapter-20261007/fridge.development.research-bundle.json`이다. 새 설명서 참고 묶음의 ID는 `LGE-R9-microwave-manual-reference-20261008-v1`이며, 공식 설명서 5종의 참고 발췌·리뷰 0건이다. 설명서만 보고 새로운 고객 불편을 발견했다고 표시하지 않는다. 표의 수량은 현재 등록 파일 기준이며, 실제 웹 자료 목록을 다시 확인한다.

이 흐름은 실제 공개 리뷰·질문/공식 답변·문서 발췌를 사용한다. 원문에서 확인하지 못한 구매 SKU·게시일은 미확인으로 남으며, 전체 시장을 대표하는 표본으로 해석하지 않는다. 예전 합성자료 화면과는 별도인 **실제 자료 작업실**을 사용한다.

## 2. 인증 파일은 한 번 만들고 보존

기존 실행을 이어보려면 **기존 credential 파일과 기존 state-dir을 그대로 사용**하고 이 생성 절차를 생략한다. `principal_id`도 유지해야 기존 소유자의 기록을 불러오고 수정할 수 있다.

처음 시작하는 사람은 아래처럼 새로운 토큰을 비공개 폴더에 생성한다. 토큰은 공백 없는 32~256자여야 한다. 이 예시는 임의의 32바이트로 토큰을 만들며 터미널에 값을 출력하지 않는다. JSON은 Python이 읽을 수 있도록 UTF-8 BOM 없이 저장한다.

```powershell
$taskCredentialDir = Join-Path (Get-Location) 'private/research-prototype'
$taskCredentialFile = Join-Path $taskCredentialDir 'editor-client.json'
if (Test-Path -LiteralPath $taskCredentialFile) { throw '기존 인증 파일을 재사용하세요. 덮어쓰지 않습니다.' }
New-Item -ItemType Directory -Path $taskCredentialDir -Force | Out-Null
$taskTokenBytes = New-Object byte[] 32
$taskRng = [Security.Cryptography.RandomNumberGenerator]::Create()
try { $taskRng.GetBytes($taskTokenBytes) } finally { $taskRng.Dispose() }
$taskCredential = @{ principal_id = 'lgax-manual-local'; token = [Convert]::ToBase64String($taskTokenBytes) }
[IO.File]::WriteAllText($taskCredentialFile, ($taskCredential | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
```

`private/`는 Git 제외 경로다. 이 파일과 실행 DB에는 접근 권한을 가진 팀원만 접근한다. 모델 원응답·전체 호출 trace도 비공개 위치에 보관한다. 실제 토큰·SSH 주소·SSH 인증 정보는 PR·문서·스크린샷·메신저에 붙이지 않는다. CLI는 이 토큰을 editor 권한으로 등록하며, 웹은 토큰을 화면 메모리에만 보관한다.

## 3. 먼저 조회용 API와 웹 시작

터미널 A에서 실행한다. 경로는 저장소 루트 기준이다.

```powershell
uv run --no-sync python scripts/serve_research_prototype.py --credential-file private/research-prototype/editor-client.json --state-dir private/research-prototype-state --port 18969
```

`--enable-model`을 생략한 상태에서는 자료 목록·원문 조회와 기존 실행 ID 복구가 가능하다. 선택 공식자료 안내서 HTML/Markdown도 모델 없이 사용할 수 있다. 새 기획 생성은 활성화 대기 상태로 표시된다. 미리 만든 기획으로 대신 성공을 표시하지 않는다.

터미널 B에서 같은 저장소 루트로 이동해 실행한다.

```powershell
$env:LGAX_WORKSPACE_PROXY = 'http://127.0.0.1:18969'
npm run dev --prefix apps/web -- --host 127.0.0.1 --port 5175 --strictPort
```

브라우저에서 `http://127.0.0.1:5175/`를 연다. **실제 자료 작업실 연결**에 credential JSON의 `token`을 넣는다. Windows에서는 다음 명령으로 터미널 출력 없이 복사할 수 있다.

```powershell
Set-Clipboard -Value ((Get-Content -LiteralPath private/research-prototype/editor-client.json -Raw | ConvertFrom-Json).token)
```

자료 목록에서 R9 제품군을 고르고 원문·위치·모델·날짜·자료 한계를 확인한다. 저장된 실행은 그 실행에 사용된 자료 묶음을 고른 뒤 실행 ID로 불러온다. 다른 자료 버전에서 같은 실행을 불러오면 범위 불일치로 거절한다.

API는 `127.0.0.1:18969`, 웹은 `127.0.0.1:5175`에만 바인딩한다. 연구실 모델도 승인된 LG 전용 숫자형 loopback endpoint를 사용한다. 이 개발 서버를 `0.0.0.0`, 공용 프록시 또는 인터넷 공개 시연 서버로 바꾸는 절차는 포함하지 않는다. API의 Bearer 인증·Origin 허용 목록·쓰기 권한 검사를 그대로 사용한다. 포트가 이미 사용 중이면 기존 서비스에 붙이거나 종료하지 말고, 담당자와 자신의 실행 경로를 확인한다.

## 4. LG 전용 모델이 준비된 경우에만 생성 활성화

준비된 LG 전용 모델 서비스를 사용한다. 이 CLI는 Ollama 설치·모델 다운로드·GPU 선택·서비스 시작을 하지 않는다. 타 프로젝트 endpoint나 다른 사람의 프로세스를 재사용하지 않는다.

이번 2026-10-08 수동 실험 설정은 아래와 같다. `18975`는 이번에 준비된 LG 전용 loopback 연결이며 영구 운영 주소가 아니다. 유한 모델 세션이 끝나면 담당자가 준비한 LG 전용 endpoint와 같은 모델 pin을 확인하고 주소를 맞춰야 한다. 자동 재시작이나 예약 실행은 없다.

터미널 A에서 자신의 조회용 API를 `Ctrl+C`로 종료한 뒤 환경변수를 설정한다.

```powershell
$env:LGAX_MODEL_ADAPTER = 'ollama'
$env:LGAX_MODEL_ENDPOINT = 'http://127.0.0.1:18975'
$env:LGAX_MODEL_ID = 'qwen3.8:27b-q4_K_M'
$env:LGAX_MODEL_DIGEST = '25b843619e944cd0ae6069f94ff4e5e26a16e109ccbc0a66a0f05979ed70098e'
$env:LGAX_MODEL_TIMEOUT_SECONDS = '180'
$env:LGAX_MODEL_CONTEXT_TOKENS = '16384'
$env:LGAX_MODEL_MAX_OUTPUT_TOKENS = '4096'
$env:LGAX_MODEL_TEMPERATURE = '0'
$env:LGAX_MODEL_THINK = 'false'
$env:LGAX_MODEL_API_MODE = 'generate'
uv run --no-sync python scripts/serve_research_prototype.py --credential-file private/research-prototype/editor-client.json --state-dir private/research-prototype-state --port 18969 --enable-model
```

직접 Ollama의 seed는 어댑터에서 42로 고정된다. `from_env()`에 `LGAX_MODEL_SEED` 설정은 없으므로 별도의 가짜 seed 환경변수를 추가하지 않는다. 현재 기본 API 모드는 `generate`이며, 어댑터의 상세 설정·pin 검사는 [모델 어댑터 안내](model-adapters.md)와 [`model_client.py`](../../packages/core/src/lgax_core/model_client.py)를 따른다. 예전 문서의 8B 설정을 이 27B 실행 설정과 혼합하지 않는다. 과거 Qwen3.5 챗봇과 이 모델의 동일성은 확인되지 않았다.

모델 pin은 Ollama manifest digest다. 모델 이름이 같아도 digest가 다르면 같은 실행으로 취급하지 않는다. 현재 CLI는 새 기획당 모델 호출 최대 4회·문제 최대 1개·원문 항목당 최대 1,000자·기획 입력 prompt 최대 9,000자로 제한한다. 실제 선택6건 실험에서 출처 한계 설명이 길어져 기존 6,500자 한도에서 plan 호출이 차단된 것을 확인해 시작 스크립트의 입력 용량만 조정했다. 검수 규칙·공유 수정2회·모델 호출4회는 유지한다. 전체 bundle을 선택했다고 모든 원문을 모델이 전량 처리한다는 뜻은 아니다. 사용자 입력 범위와 모델 내부 샘플링·요약 인용 집계를 따로 확인한다.

## 5. 실제 사용과 저장 이력 재사용

- **새 기획 생성**은 선택한 원자료 묶음 전체를 서버 입력으로 사용한다.
- 아래 원문 체크박스를 고른 뒤 **선택 근거로 새 기획 생성**을 누르면 해당 원문 부분집합만 입력한다. 필터를 바꾸는 것만으로 실행 입력이 바뀌지는 않는다.
- **현재 결과에서 조건 변경**은 이전 실행의 입력 범위를 이어받는다. 다른 근거를 쓰려면 새 기획을 시작한다.
- 문제·반대 근거·기존/경쟁 대조·개선 전후 장면·관계 그래프를 살펴보고 인용 버튼으로 원문을 확인한다. 관계의 추론 표시는 인과관계 증명을 뜻하지 않는다.
- JSON/Markdown은 기획·근거 ID·입력 범위·원문 맥락을 보존한다. 다운로드 완료는 브라우저의 실제 파일로 확인한다. **스토리보드**는 30~45초 콘셉트 컷 구성 JSON/Markdown이며, 이 시제품의 생성 영상은 0개다.
- **선택 공식자료 안내서 HTML/Markdown**은 공식 설명서·FAQ·설치 안내·공식 답변의 선택 원문을 모델 호출 없이 모은다. 설명서 참고 5/0 묶음을 골라 해당 원문을 체크하면 사용할 수 있다. 리뷰나 고객 질문이 섞이면 선택을 고쳐야 하며 자동 누락하지 않는다. 안내서는 전체 정식 설명서를 대체하거나 구매 SKU의 적용을 확정하지 않는다. HTML은 파일로 내보내며 작업실 화면에서 실행하지 않는다.

`--state-dir` 아래 파일은 `r8-preview.research.sqlite3`(실제 기획 기록)와 `r8-preview.workspace.sqlite3`(기존 작업실)이다. 재시작할 때 같은 디렉터리와 credential을 쓰면 이력을 이어서 사용한다. 기존 디렉터리를 지우거나 새 DB로 바꾸지 않는다. 새로 생성한 credential이나 다른 `principal_id`는 기존 기록의 소유자를 바꾸지 않는다. 원등록 자료 hash도 같아야 조건 변경을 이어갈 수 있다.

수동 모델 세션이 끝나면 API를 `--enable-model` 없이 같은 경로로 다시 시작해 원문·저장 기획 조회를 계속할 수 있다. 이 조작도 자신의 API 터미널에서만 수행한다. 앱 화면 이동이나 연결 해제는 이미 서버에서 시작한 모델 요청의 취소를 보장하지 않으므로, 생성 버튼을 반복해 누르지 않는다.

이 시작법의 확인 범위는 CLI 도움말·환경변수 소비 코드·현재 자료 등록 경로·저장 DB 파일명·웹 proxy/Origin 연결이다. 문서를 썼다는 사실만으로 새 실행의 실모델 품질이나 브라우저 다운로드 성공을 추가로 주장하지 않는다.
