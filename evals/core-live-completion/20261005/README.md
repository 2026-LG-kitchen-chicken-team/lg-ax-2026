# 자동화 이전 CORE002~005 실제 검증 / 2026-10-05

사용자가 요청한 기존 미완료 범위를 본인 연구실 계정으로 검증했다. PM과 동일한 qwen3:8b/Q4_K_M, Ollama0.34.0, digest500a1f…8b41, temperature0/seed42/thinking=false/문맥16384/출력8192를 사용했다. Worker·신규 배정·PM 상태는 바꾸지 않았다. 자료는 합성 자료다.

첫 검증 종료 시 Python491 검사, lint, 계약/지침/phase2 무결성은 통과했지만 **정상 기획 품질·독립 의미 평가·부모 작업 완료는 미완료**였다. 당시 설정 선택을 질문하고 전체 작업을 멈췄다. 아래 summary.json과 초기 원 실행은 당시 조건/상태를 그대로 보존한다.

이후 사용자가 추론 모드·더 나은 모델 비교를 명시적으로 승인해 재개했다. 새 결과와 실행 환경은 [모델 비교 기록](model-comparison.md)에 추가하며 기존 원 결과를 덮어쓰지 않는다. 신규 배정/Worker 운영을 다루지 않는다. 현재 Python504개와 lint를 통과했으며 실제 의미 품질은 별도 검증 중이다. 기존 모델 파일/PM 서비스는 보존하고 새 모델은 본인의 별도 캐시에 추가했다.

- diagnostic01/02/03/04: 실제 개발 정상 사례. 각각 held/held/failed/held. 모든 원 응답·입력·실제 전달 prompt/schema·모델/코드 해시와 실패를 보존한다. diagnostic03은 최대2회 수정에서 종료됐다.
- independent-comparison-01: 개발 사례와 분리한 SEM01~06의 Agent·동일 모델 강한 단일 프롬프트 실제 실행. Agent는5건 held, 의도적인 모델/버전 혼동1건은 생성0회로 차단됐다. 기준선6건은 JSON을 반환했지만 원문/지원/중복/보류 의미를 틀린 관찰이 있어 품질 성공으로 채점하지 않는다.
- three-product-reexecution-01: 세 제품 변경 계획과 변경 후 실제 실행. 최초 before 입력은 이전 수정 회차2여서 새 실행 조건에 맞지 않아 생성0회로 차단됐다. 이 초기 실패를 지우지 않는다.
- three-product-before-repeat-02: 호출자가 prepare_reexecution(previous, previous, explicit_new_run=True)로 새 before 실행을 명시하고0회차부터 실행했다. 같은 코드/모델/설정의 원 after 결과를 해시로 연결한다. 세 제품6개 실제 결과 모두 held다. 변화가 감지됐다는 사실을 해결 후보 완성으로 바꾸지 않는다.
- sem06-before-01: SEM06의 이전1.0 자료만 전달한 별도 양쪽 실행. 현재2.0 비교 호출/토큰 합계에 섞지 않는다.
- verification/python-tests.txt: 최종491개 회귀검사 원 로그. 테스트용 transport 응답을 실제 모델 응답으로 사용하지 않았다.
- summary.json: 결과·측정·검증·한계·미완료 상태. 인용·수정 맥락 전달·기준선 길이 문제를 보완했지만 모델의 과도한 보류/지원 판단 오류가 남아 있다.

현재6건의 비교 토큰은 Agent 입력43133/출력20263, 기준선 입력23029/출력9187다. Agent19회/기준선6회 생성 요청을 합산했다. 실패/재시도도 포함하며 의미 품질이 확보되지 않아 효율 우위를 주장하지 않는다. 시간·토큰은 이번 단일 합성 batch 관찰이며 GPU 간 성능 benchmark가 아니다.

독립 가린 검토 준비 도구는6개 실제 결과 bundle을 인수했다. preparation_status=live_results_awaiting_independent_review, evaluation_complete=false다. 작성자는 결과 생성과 방식 정보를 알고 있으므로 독립 검토자가 아니다. 방식명이 포함된 원본은 검토자에게 직접 전달하지 않으며 PM 검수 경로에서 가림·공유 범위를 조율해야 한다. 실제 PM 수신/검수/병합/Done은 아직 없다.

재현은 evals/core-semantic/README.md의 frozen 입력/비교 runner와 lgax_core.planning_agent / prepare_reexecution을 따른다. 같은 코드의 source SHA256와 실행별 원 입력/자료 hash를 각 원본에서 대조한다. 결과를 덮어쓰지 않고 새 출력 경로만 사용한다.
