# 공유 프로토타입 실행 근거

배포 source `0541ba02457055d28e3f7021fbaf907a2ca86bfb`와 실제 공개 브라우저 생성 1건의 근거다. [요약](serving-proof.json)·[웹 검사](web-validation.json)·[백엔드 검사](backend-validation.json)·[규칙/문서 검사](gates-validation.json)를 따르며 main 병합/의미 품질 승인은 아니다.

백엔드 receipt의 최종 returncode1은 61시험 PASS 뒤 archive에 Git history가 없어 phase2 검사가 멈춘 값이다. history bundle을 넣은 gates receipt에서 전체 규칙/계약/phase2/문서 탐색을 PASS했다. 웹 wrapper의 마지막 CP949 로그 출력 오류와 최초 mock 이미 소비된 response 오류는 원 실행 디렉토리에 보존한다. 테스트 입력은 인증/원문 연결을 검증하는 mock이며 새 합성 리뷰를 서비스에 넣지 않았다.

서명 키/세션 cookie/Bearer/SSH 정보는 저장하지 않는다. 요청당 모델 응답 제한과 서비스 종료 시한을 구분한다. 자동 Worker는 OFF다.
