# R9 통합 CORE 소비 검수

2026-10-08 KST, 황대겸/unknownamed. PM [PR262](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/pull/262)의 `a6da6784db60e99645fd57017d37ba1403af9cd1`을 고정하여 이전 native 후보·공개 집계·공식 안내서 인계 의존을 다시 확인했다. PM의 진행 중인 제품 파일은 수정하지 않았다.

- [원문/출력 발췌 대조와 pin](context.json): 실제 R9 후기/공식 원문 6개, 공개된 PM 의미검토의 출력 발췌를 받은 범위에서 대조했다. 배우자의 불편, 총 사용 기간·냄새 시점, 혼합 의견·설치 의도 추론을 원문과 구분한다. 이는 새 여섯 사례 독립 AI 채점이 아니다.
- [격리 결과](verification.json): 기존 native 경계9·수리 집계8·선택 입력5·공식 안내서12, 총34검사를 확인했다. 첫 staging 누락과 원 실패를 보존하고 정확한 기존 입력을 추가한 뒤 통과23을 재사용하며 남은 setup 오류11만 검사했다. 신규검사/모델0, 검수 완화0.
- PM 통합의 native opt-in·공개 집계 검증·수리 시 원 처리범위 보존·공식 안내서 API/MCP 경로를 fixture 수준에서 확인했다. 기존 CORE C3 설치/용량/비교 지침이 통합에 유지된 것도 확인했다. PM의 일반 출처 지침/anti-echo 수정은 코드에 있지만 최신 선택 실행은 출력 잘림으로 효과 미검증이다.
- [최초 환경 실패 포함 로그](consumer-initial.log) · [남은11검사](consumer-recovery.log).

실제 model raw/usage·전체 stored brief와 같은 HTTP/MCP 원 수신은 직접 받지 않았다. 구매 SKU/구매시점 문서 적용은 미확인이다. 출력 발췌에 남은 증상·주체·시간순서·혼합 의견 오류와 최신 출력 잘림은 성공으로 바꾸지 않는다. 유한 세션을 반복하거나 출력/수리 예산을 늘리지 않았다. PM 승인/병합/통합 인수·부모 Done을 대신하지 않는다. 먼저 받은 각 자료는 그 입력만으로 가능한 검토부터 이어간다.

추가 실제 입력 인수: R9 전자레인지 공식 설명서 참고5종을 기존 생성기로 HTML/Markdown/JSON 출력했다. [원 수신/버전·SHA](official-reference/official-reference-intake.json) · [HTML/Markdown/JSON 원 출력 ZIP](official-reference/r9-microwave-reference.zip) · [원 바이트/SHA](official-reference/archive-manifest.json). 순서·원문·facts·metadata 정확 보존, 구매 SKU 미확인/공식 참고 범위 유지, 모델0이다. PM PR262는 2026-10-08T00:06:40Z에 병합됐고 기존 CORE PR251도 병합 확인했다. 최신 main `dc0ccc05916c637b2e0c2cc268a061dfa655c0b7`의 제품/data/test tree는 검수 head a6da6784와 동일하다. 실제 모델 품질·부모 완료/최종 인수는 별도로 남긴다.
