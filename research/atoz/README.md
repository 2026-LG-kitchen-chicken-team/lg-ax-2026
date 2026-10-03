# AtoZ 재정렬 실험

2026-09-27 사용자 정정: 설계가 쉬우면서 심사 경쟁력이 높은 아이디어, 아이디어 발굴부터 Agent 설계·구현·평가·제출까지 실행하는 하네스가 목적이다. 기존 Kitchen Gap 확정을 되돌리고 동일 기준으로 재탐색한다. 오늘 접수 목표는 유지한다.

## 실행 주체와 참조

현재 Codex 대화가 자료 조사·아이디어 생성·설계·도구 호출을 수행한다. `scripts/ax_workflow.py`는 단계별 작업 패킷, 의존성, 산출물 계약, 증빙 버전, 재개 위치를 관리한다. 별도 모델 키 없이 이 채팅에서 사용할 수 있다. 이 도구가 백그라운드에서 스스로 LLM을 호출하는 것은 아니다. 참가작 Agent의 API 연결은 별도의 구현 과제다.

참고한 사용자 저장소의 실제 파일:

- https://github.com/jeongiryang/harness-100/blob/main/ko/44-market-research/.claude/CLAUDE.md
- https://github.com/jeongiryang/harness-100/blob/main/ko/46-product-manager/.claude/CLAUDE.md
- https://github.com/jeongiryang/harness-100/blob/main/ko/41-llm-app-builder/.claude/CLAUDE.md
- https://github.com/jeongiryang/harness-100/blob/main/ko/24-test-automation/.claude/CLAUDE.md

산업/경쟁/사용자 조사, PRD/작업 분해, 모델/평가 설계, 통합 검증의 산출물 연결을 참고했다. 외부 템플릿의 팀 생성 지시를 실행하지 않았으며 한 Codex가 역할을 순서대로 수행한다.

## 판단 기준

공식 주제 PDF 30쪽의 문제·인사이트·Agent 과정·구현·재사용을 기준으로, 모델 자유도, 외부 의존성, 정답/평가 정의, 화면 범위, 시연 전달력을 함께 비교한다. 공식 배점과 경쟁팀 수준을 모르므로 수상 확률은 산출하지 않는다. 쉬운 제작과 차별성을 동시에 만족하는 후보를 우선한다.

자료 접근이 쉽다는 것만으로 가전을 고정하지 않는다. 시장에 같은 기능이 없다고 증명한 것은 아니므로 세계 최초·사내 미보유를 주장하지 않는다. 서류 1차 경쟁력과 최종 구현·시연 경쟁력을 구분한다.

## 새로 확인한 근거

- S17: LG WSED7613*/WS7D7610*, MFL71927512 Rev.07_110525 설명서 22~23쪽. 원격 시작에는 기기측 준비가 필요하며 Wi-Fi 문제로 지연될 수 있다. 이 제품군 조건이며 LG 전 제품에 일반화하지 않는다. https://gscs-b2c.lge.com/open/downloadFile?fileId=tYJHqI7Nk3lkQwrvv6IRQ
- S18: LG의 냉장고 ThinQ 연결 안내. 연결·등록이 필요한 상황의 근거이고 통신 실패 빈도는 입증하지 않는다. https://www.lg.com/us/support/help-library/enabling-wifi-and-the-lg-thinq-app-for-a-compatible-lg-refrigerator--20152715544610
- S19: Figma Make는 흐름·상태·화면 생성을 이미 제공한다. 일반 UI 생성만으로는 차별성이 약하다. https://www.figma.com/solutions/ux-flow-generator/
- 기존 S3 ThinQ Claw의 상황 기반 기기 연결, S11 Design for All, S13 Dovetail, S14 Figma Make도 재사용한다. 고객 수요·현업 작업 시간은 아직 미측정이다.

## 실험의 범위

`flow_trials.json`은 Codex가 작성한 개발용 UX 그래프와 실패 입력이다. 결함을 주입한 그래프와 수정본은 모델 정확도 비교 실험이 아니다. `flow_audit.py`로 연결·실패 분기·결과 상태를 실제 검사한다. 기존 A4/B1의 규칙 실행 결과는 비교 자료로 재사용하고 새 모델 실행으로 계산하지 않는다.

공개 문서에서 원격 동작의 제약이 있다는 사실을 확인한 것과, 모든 가전의 실제 실패 복구 동작을 구현한 것은 다르다. 테스트는 설계 산출물의 구조를 검사하며 물리·조리 안전 검증이나 사용자 행동 시뮬레이션을 주장하지 않는다.
