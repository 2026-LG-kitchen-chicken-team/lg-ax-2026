# R8 실제 공개 자료 통합과 첫 실행 입력

2026-10-07 현재 채팅의 수동 지원 구현이다. 기존 담당자가 직접 실행한 기록으로 대체하지 않는다. 자동 작업, 운영 DB, 중앙 큐, 외부 작업자 메시지는 변경하지 않았다.

## 이어서 완료한 부분

기존 `fixed18/records.json`의 179건과 `balanced-pilot-v2/new_unique_records.json`의 59건을 합쳐 공개 후기 238건을 하나의 연구 자료팩으로 만들었다. 원문, 원 후기 ID, 본문 해시, 구매일, 게시일 null, 구매 SKU null, 기존 분할 및 입력 보류 사유를 모두 보존한다. 추가 표본의 `body_group_id`에는 기존 SQLite 적재기에 필요한 `dedup_group_id` 별칭만 추가했다. 원 자료팩은 수정하지 않았다.

| 제품군 | 보관 후기 | 개발 입력 | 독립평가 후보 | 시연 후보 | 격리 |
|---|---:|---:|---:|---:|---:|
| 냉장고 | 79 | 48 | 11 | 11 | 9 |
| 전자레인지 | 79 | 45 | 12 | 22 | 0 |
| 식기세척기 | 80 | 48 | 13 | 16 | 3 |
| 합계 | 238 | 141 | 36 | 49 | 12 |

`data/research/r8-public-research-20261007/`의 주요 파일은 다음과 같다.

- `records.json`, `products.json`, `manifest.json`, `files.json`: 후기 238건, 등록된 제품 페이지 18개, 수집·분할·한계 기록과 해시.
- `bundles/{fridge,microwave,dishwasher}.development.research-bundle.json`: PM의 ResearchBundle 1.0 계약을 그대로 소비하는 제품군별 첫 실행 입력. 개발 분할 141건만 제공한다.
- `official-sources.json`: 설명서 3문서의 기존 발췌 15개와 LG FAQ·설치 가이드·경쟁 공식 제품 지원 발췌 각 1개. PDF 전체를 입력 본문에 복제하지 않는다.
- `selected-official-sources.json`: 이번 수동 확인으로 추가한 공식 웹 발췌 3개. 원 URL과 제목·섹션·확인일·적용 범위를 담는다.
- `build-review-workbook.mjs`: 같은 JSON에서 검토용 엑셀을 재생성하는 Artifact Tool 빌더.

SQLite는 기존 `save_landing_db`를 재사용한다. `reviews`에는 격리 표본을 포함한 238건과 모든 원 메타데이터, `products`에는 18개, `research_sources`에는 공식 근거 18개, `research_bundles`에는 3개를 저장한다. Windows에서 DB 연결이 남아 새 파일 정리가 막히던 부분은 적재 완료 후 연결을 명시적으로 닫도록 수정했다. 원 CSV·HTML 파서, 검색기, OCR은 재구현하지 않았다.

## 실제 공개 근거와 범위

| 자료 | 실제 출처 | 이번 입력의 범위 |
|---|---|---|
| LG FAQ | [세척이 잘 안돼요](https://www.lge.co.kr/support/solutions-20151678633118) | 올바른 식기 수납 2문장. 게시일은 페이지의 2026-05-29. 공용 안내로 개별 SKU 적용은 미확인 |
| LG 설치 | [식기세척기 설치가이드](https://www.lge.co.kr/story/user-guide/dishwashers-install-guide) | 일반 걸레받이용(150mm) 빌트인 싱크대 깊이 안내의 일부. 타입·환경 조건을 유지하며 특정 고객의 설치 가능 판정은 하지 않음 |
| 경쟁 공식 자료 | [Samsung DW99F79E1UHCS 지원](https://www.samsung.com/sec/support/model/DW99F79E1UHCS/) | 공식 제품명에서 빌트인 14인용·필터 내장형·컵 맞춤 세척 존재만 확인. 세부 성능·동일 조건 시험·우열은 미확인 |

Q&A는 동결된 실제 질문·공식 답변 원문을 확인하지 못해 `needs_normal_UI_capture`, 실제 원문 0건으로 남겼다. FAQ를 고객 질문으로 바꾸거나 답변을 만들어 채우지 않았다. 원 후기의 구매일을 게시일로 바꾸지 않았고 설명서 개정번호를 게시일로 추정하지 않았다.

## 실행

저장소의 CORE·contracts import 경로와 `jsonschema`가 설치된 기존 Python 환경에서 실행한다. 아래 명령은 네트워크·모델 호출을 하지 않는다.

```powershell
$taskPythonPath = (Resolve-Path packages/core/src).Path + ';' + (Resolve-Path packages/contracts/src).Path
$env:PYTHONPATH = $taskPythonPath
python scripts/build_research_bundle.py
python scripts/build_public_review_db.py --profile r8 --output <새로운-연구용-DB-경로>
python -m unittest discover -s tests -p test_r8_public_research.py -v
```

기존 DB 파일을 덮어쓰지 않으며 R5 원 자료팩을 생성 목적지로 사용할 수 없다. R8 DB 검증 기준은 저장된 JSON 행의 완전 일치다. SQLite 엔진 버전에 따라 파일 바이트 해시는 달라질 수 있으므로 기존 DB의 파일 해시 일치를 행 내용 일치로 대체 주장하지 않는다. 기존 `pilot1`/`fixed18` 프로필은 유지된다.

엑셀은 대화별 작업 폴더에 번들 `node_modules` junction과 `build-review-workbook.mjs` 사본을 준비한 뒤 실행한다. 저장소의 의존성 디렉터리는 변경하지 않는다.

```text
node build-review-workbook.mjs <자료팩-폴더> <산출물-폴더> <미리보기-작업-폴더>
```

이번 산출물은 대화의 `outputs/r8-public-research/`에 있는 `public-research-238.sqlite3`와 `LG-실제공개자료-238건-20261007.xlsx`다. 엑셀은 자료 현황, 제품 목록, 후기 원문, 공식 근거 4개 탭이며 원문 238개를 한 후기당 한 행으로 보존한다. 표에는 필터와 고정 헤더가 있고 날짜는 실제 구매일·게시일 열을 분리해 저장한다. 집계 수식의 값과 변경 반응, 원문 일치, 수식 오류 검사 및 모든 탭의 렌더링을 확인했다. 데스크톱 Excel에서 열어 검증한 것은 아니다.

## 소비 시 유지할 구분

현재 후기의 독립 확인 구매 SKU 및 실제 게시일은 각각 0건이다. 기존 `eligible_for_model_input=false`는 정확 모델에 대한 입력 보류 상태로 그대로 남기고, 첫 bundle의 `analysis_scope=product_group`에서 표시 페이지 연관과 고객 보고라는 한계를 함께 전달한다. 이 자료로 특정 SKU의 결함·불편 해소·시장 발생률을 단정하면 안 된다.

별점은 본문의 긍정·부정·혼합 주장과 동일한 분류가 아니다. 기존 179건은 모두 별점 5이며 신규 59건에 최근·낮은 별점 표본이 들어왔다. 전체 별점 1~3은 30건, 별점 5는 208건이다. 목적 표본과 분모를 표시하며 대표성이나 새 주제 포화를 확보했다고 주장하지 않는다.

독립평가 후보 36건과 시연 후보 49건은 실행 승인된 수가 아니다. 기존 독립성 보류 overlay를 통째로 보존한다. 원 후기 776453·842682의 기존 개발 노출과 남은 lineage 검토는 계속 시연 후보 보류 사항이다. 개발 bundle에는 평가·시연·격리 표본을 포함하지 않는다.

공식 문서에 기능이 있다는 근거와 고객이 그것을 쉽게 발견·이해·실행했다는 근거를 구분한다. 설명서의 공용 모델 적용 조건, 필수 조작 조건, 현재 버전만 확인했다는 한계를 발췌마다 유지한다. 고객 후기의 경험 보고는 검증된 결함이나 원인으로 자동 확정하지 않는다. 경쟁사의 기능 존재를 LG 모델의 기능이나 개선 효과로 전이하지 않는다.

## 남은 수동 작업

첫 bundle을 CORE의 실제 분석·조건 변경 흐름에 연결하고 원 source ID가 기획 결과·근거 열기까지 유지되는지 확인한다. DATA의 대규모 수집 완료를 기다릴 필요는 없다. 병렬 후속은 정상 공개 UI에서 실제 Q&A 원문·답변·표시 날짜·원 ID를 소량 고정하고, 나머지 15개 제품 페이지의 설명서 확인을 보충하는 것이다. 후기 추가 수집은 제품군·모델·별점·본문의 혼합 경험·구매 기간·사용 조건을 나누고 중복 제거 및 새 주제 포화를 기록한다. 게시 기간 구간은 실제 게시일을 확인한 자료에만 적용한다.
