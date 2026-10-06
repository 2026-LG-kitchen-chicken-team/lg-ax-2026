<!-- member-log:entry v1; generated navigation, original content below -->
원본: `docs/작업근거/정이량.md` · source commit `84844b86d4d90faf341c0b19ef7407be274b9d17`

원문 byte 구간: 99880..103611 · 원문 행: 382..394

[개인 목차](../README.md) · [원바이트 전체 원본](../archive/84844b86-original.md)

<!-- member-log:body:start -->
## 정이량-E015-PROJECTMOVE — 조직 Project 이관·공백 검수 근거

- 최종 공식 승인 증거: `evals/project-migration/20261005/final-verification.json`, main4ba1fa16cac09ace97d5654f770345e1fe6b945a·ACCEPTED5982274252·서비스fresh health published/trusted 일치/미승인0·Done5·3Sent. 실제 자기보고 ACK5982254301은 새Project1 URL을 반환했다. 이 승인/보고는 모델 의미 품질 입증과 다르다.
- 공백 대조: `gap-reconciliation.json`, 실제2026-10-05 02:11 KST에 승인된 로컬 비공개 접속을 이용해 서버의 durable state를 읽고 GitHub 등록 command 전체를 대조했다. before seen30행의 comment_id/body_sha256/outcome/task_id/status/commit 변경0/누락0; 현재34행32accepted/2rejected·미처리0·ACK누락0·최근보고/보드불일치0. 이전 권한 위반 거절2행도 유지한다. 새 팀원 보고 ACK는 #8의5982325640 및 #25의5982391462다. 미전송/미push 개인작업까지 없다는 주장이나 코드 품질/실행 진실성 검증을 지지하지 않는다.
- Notion 재조회: `notion-verification.json`은 LG 페이지와 전체 대시보드 중 LG 대상 내용 반영·비대상 동일성을 기록한다. 처음 raw문자열 비교 실패는 시한부 S3 첨부 URL의 재발급 서명 쿼리 차이였고, 서명 쿼리·공백만 정규화한 뒤 원 첨부 경로/나머지 내용 동일을 확인했다. 잘못 자동 링크화된 지침 파일 문구는 코드 표기로 수정·재조회했다. 첨부 원문/서명 URL/페이지 전체 개인정보를 공개 증거에 복사하지 않는다.
- 독립 대조: `independent-review.json` SHA256 a3cd5cddc2b41415bec95fe9d9d7105f702376c6d9df7f831a7e231b0488cd3a·16PASS. 26Issue·25field/option·238editable values·26date·같은ID/순서/담당·parent/subissue0·PR30과17/18의2관계·보기10열 일치. 3메일 필드의prepared→sent 이후 변경은 의도된 운영 변화다. `ui-checks.json`의Read/PMAdmin/기본Read·기본repo 및6workflow조건/Status는 rootCUA 실제조회이며 독립 다른계정 로그인을 가장하지 않는다.
- 공개 기록에는 민감 패턴 검사0. 보드 원본의GitHub 이벤트/Insights는 재생성하지 않고 닫힌원본에 보존한다. CUA 결과 스크린샷은 `private/project-migration/20261005/repository-projects.jpg`다. 공식CLI의JSON 정규화로 github.json에같은내용의줄바꿈변경만생겨 diff0을확인했다.

- 연결 기록: 정이량-20261005-002-PROJECTMOVE / 직접 사용자 지시 / 확인일 2026-10-05 KST.
- 원본: 개인 Project3 `PVT_kwHODCN5Rc4BlmPN`, https://github.com/users/jeongiryang/projects/3. 기존 조회 26항목·25필드·1보기·6활성 workflow. 전체 날짜·옵션·관계의 원본은 `evals/project-migration/20261005/before-raw.json`을 작성해 대조한다. CLI item-list의 일부 한글 표시 키가 깨져 필드 복사 원본으로 사용하지 않는다.
- 방법 근거: 공식 계정 이동 안내 https://docs.github.com/en/account-and-profile/how-tos/account-management/moving-your-work-to-an-organization 와 실제 `/move_work/new`의 V2 프로젝트 미표시·원본 설정의 복사 제공을 구분한다. GraphQL 실제 스키마에는 `copyProjectV2`, `linkProjectV2ToRepository`, 보기/필드 갱신이 있으며 직접 transfer mutation은 발견되지 않았다. 보드 재구성 후 기존 이슈의 ID를 재사용하므로 PR·담당자·상하 관계 원본은 이동하지 않는다.
- 현재 주장 한계: 이관 완료·권한 확인·새 서비스 운영은 후속 실제 증거 전까지 미완료다. 계정·비공개 서비스 인증값과 연락처는 출력·Git·Issue·Notion에 기록하지 않는다.


<!-- member-log:body:end -->
