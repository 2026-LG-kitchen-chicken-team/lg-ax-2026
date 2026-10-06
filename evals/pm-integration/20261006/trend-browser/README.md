# 실제 Chromium의 동향 소비 경로 검증

PM이 지정한 source `c916b84598367eaa5d55f7e407b528300bb05d8d`에서 합성 날짜팩과 원 미상 날짜 자료를 각각 실제 API·MCP·Vite·Chromium으로 연결했다. API/MCP 20개 대조와 브라우저 4개 검사가 통과했고, 검사한 입력 원바이트 변경은 0이다. 실행 수신증·출력 원바이트 SHA·버전/필터/분모는 [validation.json](validation.json)에 고정했다. 제품 코드·계약·원자료는 변경하지 않았다.

| 자료 | dataset | FRIDGE-A 10월 분모 | 날짜 없음 제외 | 청소 관련 원문 | API/MCP | Browser |
|---|---|---:|---:|---|---:|---:|
| 별도 합성 날짜팩 | `pm-synthetic-trends.v1` | 3 | 2 | 새 ID `DEMO-TREND-REVIEW-EVIDENCE-001` 1건 | 10/10 | 2/2 |
| 원 36개 합성 리뷰 | `0.1.0` | 0 | 10 | 없음, 비율 null | 10/10 | 2/2 |

날짜팩 전체는 배정한 합성 날짜 31개·미상 5개이며 원 36개의 `null/unknown/null`을 보존한다. 10월 청소 관련 수치는 1/3건·33.3%다. 긍정·불편 모두 포함하는 “주제 언급 비율”이고 고객 불만률·판매량·수요·계절성·분류 정확도 승인이 아니다. `server`는 실제 HTTP 집계 경로를 뜻한다. 합성 날짜·후보 rule 분류·작은 표본 경고를 UI와 내보내기에 그대로 표시했다.

## 실제로 비교한 결과

- 지정된 production CLI가 파일/SHA를 선택한 고립 workspace API의 집계를 실제 SDK stdio `review_trends`, `get_review_trends`, `trend_evidence`로 읽고 같은 ID·JSON·원문을 확인했다. 웹은 동일 프로젝트를 선택하고 fixture 없이 서버에 다시 조회했다.
- [날짜팩 API/MCP 원출력](dated/api-mcp-path.json)과 [원 날짜 미상 원출력](undated/api-mcp-path.json)은 모델·문서 1.0·출처·기간·timezone·빈 topic filter·dataset/annotation 버전과 SHA·분류 method를 포함한다. 원문 문장 UTF8 SHA `5cdc254e52b348ae5aba5f2af5b4228ece07acd6d9c4081dc008b818dd4142c3`도 브라우저의 실제 blockquote와 대조했다.
- 변경하지 않은 팀원 E2E에 더해 [보완 검사](tools/supplemental.spec.ts)가 막대 1/3·33.3%·작은 표본, 선택한 `MONTH-2026-10/cleaning`, exact 원문/ID/문서 버전, JSON의 전체 aggregate 동일성·viewed IDs, Markdown의 ID/기간/자료 버전/비율/경고, 기획 입력의 동일 모델·월·주제·근거·판매량/수요 경고를 확인했다. 원문 전체를 기획 입력에 복사하지 않았다.
- 원 미상 날짜 경로는 분모 0·미상 제외 10·“자료 없음”을 보여 주고 0%로 표현하지 않으며 기획 인계 버튼이 없었다. 원 팀원 E2E가 빈 집계의 JSON/Markdown도 확인했다.

실제 엔진은 Playwright 1.63.0·Chromium `153.0.8010.12`다. [선택 원문 PNG](dated/browser/pm-selected-original.png), [기획 인계 PNG](dated/browser/pm-planning-handoff.png), [미상 날짜 PNG](undated/browser/pm-empty-scope.png)를 직접 열어 숫자·문장·경고·ID·버전을 시각 대조했다. 기획 인계는 편집 가능한 textarea에 추가한 것까지이며 저장이나 판단 실행은 하지 않았다. 기획 화면의 기존 변경 비교표가 좁은 열에서 세로로 길게 줄바꿈되는 시각적 후속 사항은 남겨 두었다.

## 실행 경계와 설치 조건

고정 image `sha256:5a234dd63a42d34e8ea3d47b93174be88d33635c34d07d048c66ce486ac831e5`에서 UID 1000:1000·network none·root/workspace 읽기 전용·capability drop-all·no-new-privileges·공개 source와 artifact 두 mount만 사용했다. publisher·AI·GitHub·controller 자격증명은 마운트하지 않았다. 모델 호출 0, host 제품 import/실행 0, host 서비스 접촉 0이다. API 18867/18881·Vite 5183는 guest loopback에만 열었다.

애플리케이션 토큰은 guest tmpfs 안에서 임시로 생성했다. 공개 후보 JSON/Markdown에 그 값이 없음을 guest에서 검사하고 screenshot은 연결 후 또는 동향 panel crop만 보관했다. 토큰 파일·raw trace·error context·API/Playwright log는 공개하지 않았다. 공개 자료는 지정된 proof·다운로드·PNG만 원바이트로 복사했다.

Windows NTFS의 node_modules I/O와 `/tmp`의 native 실행 제약을 피하기 위해 공개 package/lock 두 파일만 넣은 새 build context에서 [의존성 Dockerfile](tools/dependencies.Dockerfile)을 사용했다. base browser image `aebef576...`를 검증한 독점 local alias로 고정하고 `--network=none`에서 `/opt/npm-cache-seed`로 `npm ci --ignore-scripts --offline`을 수행했다. 143개 의존성은 image의 `/opt/lgax-web-dependencies/node_modules`에 설치했다. package SHA `8219df7f9a6ddec343dd28c1ecc740f6e5aef7e7cc87e275a2a4599a436aa6c6`, lock SHA `271f5c742de25ff68f71370684ca53218750e654ce75a62fa901a42e27953981`을 매 실행 대조한다.

재사용 시 같은 고정 image에 공개 source만 export하고 [guest helper](tools/browser_runner.py)를 실행한다. helper는 `/tmp`에 source를 복사하고, 쓰기 가능한 node_modules 루트 아래 각 의존성을 읽기 전용 image entry로 symlink한다. Vite cache는 guest tmpfs에 쓰고 esbuild 등 native 실행은 image 경로를 사용한다. Python은 symlink 기반 guest venv와 현재 source/image site의 `.pth`를 사용하므로 SDK 수정이 없다. 이 방법은 root의 후속 test/build 실행에도 재사용할 수 있지만 이번 브라우저 검증 자체가 전체 웹 단위 검사·build·CI를 증명하지는 않는다.

첫 설치에서 BuildKit의 `FROM sha256:ID` 해석과 실행용 빈 npm cache 경로 때문에 실패한 설정 시도는 command transcript 관찰로 구분했다. 최종 설치는 source alias pin과 image seed cache를 사용했다. 첫 browser 실행은 원 E2E 1개가 통과했으나 보완 검사의 nested 주제 select `getByLabel`가 timeout이었다. 제품/자료를 고치지 않고 보완 검사 selector만 정정했다. 원 실패 receipt/log와 최종 receipt/log SHA는 validation에 모두 남겼다.

최종 실행 폴더 ID는 `pm-trend-browser-36ccea29ad4b4447b997bf17f96d1155`, 입력 SHA는 `8b26531f12c9d1b3b6b48c6a0635a889971798c429e7307c2945c0137ee6d9c2`(고정 source 2925개+평가 helper 2개)다. 38.312초에 return 0, 중단 사유 null, source_changed 빈 배열이었다. proof 문서와 공개 복사본은 실행 후 작성했고, validation의 97개 product/source-area 원바이트 pin이 고정 source와 일치한다.

이번 결과는 지정 c916의 동향 소비 경로다. 이후 WEB179의 planning/liveWorkspace 변경과 대기 WEB180/181, 전체 웹/CI, 계절/다른 주제/페이지 추가/스코프 변경, 실제 계정 MCP, 운영 배포·실고객 날짜·실모델 판단 품질은 각각 후속 검증 범위다. 자동화 OFF를 유지한다.
