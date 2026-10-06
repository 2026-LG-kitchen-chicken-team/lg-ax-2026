# 신진하 #14 세션 근거

- 근거 ID: E-DATA003-SEARCH-COMPARE-20261006-01a10834
- 연결 기록: session-work.md, 기록 ID 신진하-20261006-DATA003-SEARCH-COMPARE-01a10834.
- 코드/자료 확인 기준: GitHub main `b477860b2612f51b7e81f37b635c05ba02338bfb`; 2026-10-06 KST.

## 원본과 실제 인수

github/main.json/tree.json/pr131.json/pr141.json/pr151.json/pr154.json과 PM 댓글 원본을 읽기 전용으로 저장했다. main-reference/evals/pm-data-intake/20261006/source-intake.json은 실제 선택 인수의 파일/원 PR head/hash를 연결한다. prepared/PR-intake-scope.json은 원 PR 닫힘과 전체 병합·활성 적용·부모 완료를 구분한다.

PM 등록 팩은 main-reference/data/research/PM-DATA-intake-20261006/generated/의 dataset/plan/origins/pack-summary/source-range-verification이다. 공식 설명서3개와 공개근거21개/기능9개, dataset_version lg-manual-scope-20261006.3-pm-intake를 확인했다. 본 세션은 PDF를 새 다운로드/파싱/등록하거나 OCR·시각 검수를 다시 하지 않았다. 원문 범위 검사의 출처는 PM 실행 자료이며 본 세션의 해시/길이/필드 대조와 구분한다.

## 과거 실행 원본과 보존

원 위치: .worktrees/data003-preparation/evals/data003-live/20261005/retrieval-v1/results.json 및 ocr-v3/results.json, 같은 폴더의 실제 runner snapshot·환경 freeze·downloaded-models.json. prepared/historical/에는 기존 공개 산출물75개를 byte 동일 복사했다. 원 publication-manifest의 SHA256을 전부 대조했으며 prepared/historical-preservation.json에 원 경로/bytes/hash/main blob 일치 여부를 남겼다. 원 source/실측 결과/실패/gold를 수정하지 않았다.

검색225회·warmup6회, OCR70회·warmup2회는 **과거 실제 실행**이며 이번 신규 실행 횟수가 아니다. 기존 Hit@1 10/11,11/11,11/11과 중앙지연0.6337/316.2207/6006.4974ms를 같은 원시 결과에서 재계산했다. 새 원문 corpus 성적은 전혀 산출하지 않았다. 과거4 no-gold는 순위 분모에서 제외하고 의미 응답 성공을 추정하지 않았다.

OCR 원 crop manifest/visual-review/gold text/hash를 연결했다. normalized CER의 문자 거리·숫자/단위 파싱을 다시 계산했다. OCR 오류 원인과 분모15/12/11을 각각 유지했다. 원 PDF 문자 추출의14구절 존재와 OCR CER은 같은 정확도 척도가 아니다. 표 열/모델 연결·자동 전체 레이아웃은 미측정이다.

## 실제 파일/산술 검사와 조건

제어된 새 표준 라이브러리 분석 스크립트 prepare_comparison.py와 finalize_analysis.py만 실행했다. 저장소 소스·테스트·모델·타 채팅 스크립트를 호스트에서 import/실행하지 않았다. 전자는 소스 파일 조회/해시/원시 결과 산술/새 입력·표 작성, 후자는 저장된 순위와 typed 숫자/단위 재계산이다. 분석 결과를 저장소 시험 PASS·신규 모델 실행·독립 Agent 평가로 표현하지 않는다.

명령:

```text
python -I -S -B -X utf8 publication/data003-search-compare-20261006-01a10834/prepare_comparison.py
python -I -S -B -X utf8 publication/data003-search-compare-20261006-01a10834/finalize_analysis.py
```

두 명령 exit0. prepared/analysis-checks.json의45항목, independent-arithmetic-checks.json의528항목 모두 일치. 결과225/70행·새 측정225행·현재원문21개·추가근거6개 확인. 생성 폴더/파일은 기존 경로가 있으면 거부하도록 mkdir(exist_ok=False)/open(x/xb)로 만들었다. 원 모델 가중치19개는 파일 존재·크기만 확인하고 역사상 검증된 revision/hash를 참조했다. 환경 재설치나 새로운 원 가중치 전체 hash 검사를 하지 않았다.

고정 Docker image ID 존재는 image inspect로 읽었고 컨테이너/모델은 시작하지 않았다. AGENTS/CLAUDE 고정 main bytes 동일을 직접 대조했으며 지침 검사 스크립트를 실행하거나 지침 파일을 변경하지 않았다.

## 공유 자원·인증·게시 경계

resource-readiness.json: 기존 개인 인증으로 GET 상태 조회만 수행, HTTP200/teamOFF/모두false/#12냉장고예약active. 토큰·Git 자격증명은 메모리에서만 사용하고 파일/출력에 보관하지 않았다. 다른 세션 예약을 해제/갱신/우회하지 않았다. 새 공유 모델/CPU 예약이나 생성 호출0이다. 읽기 전용 metadata와 비공유 별도 준비파일 작업만 수행했다.

사용자 지시로 신규 서버배포/모델서비스/자동화/인증 변경0, #13 등록/보존코드·판단코어·웹/Schema/API 변경0, push·Issue/PR 게시·다른 채팅 메시지0. 최신 사용자 확인 제한을 기록했다.

## 주장 범위와 대기

지지하는 주장: 기존 실험의 보존/산술 재계산, 현재 PM 자료의6근거 포함, 원문21개와 요약27개의 정확한 차이, 재실행 가능한 공통 비교 입력·측정 항목 준비.

지지하지 않는 주장: 새 corpus 모델 성능·실제 #13 이번 등록/재시작 성공·표 전체 OCR 정확도·선택 SKU 기능 적용의 신규 증명·고객 불편/콘셉트 품질·최종 독립 평가·PM에게 실제 전달·#14 전체 완료.

다음 재개는 #13 실제 handoff와 FR-01 대응 확인, 승인된 격리 모델 환경·자원 확인 뒤 동일 입력의 새 검색 실행이다. 별도 새 run/측정 보고를 만들고 기존 출력/실패는 유지한다.
