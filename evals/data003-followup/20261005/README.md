# BM25·OCR 입력·#15 준비 수행 결과

2026-10-05 사용자 지시 “그럼 지금 할수있는작업 3가지 있으니까 그거 지금하자”로 아래 세 로컬 작업을 수행했다.
브랜치 codex/data003-preparation-20261005 / base b82cf9c2d063458bc3e54eb34b856c1050c93ced. 이전 단계3/4와 다른 #12 작업 공간은 보존했다.

| 작업 | 실제 결과 | 위치 |
|---|---|---|
| BM25 실행 코드·기준선 | 15문항×5회=75회, warmup2회 별도. 근거 있는11문항 중10개 Hit@1, 모델/버전 혼입0·실행 오류0 | [최종 v3 결과](../../data003-execution/20261005-cpu-baseline-v3/README.md) |
| OCR 입력 준비·텍스트 추출 | 원문6페이지/6사례의 인식 영역14개를300DPI/RGB로 고정·시각 검토. pypdf 추출에서14구절 모두 발견 | [OCR 입력](../../data003-ocr-inputs/20261005-v2/README.md) |
| #15 검수 준비 | 검사 기준10개·6유형별2개/총12개 개발 사례, 실제 충돌2개 보존, 빈 검수57칸 | [DATA004 준비](../../data004-preparation/20261005-v2/README.md) |

## BM25에서 확인한 실패

Hit@1/Recall@3/MRR@3는 각각10/11=0.9091이다. MW-01의 수동 출력 선택 질문에서 M11(200/400/600/800/1000W)을 찾지 못하고 최대 고주파 출력 M06이1위였다.
어휘·조사 처리의 한계를 보존했고 정답을 보고 tokenizer/corpus를 고치거나 실패 문항을 지우지 않았다.
정답 근거가 없는4문항은 순위 평균에서 제외했다. 그 문항의 의미 답변·추가 조건 요청·금지 주장 준수는 미평가다.
FR-04의 미지정 과거 개정은 runtime input에서 버전null로 별도 고정하고 현재 설명서로 대체하지 않았다.

최종 기준선은 v3이다. 이전 v1/v2 결과는 초기 코드 검사/CPU 작업 중첩 기록으로 보존하며 성능 비교의 기준으로 섞지 않는다.
v3 실행 중 이 AI의 PDF/병렬 처리 작업은 없었다. 다만 공유PC의 외부 프로세스/부하는 통제하지 못했다.
지원11문항의 성공 측정55회 median0.3318ms/p95 0.6938ms, 프로세스 peak working set25.90MiB.
이는 사실 요약27개인 작은 corpus의 Python BM25 검색시간이다. 전체 Agent나 운영 환경 성능이 아니다.
BM25는 Python float64/한 스레드다. 이후 BGE의 FP32/4threads와 수치 정밀도/스레드가 같다고 표시하지 않는다.
CPU·RAM은 platform/Windows API로 기록했다. CIM CPU/메모리 접근은 거절되어 순간 부하는 미확인으로 보존했다.

## OCR·검수 준비의 해석

OCR crop의 좌표·크기·원문/hash·정답을 고정했다. 처음 MW 문장 crop에 들어온 다음 줄을 수정했고,13L 뒤 괄호·1000W의 원문 각주 표식도 정답에 포함했다.
DUE 표의 빌트인 열과 MW23FDI 열을 전체 원문 표에서 검토했고, mm 머리글은 context 이미지에 보존했다.
이미지·페이지 전문과 합성 개발 입력/기대 답안은 private에 있다. 공개 메타데이터의 public 표기는 원문의 재배포 라이선스를 의미하지 않는다.
문구 존재14/14는 OCR CER·숫자/단위 정확도·모델 열 연결 정확도가 아니다. 해당 점수는null이며 Paddle 인식 호출0이다.

#15의 상충 리뷰4개와 새 명세2개는 명시적인 합성 개발 fixture다. 실제 고객 리뷰0개·실제 제조사 새 개정0개이며 E01 독립 사례로 사용하지 않는다.
변경 전후snapshot/hash·DEV source ID·예상 영향 판단/후보와 보존할 사실을 나눴다. 실제 코어 변경 서비스 호출은0이다.
실제 원문 충돌 C01/C02는 값·범위·출처·미해결 상태를 보존했다.

## 재현과 검증

저장소 루트에서 기존 Python3.11로 BM25/검수 준비·검사를 실행하고, 기존 번들 PDF용 Python3.12로 OCR 입력을 만든다. 새 설치/다운로드/유료 API/GPU 실행은 없다.
각 생성 스크립트는 기존 출력 덮어쓰기를 거부하므로 재실행할 때 새 출력 폴더를 지정한다.

```powershell
python -B -X utf8 scripts/run_data003_bm25.py --output evals/data003-execution/새로운-실행-ID
python -B -X utf8 scripts/prepare_data003_ocr_inputs.py --source-directory '기존-원문폴더의-절대경로' --output evals/data003-ocr-inputs/새로운-ID --private-output private/data003-ocr/새로운-ID
python -B -X utf8 scripts/prepare_data004_review.py --output evals/data004-preparation/새로운-ID --private-output private/data004-development/새로운-ID
python -B -X utf8 scripts/verify_data003_followup.py --source-directory '기존-원문폴더의-절대경로'
python -B -X utf8 -m unittest discover -s tests -p test_data003_bm25.py -v
```

verification.json의 실제 무결성164항목 PASS/오류0. 새8테스트·Ruff·계약·phase2 validate·동일 지침 검사 PASS. 실행 출력은 execution-checks.json에 보존했다.
verify 스크립트는 현재 채택한 v3/v2 경로를 고정한다. 새 실행을 검수할 때 고정 경로/버전을 갱신하고 이전 검증을 보존한다.
기존 시스템 전체 회귀·웹/MCP·실모델·독립 평가를 이번 검사로 재실행했다고 하지 않는다.

## 진행 체크리스트와 다음 담당

- [x] 신진하: 새 입력 어댑터·무정답/scope 안전 처리·BM25 기준선 실제 실행
- [x] 신진하: OCR 원문 영역/좌표·짧은 정답·원문/PDF 추출 대조와 입력 시각 검토
- [x] 신진하: #15 검사 기준·실제 충돌 보존·개발 사례/변경 이력·빈 검수표 작성
- [ ] 신진하: 기존 BGE/재정렬/Paddle 실행 환경·라이선스/weight revision 확인 후 실제 비교
- [ ] 신진하: #13 처리 출력 연결과 실제 원문/근거 통합 확인
- [ ] 황대겸·PM 정이량: 변경 재검토 서비스의 실제 영향/수정 및 별도 독립 평가 의미 검토
- [ ] PM 정이량: 실제 인수·병합·통합/최종 완료 판단

현재 사용자 직접 할 일은 없다. 원격 게시·PR/push·자기보고 ACCEPTED·PM 수신·Notion 반영·#14/#15 정식 완료는 미실행이다.
