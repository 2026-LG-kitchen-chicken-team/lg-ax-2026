# 신진하 작업기록 — manual-data001-remaining-20261005T1143Z

- 실제 사용자 원문: “Git 오류128 진단·복구…저장 자료 보호 검증…세 제품 AI 재실행…독립 평가…깃오류 잡았을거야1~5해봐”. 추가 원문: “#13한테 #12가 끝내는걸 우선으로하라고해”.
- 해석: 기존 복구 증거를 재사용·직접 확인하고 좁은 snapshot 보호 수정과 실제 제품 재실행/평가 준비를 진행한다. #13에1회조율 메시지를 사용자 승인으로 전달했고 자기 예약이 해제된 뒤 별도 예약을 확보했다. 새 설치/원자동job재시도/CORE전체수정/PM권한/Done/비공개답안게시로 확대하지 않는다.
- 시각: 2026-10-05T21:44:08+09:00. 현재main 기반df0310ea31bbadda68b299dc96a85475cf7ecec9; 수정전/후 Source/test SHA와 입력/출력/실패는아래 공개요약 및원private run에연결한다.

# #12 Git 복구 확인·자료 snapshot 수정·실제 재실행

2026-10-05T21:44:08+09:00, 신진하/Codex. 실제 실행 기준은 df0310ea31bbadda68b299dc96a85475cf7ecec9와 version-provenance.json의 두 수정 파일 SHA다. 아직 새 게시 head가 아니다.

- Git128: 기존 복구의 실제 Limited fetch/checkout0·최장219자 파일 읽기 성공을 확인했다. 다른 채팅의 주장만 옮기지 않고 원 수신증 SHA를 연결했다. 원 자동 blocked3개와 예산/기록을 재시도하거나 지우지 않았다.
- 자료 snapshot: 검증/인덱스가 생성자 원 dict를 참조하던 결함을 먼저 실패로 재현하고 같은 deep copy에서 구성하도록1줄 수정했다. 같은 최종7검사는 수정 전실패/수정 후PASS, 기존등록10/연결5 및계약PASS다. 공개자료/합성자료는 분리했고 원 PDF·plan·dataset·Schema는 바꾸지 않았다.
- 실제 LG3모델: 기존 WorkspaceDocumentStore→build_planning_input→EnvPlanningRunner→PlanningAgent 경로로 실행했다. 15근거의 모델·자료ID·페이지/절·개정판·public 구분은 일치했다. 리뷰0이라 생성 전에3개 모두HELD이며 실제 LG 모델 답변의 품질 성공을 주장하지 않는다.
- 별도 기존 합성3모델: 동일 고정Qwen/digest·temperature0·seed42·context16384·output4096·thinkingfalse. 실제응답12개/원prompt·response·revision 대조PASS, 측정52627토큰. 냉장고5·식기세척기4·전자레인지3호출이고 세 결과 모두FAILED다. 불편 아닌 리뷰의 불편화·기능/리뷰근거 누락·희망 결과 누락이 남았다. 원시 합성리뷰/응답은 private supervisor 로그에만 보존한다.
- 평가: 기존 분리6유형/Agent·기준선 결과는code5af64e93의 과거 결과로 구분했다. 현재 평가 준비 도구를networknone/noauth의 별도 평가용 복사본에서 실행했으나 입력 미잘림 미확인으로exit2거절. 정답/독립성의 사람 검토·채점 미완료, reviewer-only 원문을 개발/모델에 제공하지 않았다. 구독/API로 전환하거나 새 tokenizer 패키지를 설치하지 않았다.

| 이번 요청 | 상태 | 근거/남음 |
|---|---|---|
| 1 Git 오류 복구 확인 | 완료 | 실제 원 제한 권한 수신증과 현재 Docker 정상 |
| 2 저장 자료 보호 | 개별 검증 완료 | 같은 테스트의 실패→22검사/계약PASS; PM 인수/통합은 별도 |
| 3 세 제품 AI 재실행 | 실행 완료·전체 성공 미완료 | 실제3제품리뷰0보류, 별도합성3제품실제12응답/판단실패 |
| 4 독립 평가·필요 수정 | 미완료 | 데이터 snapshot 수정만 완료; CORE 판단 오류는 해당 담당/PM 조율, 평가 준비exit2·독립채점 없음 |
| 5 새 증거 전달 | 로컬 준비 | 새 구현 PR 게시 전 사용자의 상시 확인 지시를 따른다 |

사용 방법: before-final/after-final-checks를 대조하고 각 public-replay/dev 요약의 실제 데이터 성격·model/digest·근거조회·상태를 확인한다. evaluation-gate-corrected-result에는 실제 실패 명령/출력이 있다. 코드/데이터에 결과를 하드코딩하지 않았으며 JSON/연결 통과를 판단 품질로 바꾸지 않았다.

다음: PM은 data-document-store-frozen-snapshot을 독립 인수하고 실제 등록/검색 경로에 통합한다. CORE 담당은 NON_COMPLAINT_AS_NEED·GAP_MANUAL_MISSING·GAP_REVIEW_MISSING·희망결과 누락을 실제 실패에 따라 수정한다. 독립 평가의 전체입력/정답검토 후 필요한 실패만 다시 실행한다. 새 게시 승인 뒤 exact head의PR/Issue/ACCEPTED, PM최종검수·병합·통합 후#12완료를 판정한다.

- 범위/한계: 최초 wrapper API속성 및 fixture 버전/스키마 오류, 문서 어댑터 선택 오류·평가CLI필수인수누락을 각 원 실패로 보존하고 소스/결과 버전을 구분한다. 새실행의 raw prompt/response·독립 자료/답안은 PR에 넣지 않는다. 현재ChatGPT가 수동 source diff를 작성했고 별도 coding CLI의 모델 생성으로 가장하지 않았다. 제품Qwen12응답과 coding/규칙검사를 구분한다.

- 게시 승인: 사용자가 새 수정본23파일/b504bc6의 main 대상 PR·#12 게시 질문에 “새 수정본 PR·#12 게시 승인 (추천)”으로 직접 답했다. 승인 범위는 저장 자료 보호 수정/검사/실제 실행 실패의 부분 전달이며 #12 Done·PM 병합·독립 채점 승인으로 바꾸지 않는다. 코드/테스트/모델 입력/원 결과 바이트는 승인 전 검증한 것과 동일하다.
