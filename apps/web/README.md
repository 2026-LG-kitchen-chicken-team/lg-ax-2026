# 키친 상품기획 작업실

React·TypeScript·Vite 기반의 기획자용 웹 화면입니다. 요청 입력·근거 대조·콘셉트 비교·수정 이력 네 영역이 있고, **실제 서버**와 **계약 fixture** 두 모드로 동작합니다. 분석을 활성화한 작업실 서버는 실제 판단 결과를 저장하고, 웹은 완료·보류·실패 및 원문·수정 기록을 표시합니다. 분석을 활성화하지 않은 서버는 요청만 `not_implemented`로 저장합니다. 화면이나 규격 검사 통과만으로 상품기획 품질이 검증된 것은 아닙니다.

## 실행

검증 환경은 Node.js 22.23.2, npm 10.9.8입니다. Node.js 22 LTS를 사용하세요. Node 24에서도 테스트·빌드가 통과했습니다.

명령은 저장소 루트에서 실행하고, 서비스마다 터미널을 하나씩 엽니다.

```powershell
npm ci --prefix apps/web
uv run python -m lgax_api.server --host 127.0.0.1 --port 18867
npm run dev --prefix apps/web
```

접속 주소는 `http://127.0.0.1:5173/`입니다. 개발 서버가 `/api`·`/health`는 18867(합성자료 API)로, `/api/workspace`는 18869(작업실 API)로 전달합니다. 로컬 개발용 프록시이며 공개 배포·HTTPS는 포함하지 않습니다.

판단을 실제 실행하려면 PM이 구성한 모델 어댑터와 분석 활성화 작업실 서버를 사용합니다(`docs/pm/model-adapters.md`). 기본 서버 명령은 요청 저장용입니다. 별도 서버를 쓰는 경우 Vite 시작 전에 `LGAX_WORKSPACE_PROXY`로 작업실 주소를 지정합니다. 기존 서버를 덮어쓰지 마세요.

요청 저장과 실행 기록까지 쓰려면 작업실 서버를 추가로 실행합니다. 자격증명은 한 번만 만들며, `private/`에 저장되어 Git에 올라가지 않습니다.

```powershell
uv run python scripts/init_workspace.py --directory private/workspace
uv run python -m lgax_api.workspace_server --db private/workspace/workspace.sqlite --credentials private/workspace/server-credentials.json --port 18869
```

화면 위쪽 **작업실 서버** 칸에 `private/workspace/editor-client.json`의 `token` 값을 붙여 넣고 연결합니다. 토큰은 화면 메모리에만 있고 브라우저 저장소에 남지 않으므로, 새로고침하면 다시 입력해야 합니다. `viewer-client.json` 토큰으로 연결하면 읽기만 할 수 있습니다.

### 의존성 재설치는 `ci:safe`로

개발 서버(`npm run dev`)나 Playwright가 띄운 서버가 실행 중일 때 `npm ci`를 돌리면 `node_modules`가 지워지면서 그 서버가 깨집니다. Windows에서는 잠긴 `esbuild.exe` 때문에 설치가 반쯤 끝난 채 남습니다(2026-10-04 실제 사고). 재설치는 아래 명령을 쓰세요. 5173 포트가 열려 있으면 설치하지 않고 멈춥니다.

```powershell
npm run ci:safe --prefix apps/web
```

서버를 멈출 수 없으면 `git worktree add <다른 경로> <브랜치>`로 별도 작업 폴더를 만들어 거기서 설치·검사합니다. 같은 사람이 AI 세션을 여러 개 쓸 때도 세션마다 다른 worktree(또는 clone)를 쓰고, 같은 폴더에서 개발 서버와 설치·검사를 함께 돌리지 않습니다.

## 검사

```powershell
npm run test --prefix apps/web
npm run typecheck --prefix apps/web
npm run build --prefix apps/web
```

실제 작업실 서버 흐름 시험은 서버를 띄운 뒤에만 켭니다. `apps/web` 폴더에서 실행합니다.

```powershell
$env:LGAX_WORKSPACE_URL='http://127.0.0.1:18869'; $env:LGAX_WORKSPACE_CREDENTIAL_FILE='../../private/workspace/editor-client.json'; $env:LGAX_WORKSPACE_VIEWER_FILE='../../private/workspace/viewer-client.json'; npx vitest run src/liveWorkspace.test.ts
```

이 시험은 작업실 DB에 프로젝트를 하나 추가합니다.

### 브라우저 E2E (Playwright)

설치된 Chrome으로 실제 화면을 조작해 검사합니다. 개발 서버가 떠 있으면 그 서버를 쓰고, 없으면 직접 띄웁니다.

```powershell
npm run test:e2e --prefix apps/web
```

- fixture 흐름(항상 실행): 요청의 누락 질문 → 후보 비교·원문/판단 검토 → 내보내기 점검과 JSON 내용 → 수정 시간 측정과 조건 교정 재실행 → 측정 기록 JSON → 초안 Markdown. 측정을 취소하면 null로 남는지도 확인합니다.
- 실제 서버 흐름(선택): API 두 개를 띄우고 `$env:LGAX_E2E_TOKEN_FILE='../../private/workspace/editor-client.json'`을 설정하면 연결 → 저장 → 조건 교정 재실행을 실제 서버로 검사합니다.
- Chrome이 없는 환경(CI 등)에서는 `npx playwright install chromium`으로 브라우저를 받은 뒤 `$env:PLAYWRIGHT_CHANNEL=''`로 실행합니다. CI 워크플로에는 아직 넣지 않았습니다(PM 결정 사항).

## 수정 시간 측정 (E03)

수정 이력의 "다시 실행" 패널에서 **수정 목표**를 적고 "수정 시간 측정 시작"을 누르면, 재실행 요청이 저장될 때까지 걸린 시간을 초 단위로 기록합니다.

- 기록에는 시작·종료 기준과 바꾼 내용의 개수(후보 선택, 추가·삭제한 조건)가 함께 남습니다.
- 측정을 취소하거나 끝내지 못한 기록은 0이 아니라 `null`로 남깁니다.
- "수정 시간 기록 내보내기(JSON)"로 받은 파일의 `modification_seconds`는 `docs/pm/evaluation.md`의 측정 필드와 같은 규칙을 따릅니다.
- 기록은 화면 메모리에만 있으므로 새로고침 전에 내보내야 합니다.
- 화면 타이머 기록일 뿐이며, 같은 목표끼리 비교하기 전에는 시간 절감을 주장하지 않습니다.

## 두 모드

| | 실제 서버 | 계약 fixture |
|---|---|---|
| 자료 | 18867 합성자료 API, 18869 작업실 API | 번들된 `src/fixtures/` (FRIDGE-A만) |
| 요청 | 작업실에 프로젝트·실행으로 저장 | 공통 규격 검사만, 전송하지 않음 |
| 후보·이력 | 서버에 저장된 실행 기록 | 손으로 작성한 예시 실행 2개 + 브라우저 초안 |
| 표시 | 상단 상태와 작업실 연결 칸 | 노란 "모의 데이터" 배너, 상태 배지 "fixture 예시" |

fixture는 판단 Agent가 없을 때 화면 계약을 개발·시험하기 위한 예시입니다. Agent 출력이나 서버 응답이 아니며, 내보내기 파일에도 그렇게 적힙니다. `bootstrap.fixture.json`은 `data/demo/dataset.json`의 FRIDGE-A 항목을 그대로 복사했고, 원본과 같은지 테스트가 확인합니다.

## 네 영역

- **기획 요청:** 제품군, 대상 고객, 사용 상황, 개선 과제, 제외 조건(한 줄에 하나)을 입력하고 검토 모델을 하나 이상 고릅니다.
  - 빈 항목은 질문으로 표시하고 저장하지 않습니다.
  - 연결된 프로젝트와 제품군·모델 범위가 같으면 **변경 요청**(이전 실행에 연결, 요청 회차 증가)으로 저장합니다. 범위가 다르면 새 프로젝트로 저장합니다.
  - 원 요청 대비 변경표와 요청 회차를 보여 줍니다. 회차는 서버 규칙과 같은 방식으로 계산합니다.
- **근거 대조:** 제품군·모델·리뷰/설명서 필터와 원문 검색으로 위치·문서 버전·근거 ID·자료 성격(합성/공개 등)을 확인합니다. 작업실에 연결하면 프로젝트에 고정된 문서 버전 안에서 **서버 검색**을 합니다. 결과 0건은 오류가 아니라 "결과 없음"으로 표시합니다.
- **콘셉트 검토:**
  - 실행별 불편·기존 기능 대조표(모델·불편·기능·조건·판단·남은 불편·근거·질문)와 최대 3개 후보(차별점·요구사항·확인할 가정·근거 원문)를 보여 줍니다.
  - 후보 비교표가 있고, "원문·판단 함께 보기"로 후보 하나의 판단·원문 전문·가정·보류를 한 패널에서 봅니다.
  - JSON과 Markdown으로 내보낼 수 있습니다. 내보내기에는 보류 항목·실행 계보·**내보내기 점검**(인용 근거 원문·요구사항·가정·미확인·미해결·보류 누락 여부)이 함께 들어갑니다.
- **수정 이력:**
  - 원 요청·사용자 조건 변경·자료 버전 변경을 구분하며, Agent 내부 수정 횟수(최대 2회)는 별도로 표시합니다. 이전 실행의 연결이 누락·순환·타 프로젝트이면 비교를 보류합니다.
  - 이전 실행 대비 요청·후보·보류/실패 이유·질문 변화를 표시하고 저장된 판단 순서와 사용한 Skill을 보여 줍니다.
  - 추가 질문에 답변하면 원 실행과 연결된 새 요청으로 전달합니다. 답변은 기획 요청의 추가 정보이며 설명서 근거나 문서 범위 변경을 대신하지 않습니다. 빈 답변은 전송하지 않고, 취소는 기록을 만들지 않으며 저장에 실패하면 입력을 유지합니다.
  - "다시 실행"에서 후보를 유지·집중·제외하고 조건을 수정·삭제·추가한 뒤, 다음 요청을 미리 보고 연결된 새 실행을 만듭니다. 실제 서버 모드에서는 서버에 저장하고, fixture 모드에서는 브라우저 초안을 만듭니다.
  - 후보 선택은 공통 계약 안에서 제외 조건 "후보 제외: …"와 기획 요청 끝의 "[집중 검토: …]"로 전달됩니다.

## 오류 표시

공통 계약의 오류 코드는 모두 각자의 제목과 다음 행동으로 보여 줍니다.

- 인증·권한: `UNAUTHORIZED`, `FORBIDDEN`
- 기록·자료: `NOT_FOUND`, `DATASET_MISMATCH`, `INVALID_*`
- 판단 단계: `INSUFFICIENT_EVIDENCE`, `VALIDATION_FAILED`, `MODEL_UNAVAILABLE`
- 연결·계약: `CONNECTION_FAILED`, `CONTRACT_MISMATCH`
- 미구현: `NOT_IMPLEMENTED`

연결이 실패해도 샘플 자료로 몰래 대체하지 않고, 저장 요청을 자동으로 다시 보내지 않습니다.

## 계약과 자료

`packages/contracts/schemas/lgax.schema.json`을 직접 가져와 Ajv Draft 2020-12로 검증합니다. 웹에 스키마를 복제하지 않습니다.

- 실제 서버 모드: 브라우저는 API 응답만 사용합니다.
- fixture 모드: 번들된 fixture도 같은 계약 검사를 통과해야 화면에 표시됩니다.

모든 자료는 시연용 합성자료입니다. 실제 LG 제품 기능, 실제 고객 수요, Agent 성능을 입증하지 않습니다.

## 알려진 사항

- 공통 `WorkspaceClient`(`src/workspace.ts`)는 transport를 객체 메서드로 호출합니다. 브라우저의 `window.fetch`를 그대로 넘기면 "Illegal invocation"이 났었는데, PM이 기본값을 전역 호출 래퍼(`defaultTransport`)로 고쳤습니다(63112e6). 웹은 그 전부터 쓰던 `liveWorkspace.ts`의 `browserFetch` 래퍼를 계속 넘깁니다. 동작은 같습니다. 직접 transport를 넘길 때는 `fetch`를 메서드로 넘기지 말고 래퍼를 쓰세요.
- 브라우저 초안 실행(fixture 모드)은 새로고침하면 사라집니다.

## 의존성 선택

버전과 잠금 파일을 고정했습니다. 이 Windows 환경에서는 최신 Vite의 Rolldown 네이티브 모듈이 애플리케이션 제어에 막혀서, 검증한 안정 버전 Vite 7.3.6과 공식 `@rollup/wasm-node`를 사용합니다. 보안 설정은 바꾸지 않습니다. `npm ci`로 재설치한 뒤 테스트·빌드가 통과했습니다. 의존성을 바꿀 때는 같은 검증을 다시 실행하세요.
