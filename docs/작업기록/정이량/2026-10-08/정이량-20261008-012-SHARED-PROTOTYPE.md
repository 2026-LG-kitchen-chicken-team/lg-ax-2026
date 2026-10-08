# 정이량-20261008-012-SHARED-PROTOTYPE

KST 2026-10-08. 사용자 직접 요청: 종료 지시 전 링크 사용자용 웹/API·LLM을 유지하고 프로토타입 링크를 제공한다.

확인: gh 인증 jeongiryang. 본인 사서함 LG 관련 10/7 이후 조회에서 DATA 후속 PR281/278/276 전달을 확인했다. 이번 범위는 후속 PR 인수/의미 승인이 아니라 팀원용 프로토타입 서빙이다. 기존 디자인443133ca와 main eab85d4를 이어 사용하며 중복 개발/새 합성 리뷰/Figma/개발 자동화 ON은 없다.

실제 조사: 기존 R9 테스트 session은 로컬1700·원격1800초와 finally stop이 있다. 제품 요청도 keep_alive=5m이다. 연구실 GPU3 여유/보호 GPU1 프로세스/독립 포트를 확인했다. 기존 Tailscale 상태를 읽고 별도8443 추가를 시도했으나 사용자 권한·sudo 권한이 없어 실패했다. 기존 경로/ACL/서비스는 변경하지 않았다. 별도 소유 경로에 공식 cloudflared binary의 release digest를 대조해 저장했다.

구현: 공유 전용 gateway, 브라우저별 signed editor session, 실제 자료 전용 웹 자동 연결, 생성1개 제한, 원문/조건/이력 계약 보존, 상시 GPU3 모델 서비스. [상세 운영 범위](../../../pm/prototype-sharing-20261008.md).

자기 검수/배포/실모델/외부 브라우저 결과는 E059에 종료 보완한다. 구현만으로 접속 성공·LLM 의미 정확도·필수 CI/main 병합·정식 Done을 선언하지 않는다.

## 실제 완료 보완 — 2026-10-08 13:35 KST

- 공유 URL: https://consumption-tied-mens-alleged.trycloudflare.com/ . 외부 Chrome에서 로그인/토큰 입력 없이 연결, 실제10묶음 조회를 확인했다.
- 배포 source `0541ba02457055d28e3f7021fbaf907a2ca86bfb`. 연구실 소유 서비스 web/model/tunnel active·Restart=always·RuntimeMaxUSec=infinity·NRestarts0, 유휴 자동 해제 없는 모델 residency와 GPU3 pin을 직접 확인했다. 자동 Worker ON0/새 예약0/다른 프로세스 신호0.
- 실제 후기4·설명서2를 선택한 공개 웹 POST1은 88.176초·모델2콜(discover/plan)·수리0으로 complete. `run-f0ebcae46f5e4bbd8f087161fd801ce5` 저장과 화면의 양면 요약/기획 연결/개선 장면/관계 그래프를 확인했다. 별도 empty preload1은 기획 생성 호출과 구분한다.
- WEB46 PASS/선택 DATA3 SKIP·safe-ci4 PASS·tsc/build PASS. 백엔드61 PASS(신규gateway13 포함). 규칙 동일/계약/phase2/navigation PASS. 인증 없는 Docker readonly/networknone 검사이며 필수 GitHub CI 성공/병합으로 확대하지 않는다.
- 공개 smoke: bootstrap/health/bundles200·10묶음, 무토큰401·타Origin403·Origin 없는POST403·기존workspace/model직접endpoint404. credentials 출력/기록0.
- 원 실패: 초기 mock response stream 소비로3subcase 오류를 test helper만 수정; 61시험 뒤 Git history 없는 archive의phase2 FAIL은 history bundle로 별도gate PASS; WEB receipt 이후 CP949 wrapper 로그 오류는 검사/build PASS와 분리. SSH warm read timeout30초 뒤 실제 preload45.9초 완료를 읽기 대조했다. 새 모델 재호출0.
- 서비스 예약 종료는 없으나 하드웨어/망 장애와 Quick Tunnel 재생성의 주소 변경은 남는다. 모델 tmpfs는 연구실 재부팅 시 재확보가 필요하며 이를 상시 무장애 보장으로 표현하지 않는다. 브라우저마다 이력 분리·생성 동시1건; 쿠키 삭제/다른 브라우저는 새 작업실이다.
- 품질 제한: 원문 주체/희망·경험/기간 오독과 가정 장면 등 기존 CORE 보완은 유지한다. 이번 결과에서도 다리 아픔을 관절 질환으로 단정하거나 원문에 없는 분해/청소 포기를 이전 장면으로 넣는 문제가 있어 독립 의미 승인 false를 유지한다. 사용자에게 AI 초안으로 안내한다.
- 팀원은 링크 → 자료 묶음/원문 선택 → 선택 근거로 새 기획 생성으로 시험한다. 새 합성리뷰0/Figma0/생성영상0.
- [고정 실행 요약](../../../../evals/pm-r9/20261008/shared-prototype/serving-proof.json). 운영/PR/노션 공유 결과는 아래에 추가한다.
