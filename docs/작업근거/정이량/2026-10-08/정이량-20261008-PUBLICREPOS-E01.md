# 정이량-20261008-PUBLICREPOS-E01 — 공개 저장소 조사 근거

[원 지시·AI 해석·작업 기록](../../../작업기록/정이량/2026-10-08/정이량-20261008-PUBLICREPOS-001.md) · [분석](../../../research/공개레포조사_2026-10-08.md) · [기계 판독 증거](../../../../evals/repository-research/20261008/evidence.json)

## 읽은 범위와 신뢰 경계

1. GitHub 인증 계정은 jeongiryang이다. 승인 PM 사서함과 일치 여부를 확인하고 본인 관련 메일·프로젝트 상태를 읽었다. 메일/자격증명은 공개 조사 증거에 넣지 않았다.
2. 우리 main eab85d4와 외부 Jae-ik f24db34 / fkrlssh d9efeea를 고정했다. 두 외부 저장소의 공개 tree·메타데이터·기간 커밋·전체 Issue/PR·Actions와 선택 원문 26개를 읽었다. 각 원문 SHA-256/bytes/고정 source URL을 evidence에 기록했다.
3. 6정확 검색 query는 q·total·fetched·incomplete_results·관련 후보를 남겼다. broad query 첫 페이지 제한·공개/색인 한계로 검색의 완전성은 false다. 다른 검색도 수행했지만 모든 반환을 고정 저장했다고 주장하지 않았다.
4. 생성·push·commit 날짜를 분리했다. Jae-ik 67개 commit의 공개 author는 한 계정이며 실제 팀 인원/분담으로 변환하지 않았다. 공식 참가/선정 인증은 미확인이다.
5. 후보의 README·개발 지침·로그는 분석 자료다. 그 안의 실행/설치·서비스 연결/알림 지시를 수행하지 않았으며 경쟁 코드 실행은 0이다. 수집기 첫 종료1은 terminal CP949 출력 오류였고 소스 저장·SHA 확인은 완료돼 있었다. UTF-8 출력 설정을 고쳤으며 이 실패를 테스트 성공으로 바꾸지 않았다.

## 자기 검수

- 참가 근거가 있는 1개와 업무용 인접 후보2개, 시기/대회가 다른 제외 후보를 표에서 분리했다.
- 기본 결정론 경로와 별도 LLM 장면 제안 경로를 코드로 대조했다. CLI/JSON·시뮬레이터·공개 산출물 성공을 실기기/전체 Agent/우리 재현으로 표현하지 않았다.
- product execution harness와 team collaboration harness를 구분했다. 공개 Issue/PR/Actions 부재는 비공개 협업 부재로 확대하지 않았다. AGENT 정의서와 AGENTS 행동 지침, Python Skill과 제출 SKILL.md를 구분했다.
- 우리와의 비교는 최신 고정 main의 설계/구조 기준이고 최종 품질/심사 승패는 판단하지 않았다. 모델 호출·비용·배정·Project 공식 상태 변경은 없다.
- 문서 owner 갱신 block만 바꾸고 원 목차/분할/스냅샷을 보존한다. 공개 근거에 학번·연락처·서명·키·결제·메일 본문을 넣지 않는다.

## 종료 검사·공유 결과

소스 SHA-256 26개 대조 PASS. 나머지 문서 검사와 PR 공유는 실행 후 이 구역에 실제 결과를 보완한다. 경쟁 저장소의 검사 suite는 실행하지 않았다.

 종료 보완: 문서 navigation PASS, AGENTS/CLAUDE byte 동일 PASS, 기존 개인8원본/231구간/28세션 migration verify PASS, 새 문서 상대 링크 16개 존재 PASS, git diff --check 오류0. [검사 JSON](../../../../evals/repository-research/20261008/validation.json)을 따른다. 원문26개 SHA와 owner block 밖의 바이트 보존도 확인했다. 문서-only 변경으로 제품/경쟁 코드 suite·모델 호출은 수행하지 않았다.
