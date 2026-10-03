# PM 공통 프로젝트·권한·실행 이력

2026-10-04, 정이량 #19(P2-PM-003). 웹용 TypeScript 클라이언트와 전용 MCP stdio가 같은 loopback API/SQLite를 사용한다. 상품기획 판단·실제 콘셉트 생성은 아직 미구현이다.

## 시작

```powershell
uv run python scripts/init_workspace.py --directory private/workspace
uv run python -m lgax_api.workspace_server --db private/workspace/workspace.sqlite --credentials private/workspace/server-credentials.json --port 18869
```

초기화는 한 번만 한다. 기존 자격증명을 덮어쓰거나 자동 교체하지 않는다. 서버에는 토큰 SHA256만 저장하고 클라이언트 자격증명은 `private/workspace/{editor,viewer,admin}-client.json`, DB도 private에 보관한다. Git/Issue/Notion에 토큰이나 DB를 올리지 않는다. Linux 생성 파일은0600, Windows는 사용자 폴더의 기존 접근 권한을 따른다.

서버는127.0.0.1:18869만 청취한다. CORS는 개발 웹 localhost/127.0.0.1:5173만 허용한다. `/api/workspace`에는 Bearer 인증이 필수다. editor는 자기 프로젝트 생성/조회/기록, viewer는 같은 principal 기록 읽기, admin은 모든 principal 검토다. owner/admin을 요청 본문에서 받지 않는다. 개인 개발용 인증이며 대학 SSO/OAuth·팀원 전체 배포가 아니다. 공개18866 MCP·18867 합성 API·기존 Tailscale 경로·연구실 공개 범위는 유지한다.

## 저장 의미와 공통 계약

원본 `packages/contracts/schemas/lgax.schema.json`에 Workspace 정의와 오류 코드를 추가했다. 기존0.1.0 공개 계약은 유지하며 새 클라이언트는 이 정의를 포함한 main을 받아야 한다. Skill 스키마도 공통 정의에서 생성한다.

- 프로젝트: canonical Project/원 요청·소유자·선택 모델별 문서 버전·시각·자료 SHA256. 제품군/모델/자료 버전/문서 범위는 생성 때 고정한다.
- 실행: canonical Run/해당 원 요청·이전 실행 ID·사용자 입력 변경 회차·인증 principal·보고된 client 종류·시각·자료/문서 버전·미확인 사항. 원 실행을 수정하지 않고 새 실행으로 연결한다.
- `request_revision`: 첫 요청이 프로젝트 원본과 다르면1, parent와 같으면 유지, 달라지면+1. parent 없는 실행은 새 분기다. Agent 내부 `run.revision_count`와 별개다.
- 실행 POST의201/`ok:true`는 **요청 저장 성공**이다. 현재 `status=not_implemented`, `concepts=[]`, `output=null`이며 분석 성공으로 해석하면 안 된다. 실제 코어 결과 저장은 통합 단계다.
- client 종류는 호출자가 보고한 경로 정보이며 호스트/사람의 인증 증거가 아니다. actor_id는 서버 인증 principal에서 기록한다.
- 자료 SHA는 transport contract_version을 제외한 DemoDataset의 canonical UTF-8 JSON(정렬 키·공백 없음)을 해시한다. 파일 바이트 SHA와 다르다. 자료가 바뀌어도 옛 기록은 읽지만 기존 프로젝트 새 실행·현재 근거 조회는409로 거부한다.

## API와 클라이언트

| 경로(`/api/workspace` 뒤) | 기능 |
|---|---|
| GET/POST `/projects` | 허용 목록/생성 |
| GET `/projects/{id}` | 고정 범위·원 요청 |
| GET/POST `/projects/{id}/runs` | 이력/입력 추가 |
| GET `/runs/{id}` | 동일 실행 snapshot |
| GET `/projects/{id}/evidence?q=청소&model_id=FRIDGE-A` | 고정 문서 버전 원문 검색 |

생성 입력은 `{name,request,document_versions}`. request는 canonical PlanningRequest, 버전 map 키는 model_ids와 정확히 같다. 실행 입력은 `{request,previous_run_id:null 또는 ID,unconfirmed:[]}`. 필드는 공통 스키마를 따른다. 오류는 인증401·권한403·기록 없음404·자료 변경409·입력422, 유효한 빈 검색은200이다. 쓰기 요청은 자동 재시도하지 않는다. 응답이 불확실하면 목록과 ID를 먼저 확인한다. idempotency key·로그인 UI는 후속 범위다.

최길웅의 웹은 `apps/web/src/workspace.ts`의 `WorkspaceClient`를 사용한다. Vite `/api/workspace`는18869, 기존 `/api`는18867이다. `new WorkspaceClient('', () => currentCredential)`로 호출자 메모리에서 자격을 받고 localStorage/번들에 토큰을 넣지 않는다. 화면 연결은 #24/#25다. 이번 실제 웹 검증은 **TypeScript 클라이언트 HTTP 호출**이며 완성 사용자 화면/브라우저 검증은 아니다.

```powershell
uv run python -m lgax_mcp.workspace_server --url http://127.0.0.1:18869 --credential-file private/workspace/editor-client.json
```

전용 MCP는 stdio 전용이고 프로젝트/실행 저장·조회·이력·고정 근거 검색7도구를 API에 전달한다. 공개 읽기3도구와 다른 서버다. ChatGPT/Claude 계정의 **새 작업실** 연결·원격 OAuth 검증은 아직 하지 않았다. 초기 공개3도구 계정 검증과 구분한다.

## 실제 근거·후속

- [live-workspace-final.json](../../evals/pm-workspace/20261004/live-workspace-final.json): 실제 TS HTTP가 만든 프로젝트/실행을 MCP SDK가 동일 값으로 읽고 변경 요청 추가. API도 동일 값을 조회하고 원입력 불변·401/403·문서1.0 필터를 확인. 첫 실행 원본도 보존했다.
- [restarted-workspace-final.json](../../evals/pm-workspace/20261004/restarted-workspace-final.json): LG 전용 작업실 프로세스 실제 재시작 뒤 두 snapshot/미확인/자료 해시 보존.
- [모델 어댑터](model-adapters.md): 같은 Qwen 모델의 Lab/Ollama 교체·실제 구조화 호출. 상품기획 의미 검증과 별도.
- [Skill 계약](skills.md):5패키지/등록 방식. 조회만 실제이며4판단은 미구현. 청소 조회는 상충/긍정 리뷰도 반환하므로 모든 결과를 불편으로 단정하지 않는다.

황대겸 #8/#9는 모델 클라이언트·SkillRuntime으로 실제 판단/검사 handler를 연결한다. 신진하 #12/#13는 모델·문서 버전·원문 계약을 유지한다. 최길웅 #24/#25는 같은 ID·오류·변경 이력을 화면에 연결한다. 정이량 PM은 실제 코어 결과 저장·호스트/화면을 통합 검수한다. 신청서 R17/R24 전체 완료는 실제 결과까지 검증한 뒤 판정한다.
