# 2026-10-05 #12 자료 계약·기존 조회 실행 증거

검사 대상 코드: `791c206338dc2786bb880bdd53d80f9d1c010767`이다. 이후 전달 commit과 구분한다. 공통 코드·schema·잠금·기존 합성 자료와 이전 담당 변경은 보존했다.

## 실행 결과

- 직접 사용자 승인 후 프로젝트 `.tools`와 `.venv`에 uv 0.12.23·Python 3.11.17·잠금 jsonschema 4.26.0을 설치했다. 전역 Python·PATH·레지스트리는 변경하지 않았다.
- 기존 계약 검사 PASS: 30정의, 기존 5모델·36리뷰·3요청. 기존 회귀 170시험 PASS.
- 실제 세 Product 스키마 PASS, 참고팩 60항목의 출처 연결 오류 0건, 기존 36리뷰의 원문 근거 연결 PASS. 참고팩 전체를 DemoDataset으로 검증했다고 표시하지 않는다.
- 기존 API의 실제 loopback HTTP로 세 제품군 검색·원문 조회·동일 입력 재호출과 오류/빈 결과 5개를 확인했다. 모델·근거 ID·source ID·위치·버전·synthetic 표시 및 원문 일치를 확인했다. 시험용 서버는 종료했다.
- 전체 Git 이력을 확보한 뒤 phase2 validate는 valid=true/errors=[]로 통과했다. PM 원본 증거는 수정하지 않았다.

명령·입력·출력·성공과 실패는 각 JSON에 연결돼 있다. HTTP 검증 소스는 http-replay-source.txt, 실제 명령과 요청 및 응답 해시는 http-query.json에 있다. 전체 가상 응답은 Git 제외 tmp에만 보관한다.

## 실패 이력과 최신 확인

최초 sandbox PyPI 연결은 WinError10013으로 실패했고, 정식 network escalation에서 승인 범위의 설치에 성공했다. install-uv.json과 install-uv-network.json을 함께 보존한다.

초기 phase2 validate의 136오류는 얕은 clone의 누락 이력과 관련됐으며, phase2-validate.json을 삭제하지 않았다. 이력을 확보한 후의 결과는 phase2-validate-after-history.json이다. 이전 환경 누락으로 실행하지 못했던 결과도 이전 run에 남겼다.

최신 #12·#13·PM CHECKPOINT·main 지침·평가 안내는 승인된 브라우저로 읽었다. 커넥터의 404는 별도 접근 경로 실패로 남긴다. 조직 이전 주소 2026-LG-kitchen-chicken-team/lg-ax-2026으로 origin을 갱신했다. main cd3044f의 검사 대상 schema/API/기본 자료/잠금은 로컬과 같은 바이트다. 170시험을 최신 main 전체 시험으로 표시하지 않는다.

## 평가 준비와 제한

main CORE001의 기존 heldout 여섯 유형을 private/evaluation/DATA001-20261005-contract-review/에 재사용했다. PM manifest 형식·계약 기대 결정 6/6 일치, 개발 원문·ID의 정확한 겹침 0건을 확인했다. 비공개 원문과 답안은 PR에 포함하지 않으며 evaluation-materials.json에는 버전·수량·해시·제한만 남긴다.

이 자료는 후보 초안의 계약 검토용 합성 사례다. 독립성·정답 타당성·전체 상품기획 평가 적합성은 PM 확인 전 미확인이다. 실제 Agent/LLM 평가·모델 비교·점수 측정은 하지 않았다.

문서 등록·파싱 경로가 없어 R03 전체 연결은 미충족이다. 실제 LG 참고팩은 기존 합성 DemoStore에 등록하지 않았다. 실제 분석·판단 출력의 원문 추적과 전체 세 제품군 완주도 남았다. #13 구현은 사용자가 이번 범위에서 제외했다. 공식/SSG 출처 값은 10/4 수집 버전이며 이번 실행에서 재수집하지 않았다. 출처 차이 2건·미확인 7건을 보존한다.

## 사용 방법과 다음 작업

저장소 루트에서 승인된 기존 환경으로 실행한다.

```powershell
& '.venv/Scripts/python.exe' -B -X utf8 scripts/check_contracts.py
& '.venv/Scripts/python.exe' -B -X utf8 -m unittest discover -s tests -v
& '.venv/Scripts/python.exe' -B -X utf8 scripts/phase2.py validate
```

HTTP 조회는 `python -m lgax_api.server --host 127.0.0.1 --port <빈포트>`를 실행한 뒤 http-query.json의 요청을 사용한다. document_version은 `1.0`이다. 원문·응답 전체를 게시하지 않는다.

남은 조건은 remaining-conditions.json, 전달 파일과 해시는 상위 delivery-manifest.json에 있다. 다음 작업 하나는 게시 승인 후 부분 PR 전달이다. #12 전체 완료·PM 검수·병합·통합 완료를 주장하지 않는다.
