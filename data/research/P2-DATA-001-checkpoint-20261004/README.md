# DATA-001-CHECKPOINT 부분 전달 준비

최신 [PM CHECKPOINT](https://github.com/jeongiryang/lg-ax-2026/issues/12#issuecomment-5979831712)를 읽고 준비했다. **게시 전 사용자 검토용 로컬 묶음이며 #12 전체 완료 제출이 아니다.**

## 부분 PR로 전달할 수 있는 것

1. 승인한 실제 세 모델의 참고팩: [JSON/CSV/요약/최소 확인](../P2-DATA-001-real-reference-20261004/README.md). 공식9건·SSG3건, 사실60개, 충돌2건·미확인7건.
2. [traceability-check.json](traceability-check.json): 60항목의 연구 사실 ID → 출처 ID → 동일 모델·문서 버전·URL·원문 위치·확인 시각 대조. 오류0. 이 PASS는 링크 대조 범위다.
3. [evaluation-readiness.json](evaluation-readiness.json): 개발 자료와 독립 평가 자료의 구분 및 PM 여섯 유형 manifest 계약의 준비 상태.
4. [R03 환경/구현 증거](../R03-fridge-20261004/README.md)와 담당자의 [작업기록](../../../docs/작업기록/신진하.md)·[근거](../../../docs/작업근거/신진하.md).

| 제품군 / 모델 | 참고 사실 수 | 설명서 개정·대표 위치 | 연결 상태 |
|---|---:|---|---|
| 냉장고 T876MEE1H1 | 19 | MFL71401557 Rev.00_032526 / F10 → F-M p19 | 참고팩 연결 대조 통과 |
| 식기세척기 DUE6BGL2E | 20 | MFL71959117 Rev.07_030626 / D02 → D-M p57 | 참고팩 연결 대조 통과 |
| 전자레인지 MW23FDI | 21 | MFL68822538 Rev.00_120925 / M02 → M-M p37 | 참고팩 연결 대조 통과 |

각 출처 참조의 개정/수집 표식을 따로 보존한다. 제품 HTML의 `unversioned@2026-10-04`와 설명서의 제조사 개정은 다를 수 있다. `F10` 등의 연구 사실 ID와 `F-M` 등의 출처 ID는 업로드 후 생성된 canonical Evidence/document ID가 아니다. 아직 등록·조회 출력이 없어 해당 ID는 null이다.

## 개발 자료와 독립 평가 자료

기존 합성 개발 입력, 세 실모델 참고팩, R03 재현 입력은 개발/조사용이다. 이미 개발에 사용한 입력을 독립 평가로 다시 표시하지 않았다. 확인한 `data`·`evals` JSON에 독립 사례 manifest는 없었다. private 전체는 열람하지 않아 전역 부재를 단정하지 않는다.

PM 계약은 `schema_version`, `independent_from_development`, `cases`와 사례별 `case_id/category/request/data_path/output_contract_path`를 요구한다. 정상·기능중복·모델/버전혼동·상충리뷰·근거누락·명세변경의 여섯 유형과 기대 대응은 아직 준비/검증되지 않았다. 평가 완료/실제 모델 비교/독립성 입증은 미완료다. 테스트가 생성한 fixture 결과도 독립 평가 실행으로 계산하지 않는다.

## 게시 전에 알릴 막힘

- 프로젝트 Python3.11/uv/.venv 미확보. jsonschema는 선언/잠금에 이미 있지만 앞선 실행 환경에 없었다. 프로젝트 내부 설치 승인 대기, 새 설치/전역 변경 없음.
- 기존 API/코어에 문서 업로드·파싱 연결이 없다. #13 구현과 공통 API/schema의 PM 편집 범위 조율이 필요하다. R03 네 단계 미실행·미충족.
- 독립 평가 여섯 유형의 자료/기대 대응 미확보. Schema 런타임 검증도 아직 미실행이다.
- 과거 phase2 전체 validate 실패와 얕은 clone 이력 제한은 이전 기록 그대로다. PM 공유 증거를 임의 수정하지 않았다.
- PR 생성·push·Issue/Project 상태 전송·PM 검수·병합·통합은 수행하지 않았다. 최신 main의 지침/평가 안내는 로컬보다 새 버전임을 출처와 함께 기록했다.

## 같은 커밋과 게시 범위

[delivery-manifest.json](delivery-manifest.json)의 명시적 파일 목록을 부분 전달 후보로 묶는다. 이 문서·목록·작업기록·근거·실제 참고팩/진단 파일이 포함된 로컬 Git commit을 기준으로 검토한다. 실제 commit 결과는 사용자 보고와 로컬 commit receipt로 확인한다. 자체 commit SHA를 파일 안에 넣어 순환 참조를 만들지 않는다.

기존 가상 모델/합성 리뷰 원문, 원본 PDF/이미지, private 자료, 환경 실행파일, 과거 선정 문서, 하네스의 정식 상태 변경은 새 전달 파일 목록에 포함하지 않는다. 게시용 제목/본문은 [partial-pr-description.md](partial-pr-description.md)에 준비했다. 게시 전에 사용자가 준비 범위와 막힘을 볼 수 있도록 보고하며 원격 게시하지 않는다.
