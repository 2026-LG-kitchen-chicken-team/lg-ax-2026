# 정이량-20261008-012-SHARED-PROTOTYPE

KST 2026-10-08. 사용자 직접 요청: 종료 지시 전 링크 사용자용 웹/API·LLM을 유지하고 프로토타입 링크를 제공한다.

확인: gh 인증 jeongiryang. 본인 사서함 LG 관련 10/7 이후 조회에서 DATA 후속 PR281/278/276 전달을 확인했다. 이번 범위는 후속 PR 인수/의미 승인이 아니라 팀원용 프로토타입 서빙이다. 기존 디자인443133ca와 main eab85d4를 이어 사용하며 중복 개발/새 합성 리뷰/Figma/개발 자동화 ON은 없다.

실제 조사: 기존 R9 테스트 session은 로컬1700·원격1800초와 finally stop이 있다. 제품 요청도 keep_alive=5m이다. 연구실 GPU3 여유/보호 GPU1 프로세스/독립 포트를 확인했다. 기존 Tailscale 상태를 읽고 별도8443 추가를 시도했으나 사용자 권한·sudo 권한이 없어 실패했다. 기존 경로/ACL/서비스는 변경하지 않았다. 별도 소유 경로에 공식 cloudflared binary의 release digest를 대조해 저장했다.

구현: 공유 전용 gateway, 브라우저별 signed editor session, 실제 자료 전용 웹 자동 연결, 생성1개 제한, 원문/조건/이력 계약 보존, 상시 GPU3 모델 서비스. [상세 운영 범위](../../../pm/prototype-sharing-20261008.md).

자기 검수/배포/실모델/외부 브라우저 결과는 E059에 종료 보완한다. 구현만으로 접속 성공·LLM 의미 정확도·필수 CI/main 병합·정식 Done을 선언하지 않는다.
