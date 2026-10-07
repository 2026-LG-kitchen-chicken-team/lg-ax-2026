# D3 고정 소스의 격리 검사

검사 소스 commit: 04f2712e58fcb818229b10677fb50ec6d916c15f.
이 디렉터리는 검사 결과만 추가하며 검사한 경쟁자료·비교 코드·manifest를 바꾸지 않는다.

- package-verification.json: 새 경쟁자료 디렉터리의 manifest8개 멤버 바이트·SHA·LF 대조.
- comparison-verification.json: 원 development 후기848850·두 모델 사양·공식 발췌12개·미확인/연결 대기 상태 대조.
- container-checks.json: 실제 격리 설정·지침 동기화·문서 탐색 검사 범위.

새 비교자료는 [D3 연구 단위](../../../data/research/r8-public-research-20261007/competitors/01a114f6/README.md)에 있다.
현재 first_problem 확정·P0 소비·고객/물리 효과·Issue235 전체 완료를 입증하지 않는다.
