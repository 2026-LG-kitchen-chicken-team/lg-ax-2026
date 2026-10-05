# PR151 선택 인수 읽기 검수 · 2026-10-06

2026-10-06 08:57 KST 기준, 검토한 기능 변경에서 구체적인 병합 차단 결함을 찾지 못했다. **판정은 선택한 구현 범위의 인수 승인(`approve_scoped_intake`)이며 CORE·WEB 상위 작업 완료, 실모델 품질 합격, 운영 배포 또는 전체 신청서 요구사항 완료의 승인이 아니다.** 실제 모델 원본 6사례는 완료 0·보류 1·실패 5, 후속 냉장고 2사례는 완료 0·보류 2이며 후보 생성 0을 유지한다.

## 지시·범위·독립성

PM은 PR151의 통합 소스, 원본/CRLF 해시 보존, WEB 최종 수정, 실제 실패 기록과 정상 경계·안전 판정을 읽기 검수하고 구체적인 차단 결함을 보고하도록 지시했다. 개인 기록·운영 상태·원 제출물·소스는 바꾸지 않고 이 새 검수 문서만 작성했다. 저장소 코드·검사·모델을 실행하거나 PR·메일·Notion·controller를 변경하지 않았다.

검수 AI는 통합 실행 담당 PM AI와 별개지만 CORE 선택 인수와 제한적인 citation 피드백 수정에도 참여했다. DATA·WEB 및 인수 도구를 별도로 읽었으나 CORE에 대해서는 개발과 완전히 분리된 독립 평가자라고 주장하지 않는다. 이 문서는 맹검 품질 평가·사람 패널·강한 일반 LLM 기준선을 대신하지 않는다.

## 고정 대상

| 대상 | 고정 버전·범위 |
| --- | --- |
| 통합 기준 main | `02f9a643e92c4665f2f0f71a5690f9ed6ed28930` |
| PR151 로컬 검수 head | `4654c0eb9bfd98965e1d99bc1f63ffb8e043ff10` |
| 기능 소스·원본 byte 보존 | `3bbdd2ebc8ef6e9644cde9dd9c1e7a8c89f55a7a` |
| 이후 기록 변경 | `aad053c4b8661be4683cad48eeeef63ca7c42984`, `4654c0e…`: 통합 품질 설명과 리뷰 동향 후속 과제 기록만 변경 |
| WEB 최종 인수 증빙 | `bc2c01c135f84d9b70d262953fff68db6675aa43`, 원 수정 `d268debb73362ed4449e5990c4e42dac2341a9d9` |
| 별도 기록 재생 평가 후보 | `c9378241cb6e37437b8bc5edd5dbcb57a8c3ed3a`의 `evals/pm-intake/20261006/replay_workspace.py` 및 설명 문서; 이 검수 head에는 아직 포함되지 않음 |
| 비공개 선택 인수 도구 | 최초 검수 SHA256 `770d3678f6f0827bff3dfbfe250ed4935be66b8f54cbd3c589c5aca277c1c253`, 최신 읽기 검수 SHA256 `4a6be66242caed87160a144739849e60df2f25a5a7f62be0d7e0e4444cb5b865` |

원격 PR151 조회 당시 head는 `b5d25cb9b72d38d3e949e59ae087ed94e696f9db`였다. 위 로컬 검수 판정만으로 최신 push·CI·실제 병합을 주장하지 않는다. 이후 소스 변경은 별도 검수가 필요하다.

## 기능·원본 경계 확인

- CORE 선택 출처는 PR142 `e7005f7cc0a6bb56bb6abb411dd9d48014c828fa`, PR145 `1bddade41d36103be0f2a27923246efd83fcea3d`와 `core/provenance.json`에 고정되어 있다. 원 담당자의 의도·근거 기록을 source SHA 링크로 유지한다. 원 PR136·97은 역사 근거이며 현재 구현으로 바꿔 기록하지 않는다.
- 통합된 CORE 기능 파일·Skill은 별도로 검증된 `c3d716061fec13ce23773af339d583b475dc7ebb`와 차이가 없음을 Git diff로 확인했다. 단계 재시도와 설치된 `review_revision`은 같은 최대 2회 수정 예산을 소비한다. 빈 후보 승인도 의미 검사를 호출하며, 고객 리뷰로부터의 need와 기능 존재·잔여 불편을 구분한다. 공개 자료만 있고 고객 리뷰가 없는 입력을 수요의 근거로 바꾸지 않는다.
- citation 수정은 원 고정 입력에 정확하게 연결된 설명서가 있는 경우에만 제한된 재시도 피드백을 준다. ID 추가·지원 판정 자동 변경·자동 승인이 없다. absent/conflicting/unknown과 일반 검토 실패는 보류를 유지하며 재시도는 공유 예산을 소비한다. 실제 후속 두 실행에서 의미 품질 완료는 발생하지 않았다.
- DATA의 `DocumentStore` alias 수정은 복사한 내부 dataset만 사용한다. 새 CSV import는 byte/행 한계, 승인된 모델·문서·자료 성격, ID 중복·원문 위치를 확인하고 반환 값을 분리한다. formula나 문서 명령을 실행하지 않는다. 원문 범위 도구는 원 bytes·텍스트·정확 span·scope를 검사하고 제공된 PDF/OCR 텍스트를 원 PDF 검증 완료라고 표시하지 않는다. 공개 설명서 팩과 합성 리뷰 팩을 실제 고객 자료로 혼합하거나 재명명하지 않는다.
- WEB은 판단 당시 원문과 현재 원문을 구분하며 dataset identity가 일치할 때만 현재 자료를 대조한다. 조건 변경은 새 요청으로 저장하고 부모 결과를 바꾸지 않는다. 잘못된 부모·프로젝트·회차·순환 관계는 비교를 보류한다. 부모 또는 선택 실행이 pending/running이면 빈 결과를 후보 삭제·질문 해결로 표시하지 않는다. held/failed와 원 실패 비용은 화면 완료로 바꾸지 않는다.
- `02f9a64…`에서 `3bbdd2e…`까지 `services/`, `scripts/`, `packages/contracts/`에 변경이 없음을 확인했다. 이 선택 인수의 제품 소스로 자동화 운영 정책·controller·공통 계약을 수정하지 않는다.

원본 byte 보존은 읽기 전용 Git blob 비교로 확인했다. `3bbdd2e…:evals/pm-intake/20261006/live-quality/original-six/{case}.output.json`과 비공개 원 실행 `live-intake-37f7e3fd0e76/{case}/output.json`의 `git hash-object --no-filters` 값이 6개 모두 같았다. `citation-repair-two/{fridge-normal,fridge-changed}.output.json`도 비공개 `live-intake-a748b663d9c3` 원본과 2개 모두 같았다. 해당 하위 `.gitattributes`의 `*.json -text`가 CRLF를 포함한 원 JSON bytes를 보존한다. PR142의 `thinking-8b-02-recommended-sampling.json` 원 실패 파일도 고정 원 source와 통합 복사본의 Git blob이 같다. 원 실패를 정상 fixture로 덮어쓰거나 새 모델 실행으로 표시하지 않았다.

## 기록 재생 평가 코드 별도 검수

`c9378241…`의 새 평가 runner는 실제 자료 조회로 조립한 입력이 녹화의 `original_input`과 같을 때만 그 기록을 반환한다. 원 입력·출력·dataset **파일 bytes SHA**를 생산자 요약과 대조하고 Agent 입력/Workspace dataset의 **canonical SHA**는 별도 필드에 남긴다. 두 해시 규약을 같은 값이라고 강제하지 않는다.

실제 임시 HTTP POST/GET·SQLite 저장은 원 녹화 보존, 기존 `public_run` 진단 투영, 부모 불변, 사용자 변경 0/1과 Agent 내부 수정 0~2, held/failed·후보 0을 확인한다. MCP stdio는 같은 프로젝트·실행 ID와 공개 snapshot을 읽어 비교한다. 인증은 게스트에서 생성한 일회 토큰뿐이며 무인증 401·viewer 쓰기/다른 소유자 읽기 403 및 거절된 쓰기에서 runner 미실행을 확인한다. 원 입력 파일들은 뒤에도 같은 hash여야 한다.

새 모델 호출 0·`quality_complete=false`이며 외부 ChatGPT/Claude 연결·실제 브라우저·운영 cutover를 증명하지 않는다는 라벨이 맞다. 읽은 코드에서 pass를 무조건 만드는 fallback을 찾지 못했다. **이 읽기 검수 자체는 평가 실행 성공 증거가 아니며 실제 고정 격리 실행 산출물을 별도로 인수해야 한다.** 이후 평가 코드/문서 변경에는 이 후보 SHA와의 연결을 다시 확인한다.

## 비공개 선택 인수 도구의 승인 근거 형식

최초 도구와 최신 버전의 차이는 실제 interpreter-only cutover 수신증, 정해진 launcher·wrapper·dependency 파일집합/hash를 요구하는 검증 추가다. 기존 원본 작업·시도·증빙·예산·구성 및 Ready 기본 유지 경계는 바꾸지 않는다. 최신 wrapper는 정확한 고정 `pm_entry`/config 인자를 요구하므로 기존 실제 PM process 식별 조건과 맞는다. 비공개 주소·인증값·전체 운영 JSON은 이 문서에 복사하지 않는다.

승인 형식에서 차단 결함을 찾지 못했지만 **실제 적용 허가를 의미하지 않는다.** 적용 전에는 다음 실제 근거가 모두 있어야 한다.

1. 실제 PM 인증 계정이 만든 non-draft 병합 PR, 정확한 PM head·merge·현재 main, 지정 CI 성공, formal Project 수신과 central ACK가 같은 merge를 가리킨다.
2. 별도의 인증된 PM 목적 한정 Issue28 댓글이 전체 manifest SHA와 head·merge·대상 job, `selective_pm_intake`·`parent_done=false`를 명시한다. 승인 manifest 안에 자기 댓글 hash를 넣는 자기 참조가 없다.
3. 선택한 원 구현 파일·검사 파일의 원 head→통합 merge hash 관계를 전부 확인한다. 적응 변경은 별도 검수 수신증에 명시하며 원 PR145·147을 실제 병합했다고 주장하지 않는다. 구현 session과 검수 session도 별도다.
4. 현재 operator 인증, 모드·원 결과·실패·비용·원 예약 보존, 활성 작업/미확정 intent 없음, 실제 고정 런처·소스·경계 검사가 통과한다. tick lock→그대로의 quiesce→중지 후 loop lock 순서가 유지된다.
5. 실제 accept POST 전 durable intent를 쓰고 같은 호출을 무조건 재전송하지 않는다. 애매한 응답은 명시적 조정 근거가 필요하다. 이미 수락된 queue를 되돌리지 않으며 개발 ledger는 append만 한다. lock을 모두 해제한 뒤 원 상태에 맞춰 같은 고정 PM을 복구한다.

미래 병합·CI·ACK·정식 PM 댓글이 아직 없을 때 기본 dry 결과는 inventory 확인이며 apply-ready가 아니다. 보존된 원 실패 job을 reset/requeue/supersede하거나 비용을 지우는 경로로 사용하면 이 판정 범위 밖이다.

## 남은 품질 조건과 인수 결론

`core-quality-review.md`의 반대 근거를 유지한다. 후속 냉장고 보류는 설명서 ID가 들어와도 비교 의미가 틀린 사례를 포함한다. 식기세척기 준비 입력은 제출 원고의 식기 조합별 배치 예시와 맞지 않았으므로 다음 corrected case는 원고에 정렬해야 하며 원 실패는 보존한다. 그 입력 불일치와 별개로 review 누락, desired outcome cardinality, 유용하지 않은 재시도 피드백, held 경로 의미 검사 미호출이 남는다.

검토한 범위는 `approve_scoped_intake`, 차단 finding 0이다. 실제 최신 통합 CI·병합 후 검사·기록 재생 실행과 외부 host 전체 흐름은 담당 PM의 후속 근거이며, 3예시 정상/변경 품질 성공·독립 평가·효과/토큰 개선·31요구 완료를 이 검수로 대신하지 않는다.
