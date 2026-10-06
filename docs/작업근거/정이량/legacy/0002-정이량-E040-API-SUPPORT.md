<!-- member-log:entry v1; generated navigation, original content below -->
원본: `docs/작업근거/정이량.md` · source commit `84844b86d4d90faf341c0b19ef7407be274b9d17`

원문 byte 구간: 30..4369 · 원문 행: 3..15

[개인 목차](../README.md) · [원바이트 전체 원본](../archive/84844b86-original.md)

<!-- member-log:body:start -->
## 정이량-E040-API-SUPPORT — 팀별 키 발급 예정 문자와 사용 의무 구분

- 출처/의도: 정이량-20261006-005-API-SUPPORT의 실제 사용자 기록 요청·로컬 모델 사용 질문. 주최 측 발신 표기 문자 캡처의 마지막 10/6 14:34 메시지 원문을 확인했다. 발송 시스템/원 수신 기기의 독립 검증은 하지 않았다.
- 추가 근거: 사용자 “10만원 상당의 API 크레딧으로 지원한다는데? 개발용으로 탑재해도 되는거 맞나”. 100,000원 상당은 사용자 보고이며 원 문자 캡처의 금액이나 지급 키/잔액 실조회가 아니다. 참가작 개발/테스트·시연/평가와 개인 코딩 도구의 지원 사용 범위는 후속 확인한다.
- CI 최초 실패: PR162 head27ed04a의 python-and-harness는 stages/requirements의 근거 SHA 변경으로 차단됐다. 요건 문서를 갱신하고 과거 SHA만 유지한 메타데이터 누락이다. 원 문서 바이트/이전 SHA를 별도 보존한 뒤 실제 새 요건 대조에 따라 현재 근거 SHA만 갱신하며 게이트·완료 상태·제품 검사는 낮추지 않는다. 원 실패 run37420551026/37420545593을 보존하고 수정 후 CI를 별도 확인한다.
- 원본: `private/운영안내/20261006_LLM_API지원_문자.jpg`는 사용자 첨부의 원 바이트 사본. SHA와 비공개 원 경로/확인 시각은 `private/runtime/api-support-notice-20261006/source.json`에 기록한다. 발신 전화번호·기기 알림 등은 Git/Notion에 옮기지 않는다.
- 요건 대조: docs/대회요건.md·docs/2차제출_평가안내_2026-10-03.md·공식 추출 자료를 읽고 지정 공급사/API 의무·로컬/오픈소스 금지 조항의 존재를 확인했다. 해당 조항은 확보한 자료에서 발견하지 못했다. 후속 모든 안내의 무제한 허용이나 주최 측 허가 확인으로 확대하지 않는다.
- 독립 읽기 감사 `/root/api_support_rules_check`는 공식 2차 PDF 1·2쪽 전체와 주제 PDF 19·20·28~31쪽을 직접 시각 대조했고 지정 공급사·제공 API 필수·로컬/오픈소스 금지 조항을 발견하지 못했다고 보고했다. PDF 29쪽의 실행 Agent/Skill·모델/API 요구는 공급사 지정과 다르다. HWP 추출 텍스트의 구조 한계는 유지한다.
- 코드 기준: main e0f3baa7의 `StructuredModelClient.from_env`는 lab/ollama만 허용하고 loopback 주소·Ollama digest를 요구한다. 웹/MCP는 공통 코어를 사용하므로 공급사별 서버 어댑터를 추가할 위치가 있지만 키만 입력하면 작동하는 상태는 아니다. private workspace 인증·개인 Codex/Claude 구독은 공급 API 추론 키와 별개다.
- 실제 실행/한계: 이번 작업은 문서·메타데이터 갱신이며 새 모델/API 호출0·제품 테스트0·키 조회/저장0·자동화 변경0이다. 이전 8건의 정상 완료0을 새 main 모델 품질의 재실측으로 바꾸지 않는다. CI·메타데이터 검증·원격 공유와 Notion 재조회 결과는 아래 종료 보완에 추가한다.
- 지지하는 주장: 팀별 API 키 발급 예정·비용 지급과 구분·현재 사용 의무/병행 조건 미확인·기존 로컬 작업 유지·컨설팅 질문 준비. 지지하지 않는 주장: 키 발급/수령 완료·지정 모델/무제한 한도·로컬 금지/무조건 허용·제공 모델 품질 향상·전체 Agent 완료.
- 실제 검증/공유: 원 캡처 SHA256 a2fb3ffb30f61c37f66bc2742132409e789a118a15bae9ae400194d953d49537과 사본 byte를 대조하고 private Git 제외를 확인했다. signed bundled Python -I/-B로 고정된 메타데이터 검증기를 실행해 phase2_errors=[]·rules_identical=true를 확인했다. 제품 코드/테스트와 모델은 실행하지 않았다. 독립 문서 감사 blocker0·git diff --check 통과. Notion 개인용 연결의 접근404는 원 결과로 보존하고 기존 대시보드가 있는 Primary 연결로 정확 대상만 갱신했다. LG task_ab598dec3afb4e79a6ace6d4799205be·대시보드 task_06a78e94fd324bca97605b20c4602006 모두 succeeded; 재조회에서 두 안내·기존 본문 전체·동일 페이지 참조·truncated/unknown0을 확인했다. 이 결과는 evals/pm-notices/20261006/llm-api-support.json에 비밀 없는 투영으로 기록한다.


<!-- member-log:body:end -->
