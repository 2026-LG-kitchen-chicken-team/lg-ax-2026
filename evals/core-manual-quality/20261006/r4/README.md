# R4 실제 고정8B 세 사례와 보류 피드백

PM R3 필수 정상·조건변경·설명서 누락 3입력을 병합 main `8f9d83fc7641ceaea7631c166137379645574ea8`에서 실행했다. 원 R2 입력/자료 SHA와 고정 Qwen3:8b digest·temperature0/seed42/ctx16384/predict8192/thinking=false를 유지했다. 합성 개발 자료이며 실제 고객 자료/전체 평가가 아니다.

세 사례 모두 needs 단계3호출·공유 수정2회 뒤 `HOLD_WITHOUT_QUESTIONS`로 failed다. 후보 accept0, 적절한 자료 부족 보류도 미검증이다. 모델은 확인된 Need ID 또는 `questions`/`hold_reasons` 같은 필드 이름을 unresolved에 적고 질문을 비웠다. 코드의 자료 부족 거부를 완화하거나 이를 성공으로 바꾸지 않았다. 작성자의 원문 관찰은 독립 AI 평가가 아니다.

[실행 manifest](execution-manifest.json), [실제 gateway usage](gateway-usage.json), 원 입력/전송 prompt/원 응답/trace가 있는 [정상](results/fridge-normal.json)·[조건변경](results/fridge-changed.json)·[설명서 누락](results/fridge-missing-manual.json)을 확인할 수 있다. 총9회, 입력20,685·출력19,041·합계39,726토큰이다. 모든 생성 응답을 수신했고 원 비용은 초기화하지 않았다.

검증용 파일 중계의 초기 byte-stream 오류는 실제 생성0으로 실패한 원 출력/SHA를 비공개 보존했다. 두 유효 실행 후 세 번째 POST를 forwarding하기 전에 TLS metadata 조회가 중단됐다. 이미 수신한6회/두 결과를 보존하고 원 미전송 세 번째만 이어가 누적9/24로 종료했다. Docker source read-only/network none/UID65534에서 실제 Agent를 실행하고 인증은 호스트의 고정 중계에만 있었다. 새 모델 설치/타 서비스 변경/Worker ON은0이다. 호스트 private 경로·인증 설정은 공개하지 않는다.

이번 후속 코드 보완은 기존 HOLD_WITHOUT_QUESTIONS 수정 피드백에 실제 unresolved/hold_reasons/questions 값과 누락 사실 확인 안내를 전달한다. 원 결과·거부 판정·공유 수정2회·정당한 보류는 유지한다. 기존 원 응답 재생은 새 모델 생성이 아니며 이 보완의 실모델 성공은 아직 검증하지 않았다. 검사 수신은 [checks/manifest.json](checks/manifest.json)에 연결한다.

PM은 공통 native-schema/필드 의미 안내와 고정 모델 후속 배치를 이 원문으로 대조해야 한다. CORE는 작은 feedback diff 검수 뒤 새로 고정된 유한 배정으로 재검증한다. WEB의 동일 accept 흐름·MCP 실제 제품 run·독립 의미 평가·최종 PM 인수와 부모 Done은 남아 있다. 원 여섯 사례 AI 채점을 반복하지 않는다.
