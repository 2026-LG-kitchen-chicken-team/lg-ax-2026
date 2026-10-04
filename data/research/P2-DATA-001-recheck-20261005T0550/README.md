# #12 수동 재검증 — 2026-10-05 05:50 세션

2026-10-05T06:15:44.132133+09:00 작성. 개인 계정 ginaginaring / 기록 신진하-20261005-008-recheck-0550 / 근거 신진하-E014-recheck-0550.

게시 commit `4ad2f108c1730e70f10e1122094dabc551c84e57`의 같은 개인 기록/근거로 [#12 blocked 자기보고](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/12#issuecomment-5984535462)를 발송했다. 최초40초 ACK 대기를 보존했고 후속 조회에서 [ACCEPTED](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/12#issuecomment-5984542706)/보드 반영을 확인했다. 자기보고 수신이며 PM 검수·부모 완료가 아니다. 수신 추가 기록용 짧은 별도 파일 예약과 최종 해제/OFF 확인은 `closeout-release.json`에 연결한다.

공식 PDF 3개와 인용 15개의 해시·원문·문서 개정판 검사는 54개 모두 통과했다. 문서의 적용 범위는 별도로 분류했다. 지정 모델의 실제 1회 생성은 JSON 검사와 digest 고정에 성공했지만, 공용 설명서의 선택 기능을 정확 SKU의 확정 기능으로 잘못 판단해 의미 검증에 실패했다. 성공으로 고쳐 기록하거나 프롬프트를 바꿔 재시도하지 않았다.

## 코드·자료 연결

- 기준 main: `c6c1382faab29ffe06ee5d24c5ff0a196d5c1531`. PR74 고정 head: `5af64e93b1ca413317a91893e530901fc7f5874e`. main의 plan/dataset 바이트가 이 PR head와 같음을 확인했다.
- PR74는 PM이 닫았고 해당 자료 일부는 PR75/main에 인수됐다. PR74 자체 병합·DATA001 정식 완료·R03 인정·의존 해제를 주장하지 않는다.
- 실행별 원본 source SHA와 파일 SHA256은 `pdf-run*/audit.json`, `model-run1/model-result.json`에 있다. 모델 실행 당시 스크립트는 `model-run1/executed_model_check.py`, 인코딩 실패 당시 스크립트는 `pdf-run2/executed_audit_pdf.py`에 보존했다. 현재 model_check.py의 변경은 import 정렬뿐이며 실제 모델 재실행은 하지 않았다.
- 최종 게시 commit은 #12 자기보고의 두 고정 문서 링크로 연결한다. 이 README의 기준 commit은 실행 시점의 코드이며 게시 commit과 구분한다.

## 문서 버전과 적용 범위

| 연결 제품 | 공식 문서 버전 | PDF 자체의 모델 확인 | 인정 범위·남은 확인 |
|---|---|---|---|
| T876MEE1H1 | MFL71401557 Rev.00_032526 / 40쪽 | 표지는 상냉장 하냉동 공용 설명서, 정확 SKU 명시 없음 | 기존 승인 제품→설명서 연결은 계승. 일반 제거/청소 절차와 선택 기능 구분. 접이식 선반 적용·수량은 정확 SKU 근거 추가 필요 |
| DUE6BGL2E | MFL71959117 Rev.07_030626 / 60쪽 | DUE6 계열 등 공용 모델 목록, 정확 SKU 명시 없음 | 계열 설명서·기존 승인 연결의 바구니 절차. 모든 선택 기능을 해당 SKU에 적용하지 않음 |
| MW23FDI | MFL68822538 Rev.00_120925 / 40쪽 | 표지의 모델 목록에 MW23FDI 명시 | 해당 출력·30초 시간 증가·제조사 자동 데우기 메뉴. 개인 저장 프리셋 지원/미지원까지 입증하지 않음 |

원본 URL·전체 해시·인용 ID·PDF 쪽·추출문자 위치·텍스트 해시는 `pdf-run3/audit.json`에 있다. 페이지는 PDF 1부터 시작한다. 표지 및 모든 인용 관련 페이지 13장을 직접 렌더링해 검토했고 `visual-review.json`에 렌더 해시를 남겼다. 원본 PDF와 렌더는 private에 유지한다.

| 기능 ID | PDF 쪽 | 원문이 뒷받침하는 동작 | 조건 | 적용 범위 |
|---|---|---|---|---|
| T876MEE1H1-FEATURE-folding-shelf | 18 | 공용 설명서의 적용 모델에서 접이식 선반으로 식품 높이·크기에 맞게 공간 활용 | 공용 설명서의 일부 적용 모델 안내; 정확 모델 적용·선반 수량은 이 인용만으로 미확인 | optional_shared_manual_exact_sku_and_quantity_unconfirmed |
| T876MEE1H1-FEATURE-shelf-removal | 19, 18, 19 | 선반 위 식품을 치운 뒤 선반 양쪽을 받쳐 홈에서 고리를 분리 | 선반 위 식품 제거; 무거운 유리 선반 분리 시 주의 | shared_fridge_manual_general_procedure_via_approved_product_association |
| T876MEE1H1-FEATURE-inside-cleaning | 21, 5 | 부드러운 젖은 수건으로 닦은 뒤 물기 제거 | 구성품 분리 전 식품 제거(p21); 청소 전 전원 플러그 분리(p5) | shared_fridge_manual_general_procedure_via_approved_product_association |
| DUE6BGL2E-FEATURE-basket-assignment | 20 | 하단 큰 식기·냄비, 상단 작은 식기·컵, 최상단 수저류 | 공용 DUE6****E 설명서의 바구니별 식기 배치 안내 | matching_DUE6_family_manual_via_approved_product_association |
| DUE6BGL2E-FEATURE-basket-height | 23, 23, 24 | 높이를 3단계로 조절 | 식기 바구니를 모두 비운 뒤 높이 조절(p23); 양쪽 높이 동일 확인(p24) | matching_DUE6_family_manual_via_approved_product_association |
| DUE6BGL2E-FEATURE-nozzle-clearance | 24, 20 | 상단 바구니를 먼저 넣고 큰 식기가 상단 노즐 회전을 가리는지 확인 | 상단 바구니를 빼낸 상태에서 세척하지 않음(p20) | matching_DUE6_family_manual_via_approved_product_association |
| MW23FDI-FEATURE-power-selection | 25 | 200/400/600/800/1000 W의 조리 출력 선택 | 조리 출력 선택 안내이며 개인 시간/출력 조합 저장 지원 여부는 이 인용으로 미확인 | exact_model_listed_in_manual_named_operation |
| MW23FDI-FEATURE-quick-time | 17 | 시작/선택 누름마다 30초 증가 | 간편조리의 시작/선택 버튼 조작; 개인 프리셋 저장 지원 여부는 이 인용으로 미확인 | exact_model_listed_in_manual_named_operation |
| MW23FDI-FEATURE-auto-reheating | 18 | 제조사가 지정한 즉석밥·국/찌개·우유 메뉴 | 제조사 지정 메뉴의 기억된 조리시간; 개인 설정 저장 지원 여부는 이 인용으로 미확인 | exact_model_listed_in_manual_named_operation |

냉장고 선반 제거는 18/19쪽, 내부 청소는 21쪽, 청소 전 플러그 분리는 5쪽으로 구분했다. 식기세척기의 빈 바구니 상태 조절·양쪽 같은 높이·노즐 간섭·상단 바구니 없이 사용 금지 조건을 유지한다. 전자레인지 출력은 25쪽의 200/400/600/800/1000W다. **실제 고객 후기 0개이며, 설명서의 지시문은 고객 수요·발생 빈도·개선 효과의 증거가 아니다.**

## 실제 모델 검증과 실패

- 경로: 개인 client 설정 → loopback model_proxy(127.0.0.1:18873) → 기존 StructuredModelClient/OllamaAdapter → 인증된 공유 모델.
- `qwen3:8b`, digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`, temperature 0, seed 42, context 4096, output 256, think false, timeout 45초. 실제 호출 1회.
- 입력/출력/schema/생성 옵션/사용량/실패는 `model-run1/model-result.json`, 입력 문자열은 `prompt.literal.json`, schema는 `schema.json`. 문자열은 공백까지 원래 입력과 같으며 원래 txt는 private에 보존했다. Git의 인용문 행 끝 공백 검사에 맞춰 JSON 문자열로 공개했으며 모델 입력을 수정하지 않았다.
- 기대: `shared_manual_only`, exact SKU false, demand false. 실제: `exact_sku`, exact SKU true, demand false. JSON은 통과했지만 적용 범위가 틀렸다.
- 이 사례는 개발용 진단이다. 독립 평가·일반화 성능·상품기획 Agent 완성을 인정하지 않는다. PM PC 연결은 이번에 성공했으므로 PC가 꺼졌다고 기록하지 않는다. 추후 연결 실패 시 실패 그대로 기록한다.

## 실행 환경·예약·보존

`environment-readiness.json`에 개인 GitHub 확인·개인 중앙 등록·기존 Codex 로그인·도구 환경·격리 미완료를 기록했다. 자동화와 네 개인 선택은 OFF, Worker 미설치/미실행. 전용 계정/VM·별도 CODEX_HOME 직접 로그인·publisher 경계 검증은 아직 남았다. PM 인증 파일은 읽거나 공유하지 않았다.

파일 3경로와 CPU/모델/포트 자원은 중앙에 예약한 뒤 실행했다. 별도 예약의 같은 소유자 충돌은 자기 예약을 해제하고 하나로 합쳐 복구했다. 상세는 `reservation-history.json`, 최종 해제/OFF 확인은 `release-confirmation.json`. 이번에 시작한 프록시 프로세스만 종료했고 종료 후 TCP18873 listener가 없음을 확인했다.

- `pdf-run1/failure.json`: Git 소유권 검사 실패. 이전 결과 보존.
- `pdf-run2/audit.json`: pypdf 표지 인코딩 때문에 버전 검사 3개 실패. 해시·인용은 통과. 렌더 확인 후 PDFium 표지 텍스트로 보완.
- `pdf-run3/audit.json`: 새 폴더에서 54검사 PASS.
- `model-run1/model-result.json`: 실제 모델 1회, 의미 실패 보존.
- `search-preparation/comparison-plan.json`: 별도 폴더의 #13/#14 비교 입력 준비만. 실행/성능 수치/모델 채택 없음, 선행 완료 처리 없음.

재현은 새 예약 후 **존재하지 않는 새 실행 폴더**를 지정한다. 두 runner는 기존 폴더 덮어쓰기를 거부한다. PDF runner는 pypdf/PDFium이 있는 bundled Python, 모델 runner는 Python3.11/httpx/jsonschema가 있는 프로젝트 환경을 사용한다. 모델 설정은 본인의 private client 파일이며 인증 파일을 복제하지 않는다.

```powershell
python -X utf8 data/research/P2-DATA-001-recheck-20261005T0550/audit_pdf.py --run-directory data/research/P2-DATA-001-recheck-20261005T0550/pdf-run-NEW
python -X utf8 data/research/P2-DATA-001-recheck-20261005T0550/model_check.py --config private/본인/client.json --run-directory data/research/P2-DATA-001-recheck-20261005T0550/model-run-NEW
```

## 인수인계

우선 PM/CORE 담당이 공용 설명서·정확 SKU·수요 근거의 검사를 구분해 이번 실패의 후속 조치를 배정해야 한다. 신진하는 정확 SKU 접이식 선반 적용 근거를 추가 확인하고 독립 평가와 #13/#14의 같은 한국어 정답셋/모델 카드·라이선스/revision/tokenizer 고정을 준비한다. 정식 완료·의존 해제·검수·병합은 PM의 실제 판정을 기다린다. 현재 사람의 즉시 조작 없이 수동 보고는 진행한다. 무인 실행 전에 전용 계정/VM과 별도 CODEX_HOME 개인 로그인·권한 경계 검증이 필요하다.
