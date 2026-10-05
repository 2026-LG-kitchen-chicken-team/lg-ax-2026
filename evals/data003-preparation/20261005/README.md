# P2-DATA-003 단계3·4 준비 결과

2026-10-05 사용자 요청으로 #14의 개발용 질문·정답 근거와 비교 조건·측정 양식을 작성했다.
시작 commit b82cf9c2d063458bc3e54eb34b856c1050c93ced, 별도 codex/data003-preparation-20261005 브랜치다.

- [질문·정답 근거표](질문_정답근거표.md): 제품별5문항/총15문항, 답이 있는11개와 조건/자료 부족4개.
- [비교 조건·측정 기준](비교조건_측정기준.md): 검색3방법, 고정 모델/revision·동일 필터·측정법, OCR6사례.
- corpus.json/queries.json/protocol.json/ocr-cases.json: 재실행용 데이터.
- retrieval-results-template.json/csv와 ocr-results-template.json/csv: 모든 결과가 미측정 상태인 기록 양식.
- run-metadata-template.json: 실제 실행 환경·weight revision·입력 해시·실행 명령을 기록하는 빈 양식.
- manifest.json: 기존 자료·원문PDF/cache·준비 산출물의 버전/SHA256. validation.json: 준비 무결성 검사.

## 재생성과 검사

저장소 루트에서 기존 Python3.11을 사용한다. 새 설치/다운로드/모델 호출은 없다.

```powershell
python -B -X utf8 scripts/prepare_data003_benchmark.py --source-directory '기존-private/documents-source의-절대경로'
python -B -X utf8 scripts/verify_data003_preparation.py --source-directory '같은-원문폴더의-절대경로'
```

원문PDF·전체페이지캐시는 private에 보존한다. 이 작업은 기존 #12 자료나 독립 평가 답안을 변경하지 않는다.
HTML 사양/가격을 설명서 버전으로 바꾸거나 가짜 이전 문서·고객 리뷰를 생성하지 않았다.
이번 corpus는 manual 자료의 사실 요약이며 #12 공통 planning dataset을 대체하지 않는다.

## 이 준비의 진행 체크리스트

- [x] 3단계: 세 제품의 개발 질문15개·근거27개·원문 모델/버전/페이지 연결 작성
- [x] 4단계: 검색3방법·OCR6사례의 조건/지표·미측정 양식 작성
- [ ] PM의 질문/근거 의미 검수와 실제 공유·인수
- [ ] 5단계: 기존 실행 코드에 새 protocol 어댑터 연결, 환경/weight/crop 고정, 실제 측정
- [ ] 6단계: #13 실제 문서 처리 출력으로 통합 검사
- [ ] #14 PM 검수·병합·완료 판정

## 다음 단계와 현재 한계

준비만 실행했다. 검색/BGE/재정렬/OCR 측정·crop 생성·성능 개선·실제 고객 수요·#13 통합은 미실행이다.
다음은 기존 모델/환경·라이선스/weight revision·자원 상태 확인, 개발용 정답 검토, 새 protocol 실행 어댑터 연결·OCR crop 고정 후 별도 실행 폴더에서5단계 실험이다.
#14 정식 의존 DATA002와 PM 검수·병합·통합은 유지한다. 원격 게시/자기보고 수신·Notion 반영은 이번 준비에 포함하지 않는다.
