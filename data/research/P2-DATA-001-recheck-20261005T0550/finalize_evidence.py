"""Build public evidence from this session; never copy credential files or PDFs."""
import json
import platform
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PRIVATE = ROOT / 'private/manual-preflight-20261005'
BASE = 'c6c1382faab29ffe06ee5d24c5ff0a196d5c1531'
PR_HEAD = '5af64e93b1ca413317a91893e530901fc7f5874e'
RECORD = '신진하-20261005-008-recheck-0550'
EVIDENCE = '신진하-E014-recheck-0550'
REL = OUT.relative_to(ROOT).as_posix()
NOW = datetime.now(timezone(timedelta(hours=9))).isoformat()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(name, value):
    path = OUT / name
    if path.exists():
        # Resume packaging after packaging-run1 failure; never overwrite earlier outputs.
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding='utf-8')
    else:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    audit = read(OUT / 'pdf-run3/audit.json')
    model = read(OUT / 'model-run1/model-result.json')
    visual = []
    for model_id, pages in {
        'T876MEE1H1': [1, 5, 18, 19, 21],
        'DUE6BGL2E': [1, 20, 23, 24],
        'MW23FDI': [1, 17, 18, 25],
    }.items():
        for page in pages:
            path = PRIVATE / 'pdf-run2' / f'{model_id}-page{page}.png'
            visual.append({'model_id': model_id, 'pdf_page': page,
                           'private_render_sha256': sha256(path.read_bytes()).hexdigest(),
                           'inspection': 'Codex tools.view_image: cover or cited operation visually reviewed'})
    write('visual-review.json', {'recorded_at': NOW, 'source': 'pdf-run2',
                               'same_original_pdf_hash_as_run3': True, 'pages': visual,
                               'pdfs_and_renders_kept_private': True})
    environment = {
        'observed_at': NOW, 'base_commit': BASE, 'personal_github_account': 'ginaginaring',
        'github_identity_verified_via_api_user': True,
        'personal_controller_setup_succeeded': True,
        'github_cli': {'version': '2.102.0', 'source': 'https://github.com/cli/cli/releases/tag/v2.102.0',
                       'official_archive_sha256': 'ae64e556ecc240b200f7eba60d550e4bb60d78e860e69dd88c449405b86067f4',
                       'installation': 'workspace-local portable CLI; no global PATH or auth file modification'},
        'python_for_model': 'existing project venv, Python 3.11.17; correct source added explicitly',
        'python_for_pdf': 'bundled workspace Python; pypdf 6.10.0 / PDFium',
        'uv': {'version': '0.12.23', 'existing_project_executable_readable_as_user': True,
               'new_dedicated_venv_created': False},
        'current_codex_chatgpt_login': 'codex login status succeeded as user; sandbox HOME discovery failed',
        'dedicated_codex_home_personal_login_verified': False,
        'dedicated_os_account_or_vm_isolation_verified': False,
        'publisher_broker_or_access_boundary_verified': False,
        'overall_unattended_readiness': 'partial; dedicated isolation and authentication still required',
        'worker_installed_or_started': False, 'automation_mode_changed': False,
        'pm_credential_files_read_or_shared': False,
        'model_proxy_owned_process_terminated': model['owned_proxy_stopped'],
        'model_proxy_port_listener_absent': 'elevated netstat TCP check after execution: no :18873 listener',
        'connectivity': 'controller and designated shared model responded during this session; no PC-off inference',
        'credential_handling': 'personal Git helper token verified in memory; new personal controller token stays private',
        'system': platform.platform(),
    }
    write('environment-readiness.json', environment)
    events = []
    for path in sorted(PRIVATE.glob('*receipt.json')):
        raw = read(path)
        if raw['action'] not in ('reserve', 'release', 'reserve-model', 'status', 'setup'):
            continue
        event = {'receipt_file': path.name, 'action': raw['action'], 'exit_code': raw.get('exit_code'),
                 'account': raw.get('authenticated_account'), 'credentials_printed': raw.get('credentials_printed')}
        if raw['action'] == 'status' and raw.get('exit_code') == 0:
            state = json.loads(raw['stdout'])
            event['state'] = {k: state.get(k) for k in ('global_mode', 'members', 'reservations', 'viewer', 'observed_at')}
        elif raw['action'] in ('reserve', 'release') and raw.get('exit_code') == 0:
            event['result'] = json.loads(raw['stdout'])
        elif raw.get('exit_code'):
            event['failure'] = raw.get('stderr', '') or raw.get('failure', '')
        elif raw['action'] == 'setup':
            event['result'] = 'personal enrollment succeeded; client/token kept private'
        events.append(event)
    write('reservation-history.json', {
        'reservation_id': 'manual-ginaginaring-data001-recheck-20261005T0550',
        'paths': [REL, 'docs/작업기록/신진하.md', 'docs/작업근거/신진하.md'],
        'resources': ['ginaginaring-manual-cpu-audit-20261005T0550', 'shared-model-qwen3-8b',
                      'ginaginaring-loopback-18873'],
        'events': events,
        'failures_preserved': [
            'Initial PDF run failed on escalated Git safe.directory ownership; pdf-run1/failure.json preserved.',
            'PDF run2: only 3 cover revision text checks failed because pypdf cover encoding; rendered covers reviewed.',
            'Model reservation private path rejected HTTP422; separate public reservation rejected HTTP409.',
            'HTTP409 was the same owner existing reservation, not another member; own reservation released then combined.',
            'First setup helper invocation used a runtime without httpx; switched to existing main venv.',
            'Sandbox uv access and Codex HOME discovery denied/failed; user-context read/status checks succeeded.',
        ],
        'release_confirmation': 'release-confirmation.json is written after the final release/status check',
    })
    queries = [
        {'id': 'DEV-SCOPE-FOLD', 'model_id': 'T876MEE1H1', 'document_version': 'MFL71401557 Rev.00_032526',
         'query': '접이식 선반이 이 정확 모델에 적용되는가?', 'relevant_ids': ['T876MEE1H1-MANUAL-F08'],
         'expected_interpretation': 'shared optional feature; exact SKU/quantity unconfirmed'},
        {'id': 'DEV-CLEAN', 'model_id': 'T876MEE1H1', 'query': '청소할 때 전원 플러그와 물기 처리는?',
         'relevant_ids': ['T876MEE1H1-MANUAL-F11', 'T876MEE1H1-MANUAL-F11-P05']},
        {'id': 'DEV-HEIGHT', 'model_id': 'DUE6BGL2E', 'query': '상단 바구니 높이 조절 조건은?',
         'relevant_ids': ['DUE6BGL2E-MANUAL-D09', 'DUE6BGL2E-MANUAL-D13-P24']},
        {'id': 'DEV-NOZZLE', 'model_id': 'DUE6BGL2E', 'query': '큰 식기가 노즐을 가리는지 어떻게 확인하나?',
         'relevant_ids': ['DUE6BGL2E-MANUAL-D13', 'DUE6BGL2E-MANUAL-D14-P20']},
        {'id': 'DEV-POWER', 'model_id': 'MW23FDI', 'query': '조리 출력은 몇 W를 선택하나?',
         'relevant_ids': ['MW23FDI-MANUAL-M11']},
        {'id': 'DEV-UNKNOWN', 'model_id': 'MW23FDI', 'query': '개인 설정을 저장하는 프리셋이 지원되지 않나?',
         'relevant_ids': [], 'expected_interpretation': 'not established by selected citations; never infer absence'},
    ]
    write('search-preparation/comparison-plan.json', {
        'created_at': NOW, 'base_commit': BASE, 'purpose': 'isolated preparation for #13/#14, no formal start or completion',
        'workspace': REL + '/search-preparation',
        'source_dataset': {'path': 'data/document_datasets/lg-three-models-20261005.json',
                           'sha256': audit['input_versions']['data/document_datasets/lg-three-models-20261005.json'],
                           'version': audit['dataset_version'], 'documents': 3, 'citations': 15, 'features': 9},
        'filters_before_ranking': ['model_id', 'document_id', 'document_version', 'source hash/currentness'],
        'candidates': [
            {'id': 'BM25', 'k1': 1.5, 'b': 0.75, 'tokenizer_revision': 'must pin before comparison'},
            {'id': 'BAAI/bge-m3', 'revision': '5617a9f61b028005a4858fdac845db406aefb181',
             'revision_source': 'inherited team candidate, not newly independently verified', 'license_verification': 'pending'},
            {'id': 'BAAI/bge-reranker-v2-m3', 'revision': '953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e',
             'revision_source': 'inherited team candidate, not newly independently verified', 'license_verification': 'pending'},
        ],
        'development_queries': queries,
        'independent_evaluation': False, 'ranking_executed': False, 'model_downloads': 0,
        'metrics': None, 'superiority_or_adoption_claim': False,
        'formal_dependencies': {'P2-DATA-001': 'ready/not done', 'P2-DATA-002': 'pending', 'P2-DATA-003': 'pending'},
        'next': 'PM assignment/dependency confirmation, validate candidate cards/licenses, pin tokenizer, independent Korean answers, reserve compute before measured comparison',
    })
    feature_rows = []
    for feature in audit['features']:
        cites = [c for c in audit['citations'] if c['evidence_id'] in feature['evidence_ids']]
        pages = ', '.join(str(c['page']) for c in cites)
        feature_rows.append(f"| {feature['feature_id']} | {pages} | {feature['description']} | {'; '.join(feature['conditions'])} | {feature['applicability_scope']} |")
    readme = f'''# #12 수동 재검증 — 2026-10-05 05:50 세션

{NOW} 작성. 개인 계정 ginaginaring / 기록 {RECORD} / 근거 {EVIDENCE}.

공식 PDF 3개와 인용 15개의 해시·원문·문서 개정판 검사는 54개 모두 통과했다. 문서의 적용 범위는 별도로 분류했다. 지정 모델의 실제 1회 생성은 JSON 검사와 digest 고정에 성공했지만, 공용 설명서의 선택 기능을 정확 SKU의 확정 기능으로 잘못 판단해 의미 검증에 실패했다. 성공으로 고쳐 기록하거나 프롬프트를 바꿔 재시도하지 않았다.

## 코드·자료 연결

- 기준 main: `{BASE}`. PR74 고정 head: `{PR_HEAD}`. main의 plan/dataset 바이트가 이 PR head와 같음을 확인했다.
- PR74는 PM이 닫았고 해당 자료 일부는 PR75/main에 인수됐다. PR74 자체 병합·DATA001 정식 완료·R03 인정·의존 해제를 주장하지 않는다.
- 실행별 원본 source SHA와 파일 SHA256은 `pdf-run*/audit.json`, `model-run1/model-result.json`에 있다. 모델 실행 당시 스크립트는 `model-run1/executed_model_check.py`, 인코딩 실패 당시 스크립트는 `pdf-run2/executed_audit_pdf.py`에 보존했다. 현재 model_check.py의 변경은 import 정렬뿐이며 실제 모델 재실행은 하지 않았다.
- 최종 게시 commit은 #12 자기보고의 두 고정 문서 링크로 연결한다. 이 README의 기준 commit은 실행 시점의 코드이며 게시 commit과 구분한다.

## 문서 버전과 적용 범위

| 연결 제품 | 공식 문서 버전 | PDF 자체의 모델 확인 | 인정 범위·남은 확인 |
|---|---|---|---|
| T876MEE1H1 | MFL71401557 Rev.00_032526 / 40쪽 | 표지는 상냉장 하냉동 공용 설명서, 정확 SKU 명시 없음 | 기존 승인 제품→설명서 연결은 계승. 일반 제거/청소 절차와 선택 기능 구분. 접이식 선반 적용·수량은 정확 SKU 근거 추가 필요 |
| DUE6BGL2E | MFL71959117 Rev.07_030626 / 60쪽 | DUE6 계열 등 공용 모델 목록, 정확 SKU 명시 없음 | 계열 설명서·기존 승인 연결의 바구니 절차. 모든 선택 기능을 해당 SKU에 적용하지 않음 |
| MW23FDI | MFL68822538 Rev.00_120925 / 40쪽 | 표지의 모델 목록에 MW23FDI 명시 | 해당 출력·30초 시간 증가·제조사 자동 데우기 메뉴. 개인 저장 프리셋 지원/미지원까지 입증하지 않음 |

원본 URL·전체 해시·인용 ID·PDF 쪽·추출문자 위치·텍스트 해시는 `pdf-run3/audit.json`에 있다. 페이지는 PDF 1부터 시작한다. 표지 및 모든 인용 관련 페이지 13장을 직접 렌더링해 검토했고 `visual-review.json`에 렌더 해시를 남겼다. 원본 PDF와 렌더는 private에 유지한다.

| 기능 ID | PDF 쪽 | 원문이 뒷받침하는 동작 | 조건 | 적용 범위 |
|---|---|---|---|---|
{chr(10).join(feature_rows)}

냉장고 선반 제거는 18/19쪽, 내부 청소는 21쪽, 청소 전 플러그 분리는 5쪽으로 구분했다. 식기세척기의 빈 바구니 상태 조절·양쪽 같은 높이·노즐 간섭·상단 바구니 없이 사용 금지 조건을 유지한다. 전자레인지 출력은 25쪽의 200/400/600/800/1000W다. **실제 고객 후기 0개이며, 설명서의 지시문은 고객 수요·발생 빈도·개선 효과의 증거가 아니다.**

## 실제 모델 검증과 실패

- 경로: 개인 client 설정 → loopback model_proxy(127.0.0.1:18873) → 기존 StructuredModelClient/OllamaAdapter → 인증된 공유 모델.
- `qwen3:8b`, digest `{model['expected_digest']}`, temperature 0, seed 42, context 4096, output 256, think false, timeout 45초. 실제 호출 1회.
- 입력/출력/schema/생성 옵션/사용량/실패는 `model-run1/model-result.json`, 원문 입력은 `prompt.txt`, schema는 `schema.json`.
- 기대: `shared_manual_only`, exact SKU false, demand false. 실제: `exact_sku`, exact SKU true, demand false. JSON은 통과했지만 적용 범위가 틀렸다.
- 이 사례는 개발용 진단이다. 독립 평가·일반화 성능·상품기획 Agent 완성을 인정하지 않는다. PM PC 연결은 이번에 성공했으므로 PC가 꺼졌다고 기록하지 않는다. 추후 연결 실패 시 실패 그대로 기록한다.

## 실행 환경·예약·보존

`environment-readiness.json`에 개인 GitHub 확인·개인 중앙 등록·기존 Codex 로그인·도구 환경·격리 미완료를 기록했다. 자동화와 네 개인 선택은 OFF, Worker 미설치/미실행. 전용 계정/VM·별도 CODEX_HOME 직접 로그인·publisher 경계 검증은 아직 남았다. PM 인증 파일은 읽거나 공유하지 않았다.

파일 3경로와 CPU/모델/포트 자원은 중앙에 예약한 뒤 실행했다. 별도 예약의 같은 소유자 충돌은 자기 예약을 해제하고 하나로 합쳐 복구했다. 상세는 `reservation-history.json`, 최종 해제/OFF 확인은 `release-confirmation.json`. 이번에 시작한 프록시 프로세스만 종료했고 종료 후 TCP18873 listener가 없음을 확인했다.

- `pdf-run1/failure.json`: Git 소유권 검사 실패. 이전 결과 보존.
- `pdf-run2/audit.json`: pypdf 표지 인코딩 때문에 버전 검사 3개 실패. 해시·인용은 통과. 렌더 확인 후 PDFium 표지 텍스트로 보완.
- `pdf-run3/audit.json`: 새 폴더에서 54검사 PASS.
- `model-run1/model-result.json`: 실제 모델 1회, 의미 실패 보존.
- `search-preparation/comparison-plan.json`: 별도 폴더의 #13/#14 비교 입력 준비만. 실행/성능 수치/모델 채택 없음, 선행 완료 처리 없음.

재현은 새 예약 후 **존재하지 않는 새 실행 폴더**를 지정한다. 두 runner는 기존 폴더 덮어쓰기를 거부한다. PDF runner는 pypdf/PDFium이 있는 bundled Python, 모델 runner는 Python3.11/httpx/jsonschema가 있는 프로젝트 환경을 사용한다. 모델 설정은 본인의 private client 파일이며 인증 파일을 복제하지 않는다.

```powershell
python -X utf8 {REL}/audit_pdf.py --run-directory {REL}/pdf-run-NEW
python -X utf8 {REL}/model_check.py --config private/본인/client.json --run-directory {REL}/model-run-NEW
```

## 인수인계

우선 PM/CORE 담당이 공용 설명서·정확 SKU·수요 근거의 검사를 구분해 이번 실패의 후속 조치를 배정해야 한다. 신진하는 정확 SKU 접이식 선반 적용 근거를 추가 확인하고 독립 평가와 #13/#14의 같은 한국어 정답셋/모델 카드·라이선스/revision/tokenizer 고정을 준비한다. 정식 완료·의존 해제·검수·병합은 PM의 실제 판정을 기다린다. 현재 사람의 즉시 조작 없이 수동 보고는 진행한다. 무인 실행 전에 전용 계정/VM과 별도 CODEX_HOME 개인 로그인·권한 경계 검증이 필요하다.
'''
    write('README.md', readme)
    log_path = ROOT / 'docs/작업기록/신진하.md'
    old_log = log_path.read_text(encoding='utf-8')
    marker = '## 재개 요약\n'
    before, after = old_log.split(marker, 1)
    current_log = f'''## 재개 요약

- 최신 `{RECORD}` / `{EVIDENCE}`, {NOW}. 직접 사용자 및 #12의 PM-20261005-DATA-AUTOMATION-PREP 지시로 최신 main을 분리 작업 공간에서 읽고 수동 재검증했다. 개별 상태는 **부분 검증 완료·실제 모델 의미 실패로 blocked 보고 예정**이며 PM 정식 완료는 아니다.
- 완료: 개인 GitHub ginaginaring/중앙 등록·예약, 공식 PDF3/인용15/9기능 적용 범위와 버전 확인(54 PASS), 지정 경로의 실제 Qwen 생성1회. JSON/digest 고정은 성공, 정확 SKU 판단은 실패. 실제 고객 후기0·독립 평가 미완료.
- 환경: 기존 Codex ChatGPT 로그인은 확인했으나 전용 계정/VM·별도 CODEX_HOME 로그인·publisher 격리는 미완료. 개발 자동화/개인 선택 OFF, Worker 시작 없음, PM 인증 파일 공유 없음.
- PR74는 닫힘, 부분 자료는 PR75/main `{BASE}`에 포함. DATA001 정식 완료 및 DATA002/003 선행 해제는 하지 않는다.
- 현재 브랜치 `codex/data001-recheck-20261005T0550`, 실행 기준 `{BASE}`, PR74 자료 head `{PR_HEAD}`. 기존 dirty 작업 공간을 보존하고 `{REL}`에 새 실행 폴더를 사용했다.
- 다음: 같은 게시 SHA의 두 개인 문서로 #12 blocked 보고 및 ACCEPTED 수신 확인. PM/CORE는 공용 설명서→SKU 잘못된 확정의 후속 조치 배정; 신진하는 정확 SKU 증거·독립 비교 준비. 예약 해제/OFF 최종 상태는 [release 확인](../../{REL}/release-confirmation.json)으로 연결한다. #13/#14는 별도 폴더의 비교 계획만 준비했다.

### {RECORD} — 최신 지침·개인 환경·공식 인용 재검증과 실제 모델 실패

- 작성 시각: {NOW}; 수행 AI: Codex / 신진하 / 분리 수동 작업 공간.
- 상태: 부분 검증 완료 / 의미 실패·환경 격리 미완료 / PM 검수·부모 완료 미확인.
- 지시 출처: 직접 사용자, #12 최신 PM 배정 PM-20261005-DATA-AUTOMATION-PREP. 이전 007/E013 결과를 보존하고 현재 원격 상태로 정정한다.

#### 사용자·PM 지시
> 사용자 발췌: “작업 전 파일·자원을 예약하고, 끝나면 해제하며, 새 실행 폴더를 써서 이전 결과를 보존해야 해.” “개발 자동화는 계속 OFF로 두라는 지시야.” “모델 ID·설정·입출력·실패와 작업 기록을 같은 코드 버전에 연결해서 남겨야 해. PM 인증 파일은 공유하지 않아.”

사용자는 #12에 실제 검증 결과 또는 막힌 이유를 보고하도록 직접 지시했다. 이 범위의 개인 브랜치 증거 게시/자기보고는 승인됐으며 예전 게시 대기 지시를 그대로 적용하지 않는다.

#### AI 해석·범위·가정
최신 운영 지침, 자기 Issue와 PM 배정을 확인하고 개인 환경의 실제 준비 수준을 나눠 기록한다. 인용 일치와 정확 SKU 적용·수요 입증을 각각 구분하며 작은 모델 생성 1회를 실행한다. 핵심 판단 코어/PM 정책을 수정하거나 선행 완료를 선언하지 않는다. 접속은 실제 상태로 판정하고 PM PC 꺼짐을 추정하지 않는다.

#### 예정 행동과 실제 수행
최신 AGENTS/공통 문서/개인 요약/PM 운영 지침과 #12/#28/PR74/#13/#14를 읽었다. 개인 계정을 확인하고 portable gh를 공식 체크섬으로 설치해 개인 등록했다. 파일/CPU/공유 모델/loopback포트 예약 후 새 폴더에서 PDF 재다운로드·해시·원문·버전·쪽 검사를 수행하고 표지와 인용 쪽을 렌더 검토했다. 개인 설정 프록시를 실행해 지정 StructuredModelClient로 한 번 생성하고 자신의 프록시를 종료했다. 추가 모델 재시도나 새 평가 답안은 만들지 않았다. 실제 작업·실패·재현 파일은 [세션 README](../../{REL}/README.md)와 E014를 따른다.

초기 Git 소유권 검사 실패, 표지 인코딩 실패, private 예약 거절·같은 소유자 중복 예약 충돌, httpx 없는 runtime 시도, sandbox HOME/uv 접근 실패를 보존했다. 충돌 원인을 다른 팀원으로 해석한 초기 설명은 자기 예약의 제한으로 정정한다. 각 재실행은 새 폴더를 사용했다.

#### 검증과 결과
공식 PDF3·인용15·기능9의 구조/원문/해시/개정판 54검사 PASS. 이는 정확 SKU 선택 기능·실제 수요 인정 검사가 아니다. 실제 Qwen1회는 native schema/local JSON/digest before+after 통과, 공용 접이식 선반을 exact_sku true로 잘못 판단해 의미 실패. 실제 고객 후기0, 독립 평가false, Agent 전체 구현은 별도. 표지 검토와 source SHA·실행 runner snapshot·모델 digest·옵션·입출력은 같은 증거 묶음에 연결한다.

#### 남은 일·인수인계
PM/CORE 담당의 적용 범위 검사 후속 배정이 우선. 신진하의 정확 SKU 증거·독립 정답셋/검색 비교는 남는다. #13/#14는 search-preparation의 계획만 준비했고 정식 상태를 바꾸지 않는다. 전용 계정/VM·별도 CODEX_HOME 직접 개인 로그인·publisher 경계 실증 전 무인 준비완료로 기록하지 않는다. 파일/자원은 최종 해제 후 OFF 상태를 확인하고 같은 게시 SHA로 자기보고한다. 발송과 ACCEPTED/보드 반영은 별도 수신증으로 남긴다. 사용자의 즉시 조작은 수동 보고에 필요하지 않으며 무인 실행 준비에는 전용 환경의 개인 로그인이 필요하다.

## 이전 재개 요약 — 당시 기록 보존
'''
    log_path.write_text(before + current_log + after, encoding='utf-8')
    evidence_path = ROOT / 'docs/작업근거/신진하.md'
    old_evidence = evidence_path.read_text(encoding='utf-8')
    before, after = old_evidence.split('## 현재 상태\n', 1)
    current_evidence = f'''## 현재 상태

최신 `{EVIDENCE}` / {NOW}. main `{BASE}`와 PR74 `{PR_HEAD}`의 공식 자료를 재확인했다. PDF3/인용15/개정판54검사 PASS와 실제 Qwen1회의 적용 범위 의미 실패를 함께 보존한다. 개인 GitHub·중앙 등록/예약은 성공했으며 전용 OS/별도 Codex 인증·publisher 경계는 미완료다. 자동화 OFF. PR74 부분 main 인수와 #12 전체 미완료·#13/#14 선행 미해제를 구분한다. 같은 게시 commit의 작업기록/근거 링크로 자기보고하고 실제 수신증은 별도로 확인한다.

### {EVIDENCE} — 원문 일치·모델 적용 범위·실제 의미 실패

- 관련 기록: `{RECORD}` / 신진하 / {NOW}.
- 근거 종류: 공식 원본, 고정 코드/자료, 실제 PDF·실모델 실행, 시각 검토, 인증된 운영 조회. 독립 평가가 아니다.
- 원본·버전·페이지·해시: [audit.json](../../{REL}/pdf-run3/audit.json)의 문서3개·인용15개, [시각 검토](../../{REL}/visual-review.json). 정확 SKU 미명시 공용 냉장고, DUE6 계열 식기세척기, MW23FDI 명시 전자레인지의 근거 범위가 다르다. 원본은 private에 보관.
- 실행 코드/입력: 기준 main `{BASE}`; 자료 head `{PR_HEAD}`; dataset lg-manual-scope-20261005.2. 실행시 runner snapshot과 file SHA256은 결과에 연결. [실제 모델](../../{REL}/model-run1/model-result.json)은 qwen3:8b/digest500a1f... 고정, temperature0/seed42/ctx4096/output256/thinkfalse, 개인 loopback proxy→StructuredModelClient, 1회 생성.
- 실제 결과: 원문/해시/개정판54 PASS; JSON/digest 검증 PASS; shared_manual_only를 기대한 사례가 exact_sku true로 응답해 의미 FAIL. 고객 수요 false 응답은 이 한 사례의 결과이며 수요 검증 성공으로 승격하지 않는다.
- 환경/예약/실패: [환경](../../{REL}/environment-readiness.json), [예약 역사](../../{REL}/reservation-history.json), [최종 해제 확인](../../{REL}/release-confirmation.json), [실행 설명](../../{REL}/README.md), 개별 checks는 final-checks.json. 개인 인증 파일·PM 인증 원문은 공개하지 않음.
- 지지하는 결론: PR74 자료의 현재 공식 파일/인용이 일치하고 문서 버전·동작·조건을 추적할 수 있다. 지정 개인 경로에서 실제 생성 가능하며 이 사례의 SKU 적용 추론은 실패한다.
- 지지하지 않는 결론: 접이식 선반 정확 SKU 적용·수량, 고객 수요/빈도/효과, 미언급 기능의 부재, 독립평가 성능, 검색 우수성, 전용 OS/인증 격리 완료, DATA001 Done/의존 해제/PM 승인/Agent 완성.
- 다음 검수: PM/CORE의 의미 실패 후속 조치, 정확 SKU 별도 공식 사양, 독립 평가 및 #13/#14 비교. [비교 준비](../../{REL}/search-preparation/comparison-plan.json)는 준비6질의만이며 실행/성능 수치/채택 없음.

## 이전 현재 상태 — 당시 기록 보존
'''
    evidence_path.write_text(before + current_evidence + after, encoding='utf-8')
    print(json.dumps({'created': True, 'record': RECORD, 'evidence': EVIDENCE}, ensure_ascii=False))


if __name__ == '__main__':
    main()
