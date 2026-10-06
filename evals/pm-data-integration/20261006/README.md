# DATA collector의 명시적 API/MCP 연결 검증

사용자의 DATA 연결·WEB/MCP 통합 진행 승인 안에서 PM collector 설정 경로와 별도 합성 날짜 시연 자료를 구현했다. 기존 계약·권한·원자료·자동화 OFF를 유지한다. 코드와 파일 고정값, 실행별 원 receipt/log SHA 및 미완료 조건은 [runtime-validation.json](runtime-validation.json), 실행 방법과 자료 성격은 [별도 자료팩 README](../../../data/demo/review-trends-dated/README.md)를 따른다.

## 실제 확인한 범위

서버는 명시적 sidecar 경로와 **파일 원바이트 SHA**를 함께 받고, JSON/계약·dataset 버전/정규 해시·annotation 해시·원문/출처/모델/문서 버전·전체 리뷰 연결을 검사한 뒤 collector를 고정한다. 후보는 합성 preview 플래그가 필요하다. 이 플래그나 파일 이름은 PM의 리뷰별 분류 의미 승인 증명이 아니다. HTTP/MCP 요청으로 sidecar나 승인 여부를 선택할 수 없고, 기본 실행은 기존 미연결 501이다. 공개 bootstrap의 `--dataset`은 합성 `DemoStore`만 허용하며 모델 실행을 추가하지 않는다.

새 8개 검사는 비밀·AI 프로필·controller를 마운트하지 않은 고정 Docker에서 모두 통과했다. 실제 임시 loopback HTTP와 MCP SDK stdio 세 도구가 같은 aggregate ID·집계·원문을 읽었고, 401/403·no-store·저장 결과/페이지의 재시작 보존과 변경된 자료에서 새 집계 409도 확인했다. `client_kind=web` HTTP는 브라우저 UI 검증이 아니다. SDK 호출은 ChatGPT/Claude 계정 안의 실제 연결·발견 증명이 아니다.

기존 승인 문서 plan에 고정된 냉장고 `T876MEE1H1`, 식기세척기 `DUE6BGL2E`, 전자레인지 `MW23FDI` **원 PDF 3개**도 새 고립 document repository에서 실제 파서로 HTTP 등록했다. 비인증 업로드 401, 인증 업로드, 모델/문서 버전/출처로 검색, repository 재생성 후 검색 및 원 PDF 바이트 보존을 확인했다. 파서 mock이나 OCR을 쓰지 않았다. 공개 합성 bootstrap에 이 실제 문서 store를 넘기면 거부된다. 이는 고립 환경의 등록/검색 기능 확인이며 운영 서버의 자료 등록·배포 완료가 아니다.

## 자료·날짜·계측 조건

원 36리뷰·CSV 8열·원 candidate sidecar의 raw SHA는 모두 유지했고, 원 날짜 36개는 `null/unknown/null`이다. 원 FRIDGE-A 10건은 undated 10·분모 0·ratio null인 빈 결과가 맞다. 날짜 시연은 별도 dataset `pm-synthetic-trends.v1`·새 review/evidence ID·새 출처와 sidecar 버전을 사용한다. 행 기준으로 날짜 31개를 **배정한 합성값**이며, 5개는 미상이다. 기간·제품·출처 필터 및 중복 제외 뒤의 고유 리뷰 수가 분모이며 2026년 10월 FRIDGE-A의 분모 3·청소 관련 언급 1은 시연용이다. 긍정 언급도 포함되므로 “주제 언급 비율”로 읽으며 불만률·감정·고객 수요·계절성으로 확대하지 않는다.

Docker image는 `sha256:76ed86b7e2a84169b14e6910b67d10a8453e0e58e53f8f2e9ef96e404df8d494`, UID 1000:1000, network none, root/workspace 읽기 전용, capability drop-all, no-new-privileges, source/artifact 두 mount다. 제품 import/실행은 guest만 사용했고 host는 고정 executor와 stdlib 메타데이터 처리만 수행했다. 모델 호출은 0이다.

기본 image에는 외부 PDF 추출 의존성 pypdf가 없어 실제 등록 검사에서 먼저 실패했다. 번들 pypdf 6.10.0(BSD-3-Clause)의 62개 공개 패키지 파일을 RECORD 해시 검증 후 읽기 전용 export에만 추가해 실제 등록을 다시 확인했다. 저장소 제품 의존성이나 Docker image를 변경하지 않았다. pypdf가 없는 일반 환경에서는 이 외부 추출 검사만 명시적으로 skip하고 나머지 7개 runtime 검사는 실행한다.

## 실패와 재검사

- 첫 7개 검사에서 테스트가 REVIEW-002의 “임시 보관” 분류를 “청소 관련”으로 잘못 기대했고, 청소 관련 1건뿐인 월 범위에 다음 페이지가 있다고 기대해 2개 실패했다. 기대값을 1로 정정하고 페이지 검사를 연 범위로 옮겼다. 원자료·sidecar·날짜 파일은 바꾸지 않았다. host receipt 작성기의 잘못된 필드명 오류도 원 log/input과 함께 보존했다.
- 이후 새 8개 검사는 외부 pypdf 부재로 1개 실패했고, 위의 검증된 외부 환경 공급 뒤 8/8 통과했다.
- 관련 회귀 84개 실행은 83개 통과·기존 공개 MCP stdio smoke 1개 환경 오류였다. SDK의 기본 자식 환경이 PYTHONPATH를 상속하지 않아 image의 이전 editable 경로를 읽었다. 부모 PYTHONPATH만 추가한 진단도 실패했다.
- 실패한 공개 stdio 한 건은 임시 guest venv의 정상 `.pth` 설치(source·image dependency·외부 pypdf)로 별도 재검사해 통과했다. 최종 재검사는 SDK를 수정하지 않았다. noexec `/tmp`의 복사 binary 및 image site 미포함 setup 실패와 allowlist 진단도 별도로 보존했다. **84개가 한 번에 전부 통과했다고 보고하지 않는다.**

실행 export는 commit `7745a0c352628227dbbdbc3389614e460ab49ec2`와 당시 미커밋 구현을 포함한 source SHA `ea663ef1af5270d1c493ce60e1325fc7b2b86831df402bd8c17280a7c8e4e399`다. 이후 WEB178/main을 반영했지만 검사한 구현 5개와 JSON 자료 3개의 원바이트는 동일하다. 공개 근거와 README만 검사 후 작성/정정했다. CORE agent 독립 소스 검수 차단 사항은 0개다.

PM의 최종 병합 head 전체/웹/CI 검사, 실제 운영 서버 적용, 실제 계정 MCP와 브라우저 연결, 리뷰별 주제 분류 의미 승인·실고객 날짜 근거·실모델 판단 품질은 별도 후속 조건이다.
