# R5 후속 실행 근거

- 최신 main `8ec1e8a51faabd6db032e52245680bef4229f93f`; 자료/모델 pin 원225 결과 `a26b6458118157fa0513218414f24abd6eae4b2a`; R5 실제 고정팩 `0d920df7d1afd09490e91cd40bf9c6cb9dfaf75d`.
- [#14 승인](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/14#issuecomment-6029600741), [재채점/명령·SHA](../../../../evals/data14-rescore/20261007-01a10600/README.md).
- [#15 경계](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/15#issuecomment-6029601114), [후보/역할/노출](../../../../evals/data15-candidate-preparation/20261007-01a10600/README.md).
- [#16 고정 인계와 PM billing 보고](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/16#issuecomment-6029600260), [JSON 집계/원문/첫 실패](../../../../data/research/r5-public-independent-20261007/trends-01a10600/README.md).

검사는 기존 networknone/zero-auth Docker image `sha256:1bdbf6c2dd816f852d816d12e219ee1326febfa11d3f0f52d5eb1f6cc598bde3`로 실행했다. 각 실행 JSON의 코드 SHA와 로그 SHA에 묶으며 다른 코드 버전의 검사를 현재 PASS로 바꾸지 않는다. 설치·새 모델/OCR/API 호출0, reviewer-only/credential mount0, 운영 변경0. 실제 CI 결과·게시 commit은 게시 수신증에 별도 연결한다.
