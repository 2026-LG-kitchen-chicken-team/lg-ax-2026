# 실제 연결 검증

확인일: 2026-10-04 KST. 초기 연결은 합성자료 읽기 도구 3개이며 상품기획 판단 Agent 전체가 아니다.

## 주소와 재실행

로컬 API `http://127.0.0.1:18867`와 MCP `http://127.0.0.1:18866/mcp`는 Python 3.11의 같은 코어·계약·자료를 사용한다. 공개 MCP는 `https://eryang-lab.tailb7c3c1.ts.net/lg-ax/mcp`이며 현재 PC와 Tailscale 서비스가 살아 있어야 한다.

```powershell
$env:LGAX_MCP_ALLOWED_HOSTS='eryang-lab.tailb7c3c1.ts.net,eryang-lab.tailb7c3c1.ts.net:*'
$env:LGAX_MCP_ALLOWED_ORIGINS='https://eryang-lab.tailb7c3c1.ts.net'
uv run python -m lgax_mcp.server --transport streamable-http --host 127.0.0.1 --port 18866
```

Tailscale 443의 기존 `/` 및 다른 포트의 handler를 보존하고 `/lg-ax`만 `127.0.0.1:18866`에 추가했다. 공개 health는 `/lg-ax/health`다. LG 경로를 제거할 때 전체 `funnel off/reset`을 실행하지 않는다.

## 관찰 결과

- 실제 stdio 및 로컬 HTTP의 `initialize → tools/list → tools/call`을 실행했다.
- 공개 HTTPS에서 프로토콜 `2025-11-25`, 3도구 발견·정상 제품 조회·검색·빈 결과·잘못된 모델 ID·단일 근거 조회 총 5호출이 PASS였다.
- 공개 초기 요청은 host 목록에 포트 없는 이름이 빠져 421이었다. 정확한 공개 hostname과 `hostname:*`를 함께 등록해 재실행 후 PASS했다. DNS rebinding 검사는 유지했다.
- ChatGPT에 개인 플러그인 **LG AX Kitchen Evidence**를 생성·연결했다. 채팅에서 `list_products`, `search_evidence(q="청소",model_id="FRIDGE-A",document_version="1.0",limit=3)`, `get_evidence("MANUAL-001")`의 실제 결과를 확인했다. FRIDGE-A, 버전 1.0, MANUAL-001의 1쪽 ‘선반 분리’ 위치와 원문이 자료팩과 일치했다.
- ChatGPT 검증 대화: https://chatgpt.com/c/6ac14c22-d778-83e8-a04a-868c4c2d3c39 . 개인 계정 대화이므로 다른 팀원이 열람할 수 있다고 가정하지 않는다.
- Claude에는 같은 주소의 개인 커넥터를 생성·연결했고 읽기 3도구를 발견했다. 검증 대화에서 각 도구에 ‘한 번만 허용’을 사용해 실제 호출 3종이 성공했다. 같은 5개 모델·검색 3건/전체 4건·MANUAL-001의 모델 FRIDGE-A/버전 1.0/1쪽/선반 분리 위치와 원문을 반환했다. 승인 요구를 항상 허용으로 바꾸지 않았다.
- Claude 검증 대화: https://claude.ai/chat/00575822-2612-405f-9158-e326a381fb99 . 로그인은 사용자가 직접 완료했다.
- 직접 관찰한 대화·도구 결과는 `evals/bootstrap-connections/chatgpt-observed.txt`, `claude-observed.txt`와 두 PNG 화면에 보관했다. 화면 관찰·도구별 승인·서버의 실제 CallToolRequest 로그·자료팩의 값을 함께 대조했다. UI 생성 자체만으로 호출 성공을 추정하지 않았다.

## 접근 범위와 한계

공개 도구는 `list_products`, `search_evidence`, `get_evidence`뿐이다. 공개 자료는 자체 제작 합성자료다. 쓰기·서버 제어·연구실 생성 모델·개인 서류를 공개하지 않는다. 초기에 인증을 사용하지 않으므로 URL을 아는 누구나 합성자료를 조회할 수 있다. 실자료·팀별 프로젝트·쓰기 기능을 추가할 때는 인증/권한 경계를 별도 설계한다.

계정 내 플러그인/커넥터 생성·발견과 실제 호출을 구분한다. SDK 성공을 실제 ChatGPT/Claude 완료로 대신하지 않는다. 현재 단계는 채팅에서 도구를 사용하는 경로 검증이며 별도 패키지 배포·모든 사용자 설치·마켓 등록이나 자동 기획 판단 구현을 뜻하지 않는다.

연구실 접속/GPU·모델 버전·실측과 재실행은 [연구실 검증](lab-report.md)을 따른다. 연구실 생성 서비스는 loopback 전용이며 공개 MCP와 연결하지 않았다.
