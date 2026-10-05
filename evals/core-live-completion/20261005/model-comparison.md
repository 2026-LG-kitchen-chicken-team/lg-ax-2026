# 수동 모델·추론 구성 비교

범위는 자동화 이전 CORE002~005의 미완료 부분이다. 사용자가 추론 모드와 더 나은 모델 비교를 직접 승인했다. 기존 합의 모델 원 실행은 summary.json에 보존하며 새 구성의 실행을 기존 설정으로 실행했다고 주장하지 않는다. 아래 개발 진단은 소스/API가 바뀌는 과정의 관찰이므로 최종 모델 순위나 독립 평가가 아니다.

| 후보 | 실제 manifest digest | 양자화·파일 크기 | 상태 |
|---|---|---|---|
| qwen3:8b | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | Q4_K_M, 5,225,388,164bytes | 기존 PM 모델/서비스 그대로 사용 |
| qwen3:32b | 030ee887880fc378860c2dd35101da424377520441ae4bfe7be6deff8ade7840 | Q4_K_M, 20,201,253,829bytes | 동일 계열의 큰 모델 후보, 본인 캐시 추가 |
| qwen3.5:27b | 64ae5b1d651fb2709d5928ccb8dcfb4bb2cc9c2c8001ac34497e36a6cf905b59 | Q4_K_M, 17,478,556,591bytes | 새 계열 후보, 본인 캐시 추가 |

출처·라이선스는 [Qwen3-8B 카드](https://huggingface.co/Qwen/Qwen3-8B), [Qwen3-32B 카드](https://huggingface.co/Qwen/Qwen3-32B), [Qwen3.5-27B 카드](https://huggingface.co/Qwen/Qwen3.5-27B) 및 [Ollama32B](https://ollama.com/library/qwen3:32b)/[Ollama27B](https://ollama.com/library/qwen3.5:27b)다. Apache2.0 모델이며 실제 받은 manifest pin과 모델 설정을 대조한다. 이름·크기만으로 우리 상품기획 품질이 높아졌다고 판단하지 않는다.

## 실행과 기존 파일 보존

본인 SSH 계정으로 nvidia-smi·compute 프로세스·root/tmpfs·RAM을 확인했다. 별도 모델은 비어 있는 GPU2 한 장, CUDA_VISIBLE_DEVICES=2·CUDA_DEVICE_ORDER=PCI_BUS_ID, loopback18866·cloud off·parallel1·max_loaded1·본인 tmpfs 캐시에서 사용한다. 본인 임시 서비스는 최대2시간 watchdog과 종료 요청을 갖는다. GPU1의 다른 작업과 PM의 기존18864/모델 캐시를 변경하지 않는다. 새 다운로드를 위해 기존 파일을 삭제/이동/덮어쓰지 않았다. tmpfs는 재부팅 시 사라지므로 영구 운영 완료를 주장하지 않는다.

시스템 Ollama는0.24.0이었다. 초기32B HTTP500와27B registry412(새 runtime 요구) 실패를 보존했다. 공식 [v0.34.0 배포](https://github.com/ollama/ollama/releases/tag/v0.34.0)의 Linux asset SHA256을 검증한 뒤 본인 tmpfs에만 추가 설치하여 PM runtime0.34.0과 맞췄다. 전역 Ollama/driver/기존 서비스는 바꾸지 않았다. 본인 초기 임시 서비스는 UID·cwd·환경·포트를 확인한 후 종료했고 새 모델 캐시는 재사용/보존했다. 본인 새 서비스도 작업 종료 시 중지/포트 해제를 확인해야 한다.

## 개발 진단과 연결 방식

- thinking-8b-01: 기존temperature0에서 think=true 요청, compare 출력8192 한도 도달로 실패했다. 실제 응답의 별도 thinking 필드는 없었다. 요청한 설정이 실제 추론 출력 분리의 증명은 아니다.
- thinking-8b-02: temperature0.6/top_p0.95/top_k20/min_p0/seed42에서 JSON 반환 완료했지만 사용 조건 자체의 고객 불편을 'resolved'로 오판하고 빈 후보 완료 처리했다. 이 실제 원 출력은 후보 없음 결론 검사 회귀의 입력으로 보존했다. 정상 기획 품질 성공으로 계산하지 않는다.
- thinking-32b-01/02: 초기 runtime0.24의 실패와0.34 동일 버전 재시도. 후자는 support_basis/status 불일치·보류 질문 누락 뒤 최대2회 수정, 출력 한도 실패다. 큰 모델이라는 이유로 통과시키지 않았다.
- thinking-8b-03: 빈 후보 의미 검사 추가 후 별도 진단. 이 실행은 빈 후보 결론을 통과시키지 않고 정상 후보 경로로 진행했지만 제외 조건 의미 검토에서 held였다. 모델 샘플링은 반복마다 동일 결과를 보장하지 않는다.
- thinking-27b-01: generate/think=true에서 별도 thinking만 반환하고 최종 response가 비어3회 JSON 실패했다. thinking 원문을 답으로 변환하지 않았다.
- nonthinking-27b-02: generate/think=false, temperature0.7/top_p0.8. 판단 결과 held이며 기획 품질 완료가 아니다.
- chat-thinking-8b-04: 실제/api/chat의3응답에서 thinking4208/2848/1944자와 최종 content701/723/839자가 분리됨을 확인했다. 앞 단계 잘못된 근거 인용/판단으로 held. 분리 동작과 의미 품질을 구분한다.
- chat-nonthinking-8b-05: chat/think=false의 별도 정상 입력 진단. 실제4호출/held.
- chat-thinking-27b-03: chat/think=true, temperature1/top_p0.95/top_k20/min_p0, 모델 기본presence_penalty1.5. 실행 중이며 원 결과 생성 전에는 성공·실패를 추정하지 않는다.

출력8192·문맥16384·seed42·호출 제한300초·응답131072bytes이며 실제 조건은 각 manual_execution/transport_request에서 확인한다. native format과 로컬 JSON/schema·호출 전후 model pin 검사는 모든 구성에서 유지한다. API 모드의 선택은 명시적이며 실패 시 자동 모델/경로 fallback은 없다. 별도 thinking 또는 message.thinking은 최종 JSON으로 대체하지 않는다. [Ollama thinking 문서](https://docs.ollama.com/capabilities/thinking)와 [0.34 generate/chat 차이 보고](https://github.com/ollama/ollama/issues/18554)를 참고하되 이슈 보고만으로 우리 환경의 원인을 확정하지 않는다.

## 코드 검증과 미완료

불변 sampling/API 설정·실제 요청/metadata/Session hash 일치, 고정 Lab API의 변경 설정 거절, chat의 최종 응답/추론 분리·빈 응답 거절, 후보 없음 결론의 원문·3기준·모델 입력/출력 해시 검사와 해당 단계 최대2회 수정을 보완했다. Python504개(76.292초), Ruff, diff check가 통과했다. 초기 새 빈 후보 검사가 기존 모의 transport에서 누락된2건은 새 검사 응답/기대 호출 수를 보완한 뒤 통과했다. 검사를 삭제하거나 실제 원 응답을 고치지 않았다.

같은 안정된 코드/자료/API/각 구성에서 여섯 유형 Agent·단일 프롬프트 기준선의 실제 비교, 독립 가린 검토, 세 제품 변경 전후 의미 품질, 일반 PR/PM 수신·검수·병합·통합 확인이 남아 있다. 테스트 수·JSON 반환·작성자 관찰만으로 CORE002~005 Done을 주장하지 않는다.
