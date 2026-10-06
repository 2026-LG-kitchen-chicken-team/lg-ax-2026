# 최신 소비자의 실제 Chromium 동향 재검증

PM 지정 source `79f31a912d307c4e8653b38dbb6fa7612e8a5443`에서 실제 API·MCP stdio·Vite·Chromium을 다시 연결했다. 합성 날짜팩과 원 날짜 미상 자료 각각 API/MCP 10/10, 브라우저 2/2로 총 **20개 대조·4개 브라우저 검사 PASS**다. 검사 source 원바이트 변경 0, 모델/GPU 호출 0, 호스트 제품 import/실행 0이다. [고정 버전·필터·분모·원출력 SHA](validation.json)와 [원바이트 실행 수신증](execution-receipt.json)을 제공한다.

|자료|10월 FRIDGE-A 분모|날짜 미상 제외|청소 주제 언급|브라우저 인계|
|---|---:|---:|---|---|
|별도 합성 날짜팩 `pm-synthetic-trends.v1`|3|2|1/3·33.3%, 근거 `DEMO-TREND-REVIEW-EVIDENCE-001`|같은 집계/모델/원문 ID를 기획 textarea에 추가|
|원 합성 리뷰 `0.1.0`|0|10|비율 null·자료 없음, 0%와 구분|원문 없음·인계 버튼 없음|

날짜팩 전체는 배정한 합성 날짜31·미상5이며 원36개 리뷰의 날짜 미상을 바꾸지 않았다. 각 fresh 프로젝트의 집계 ID는 새로 생성된다. **동일 ID**는 각 실행 안의 API/MCP/브라우저/내보내기 연결을 뜻하며 과거 프로젝트 ID를 재사용했다는 뜻이 아니다. [날짜팩 API/MCP](dated/api-mcp-path.json)와 [원 날짜 미상 API/MCP](undated/api-mcp-path.json)를 구분한다.

브라우저는 원 팀원 `trend-consumption.spec.ts`와 [최신 보완 검사](tools/supplemental.spec.ts)를 사용했다. 날짜팩 JSON 전체 aggregate와 viewed IDs, Markdown의 ID·모델·기간·버전·비율·원문 ID·경고가 실제 API 결과와 같았다. 두 자료의 실제 JSON/Markdown 다운로드 모두 주제 언급률이며 감정·불만/계절 수요가 아니라는 선언과 `kitchen-review-topics-candidate.v1`의 **PM 승인 전 미리보기 분류** 안내를 포함했다. 원문 text SHA `5cdc254e52b348ae5aba5f2af5b4228ece07acd6d9c4081dc008b818dd4142c3`, 문서1.0·FRIDGE-A·출처 ID를 실제 blockquote와 대조했다.

[선택 원문 PNG](dated/browser/pm-selected-original.png), [기획 인계 PNG](dated/browser/pm-planning-handoff.png), [날짜 미상 PNG](undated/browser/pm-empty-scope.png)를 직접 열어 숫자·문장·ID·자료 버전·합성/미리보기 경고를 확인했다. 기획 인계는 편집 가능한 textarea까지이며 저장·판단 실행을 하지 않았다. 기존 변경 비교표의 원 요청 열이 좁아 세로로 줄바꿈되는 시각적 후속 사항은 남아 있다.

## 원 실패와 유한 재실행

역사적 c916 [이전 검증](../trend-browser/README.md)·원 도구·수신증은 변경하지 않았다. 첫 최신 실행 `pm-trend-browser-current-4d8987b6c13744a4b0a3d357bd61194f`는 날짜팩 API/MCP10/10 및 원 팀원 E2E1개가 통과했으나 보완 검사34행의 이전 제목 기대 `리뷰 주제 언급 비율` 때문에 실패했다. 실제 화면은 의도된 새 제목 `리뷰 주제 언급 동향`과 새 의미 안내를 표시했다. 날짜 미상 경로는 이 첫 실행에서 미실행이다. [첫 원 수신증](prior-attempt.receipt.json)·private 로그/trace를 보존하고 제품 오류로 확대하지 않았다.

PM이 원 실패 보존과 현재 markup/labels에 한정한 유한 재실행을 명시 승인했다. [조정 diff](tools-adjustment.patch)는 새 폴더 도구만 바꾼다. runner의 보완 검사 위치1곳, 제목/의미 안내/청소 표시명 기대3곳을 현재 값으로 맞추고 JSON/Markdown 주제 언급·미리보기 선언4검사를 추가했다. 1/3·33.3%·원문 원바이트·ID·모델 scope·null·후보/합성 구분은 완화하지 않았다. 제품·원 자료·기존 팀원 E2E 변경 0이다. 조정 후 실행은 **1회**다.

## 실행 경계·재사용·한계

성공 실행은 `pm-trend-browser-current-0120f96ce581474c8f658a24d16b5d25`, source SHA `cf89aa43b3f6ade9f7f99505069a336749c0b48a0b078ce27f60bf393bc8e75a`(고정 source3006파일+새 평가 helper2파일), 40.063초 return0·중단 null·source_changed 빈 배열이다. proof 문서와 공개 복사본은 실행 후 작성했다. 101개 product/source-area rawpin과 공개 원출력19개 rawpin을 고정했다. 원 로그6개와 supervisor/input manifest는 private 실행 폴더에 보존하고 공개 JSON에 SHA를 연결한다.

동일 고정 image `sha256:5a234dd63a42d34e8ea3d47b93174be88d33635c34d07d048c66ce486ac831e5`, UID1000·network none·읽기 전용 root/workspace·capability drop-all·no-new-privileges·source/artifact 두 mount만 사용했다. publisher·AI·GitHub·controller 자격증명을 마운트하지 않았다. guest loopback18867/18881/5183만 사용하고 호스트5173에 접촉하지 않았다. 임시 애플리케이션 토큰은 guest tmpfs에서 생성·소멸하며 공개 JSON/Markdown은 token 검사 후 복사했다. 화면은 연결 후 또는 panel crop이어서 토큰 값이 보이지 않는다. raw trace·error context·로그는 공개하지 않았다.

Linux overlay 의존성과 쓰기 가능한 guest node_modules 루트/개별 이미지 entry symlink, 정상 guest Python venv/.pth 설치를 유지했다. [기존 고정 의존성 image 방법](../trend-browser/tools/dependencies.Dockerfile)과 [현재 guest runner](tools/browser_runner.py)를 사용한다. package/lock rawSHA 대조와 SDK 무수정 경계는 그대로다.

이번 검증은 합성자료·집계 소비 flow다. 정상 완료한 실모델 실행·판단 품질·실고객 시계열·수요/효과·외부 ChatGPT/Claude 계정 MCP·운영 배포·전체 웹 검사/build/CI를 증명하지 않는다. 다른 주제·계절·페이지·scope 변경 및 DATA183의 별도9날짜 시연팩은 별도 후속 범위다. 자동화 OFF를 유지한다.
