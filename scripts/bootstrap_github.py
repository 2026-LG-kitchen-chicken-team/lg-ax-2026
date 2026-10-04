"""Idempotent, user-authorized LG team Issue/Project bootstrap. No credentials stored."""
from __future__ import annotations
import argparse
import json
import pathlib
import subprocess
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = '2026-LG-kitchen-chicken-team/lg-ax-2026'
OWNER = 'jeongiryang'
TITLE = 'LG AX 2026 · 2차 개발'
TEAM = {
    '정이량': ('jeongiryang', 'PM·연결·통합·검수·병합·제출', 'PM'),
    '황대겸': ('unknownamed', '핵심 판단·불편/기능 대조·콘셉트·검사·수정', 'CORE'),
    '신진하': ('ginaginaring', '자료 처리·검색·원문/제품/버전 근거·공개 모델 비교', 'DATA'),
    '최길웅': ('choigilung', '웹 기획 검토 작업실·교정·이력·내보내기', 'WEB'),
}

def gh(*args, data=None):
    command = ['gh', *args]
    if data is not None:
        command += ['--input', '-']
    r = subprocess.run(command, input=json.dumps(data, ensure_ascii=True).encode() if data is not None else None,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT)
    if r.returncode:
        raise RuntimeError(r.stderr.decode('utf-8', 'replace'))
    out = r.stdout.decode('utf-8').strip()
    return json.loads(out) if out else None

def api(path, data=None, method=None):
    args = ['api', path]
    if method:
        args += ['--method', method]
    return gh(*args, data=data)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    opts = parser.parse_args()
    tasks = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((ROOT/'harness/phase2/tasks').glob('*.json'))]
    if not opts.apply:
        print(json.dumps({'repo':REPO,'project':TITLE,'task_count':len(tasks),'team':TEAM},ensure_ascii=False,indent=2))
        return
    existing = api(f'repos/{REPO}/issues?state=all&per_page=100')
    by_title = {x['title']: x for x in existing if 'pull_request' not in x}
    collaborators = {x['login'] for x in api(f'repos/{REPO}/collaborators?per_page=100')}
    label_specs = {'type:governance':'5319e7','type:epic':'0e8a16','type:task':'1d76db',
                   'area:pm':'6f42c1','area:core':'d93f0b','area:data':'0366d6','area:web':'a2eeef',
                   'priority:P0':'b60205','priority:P1':'fbca04','state:ready':'0e8a16'}
    labels = {x['name'] for x in api(f'repos/{REPO}/labels?per_page=100')}
    for name,color in label_specs.items():
        if name not in labels:
            api(f'repos/{REPO}/labels', {'name':name,'color':color}, 'POST')
    def issue(title, body, labels, login=None):
        data = {'title':title,'body':body,'labels':labels}
        if login and login in collaborators:
            data['assignees']=[login]
        if title in by_title:
            # A bootstrap rerun must not erase later work intent, review or evidence.
            item=by_title[title]
            if login and login in collaborators:
                api(f'repos/{REPO}/issues/{item["number"]}/assignees', {'assignees':[login]}, 'POST')
        else:
            item=api(f'repos/{REPO}/issues',data,'POST')
            print(f'Created #{item["number"]}: {title}', flush=True)
        by_title[title]=item
        return item
    requirements=json.loads((ROOT/'harness/phase2/requirements.json').read_text(encoding='utf-8'))['requirements']
    epics={}
    for person,(login,role,area) in TEAM.items():
        owned=[r for r in requirements if r['owner']==person]
        lines=[f'# {person} — {role}', f'책임자: **{person} / @{login}**. PM 검수·병합: **정이량**.',
               '초대 대기 중이어도 본문의 책임자는 확정이다. 수락 후 GitHub assignee를 연결한다.',
               '', '## 책임 범위와 요구사항', *[f'- **{r["id"]}**: {r["commitment"]} → 완료 조건: {r["acceptance"]}' for r in owned],
               '', '## 수행·검수 규칙',
               '- 작업 전 자기 재개 요약과 의존 팀원 근거를 읽는다.',
               f'- docs/작업기록/{person}.md에 실제 지시·AI 해석·수행·실패·검증·다음 행동을 상세히 기록한다.',
               f'- docs/작업근거/{person}.md에 관련 실행 증빙·버전·한계를 기록한다.',
               '- PR에는 실제 실행 방법·입력·결과·계약 영향·근거 ID를 연결한다.',
               '- 개별 검증 후 PM 검수 요청. PM 병합과 병합 후 통합 확인을 거쳐 완료 처리한다.',
               '- 조기 완료/검수 대기 중에는 PM이 지정한 다음 Ready 작업을 이어간다.',
               '- 미구현·모의 입력·실모델·실호스트 검증을 구분한다. 개인정보·비밀키는 게시하지 않는다.']
        epics[person]=issue(f'[담당 Epic] {person} — {role}', '\n'.join(lines), ['type:epic',f'area:{area.lower()}'], login)
    task_issues={}
    for task in tasks:
        person=task['owner']; login,role,area=TEAM[person]
        related=[r for r in requirements if r['id'] in task['requirement_ids']]
        lines=[f'책임자: **{person} / @{login}**',f'담당 Epic: {epics[person]["html_url"]}',
               f'작업 ID: `{task["id"]}` · 초기 기술 상태: `{task["status"]}` · PM: **정이량**',
               '', '## 작업 의도·편집 영역',f'업무: {role}. 허용 편집 영역은 root AGENTS.md/CLAUDE.md의 담당 경계를 따른다.',
               *[f'- {x}' for x in task['actions']], '', '## 입출력·의존성',
               '- 입력: 연결된 요구사항·공통 JSON Schema·버전이 고정된 자료/계약과 PM 작업 패킷.',
               '- 출력: 검토 가능한 코드·재현 입력/명령·결과·실패/미해결·실행 증빙.',
               '의존 작업: '+(', '.join(task['depends_on']) or '없음 — 바로 착수 가능'),
               '', '## 완료 조건',*[f'- [ ] **{r["id"]}** {r["acceptance"]}' for r in related],
               '- [ ] 자기 작업기록·근거·재개 요약 갱신.',
               '- [ ] 실제 검증 근거와 PR 연결, PM 검수·병합 후 통합 확인.',
               '', '## 재개·검수', f'`python scripts/phase2.py packet {task["id"]}`',
               f'다음 대기열: `python scripts/phase2.py next --member {person}`',
               '개별 테스트나 fixture 성공은 참가작 전체 완료가 아니다.']
        task_issues[task['id']]=issue(f'[{task["id"]}] {task["title"]}', '\n'.join(lines),
                                    ['type:task',f'area:{area.lower()}', 'priority:P0' if not task['depends_on'] else 'priority:P1'] + (['state:ready'] if task['status']=='ready' else []),login)
    gov_lines=['# 키친에서치킨먹기 — 팀 역할·작업 규칙·현재 배정',
               '공식 팀장 **황대겸**, 개발 PM **정이량**. 단일 레포에서 네 명이 독립 브랜치로 작업한다.',
               '', '## 담당자와 개발 시작 위치']
    for person,(login,role,area) in TEAM.items():
        gov_lines += [f'### {person} / @{login}',f'{role} — {epics[person]["html_url"]}']
        gov_lines += [f'- {t["id"]}: {task_issues[t["id"]]["html_url"]} ({t["status"]})' for t in tasks if t['owner']==person]
    gov_lines += ['', '## 공통 규칙',
                  '- AGENTS.md와 CLAUDE.md는 같은 전체 내용이다. 종료 전에 바이트 일치를 검사한다.',
                  '- 의도→해석→실제 수행→검증 근거→재개를 팀원별 docs에 기록한다.',
                  '- PM은 검수·추가 배정·병합·통합 확인을 책임진다. 개인 검증과 전체 완료는 다르다.',
                  '- 요구 31개를 Issue·코드·검증·증빙으로 추적한다. 모든 요구는 아직 구현 완료로 간주하지 않는다.',
                  '- 자료·계약 fixture로 독립 개발을 이어가며 실제 모델/호스트 연결과 구분한다.',
                  '- 현재 10/6 컨설팅 일정 확인, 10/20 결과물 제출 준비. 정확한 제출 시각/경로는 후속 확인.',
                  '- 학번·연락처·서명·원본 작성본·비밀키는 private/에만 보관한다.',
                  '', '## 구현 흐름',
                  '요구사항→배정→개발→개별 검증→PM 검수→병합→통합 확인→평가→발표/영상/ZIP→제출 증빙']
    gov=issue('팀 역할·작업 규칙·현재 배정', '\n'.join(gov_lines), ['type:governance','priority:P0'],OWNER)
    api('graphql', {'query':'mutation($id:ID!){pinIssue(input:{issueId:$id}){issue{id number}}}', 'variables':{'id':gov['node_id']}}, 'POST')
    projects=gh('project','list','--owner',OWNER,'--limit','100','--format','json')['projects']
    project=next((x for x in projects if x['title']==TITLE and not x['closed']), None)
    project_created = project is None
    if project_created:
        project=gh('project','create','--owner',OWNER,'--title',TITLE,'--format','json')
    number=str(project['number'])
    gh('project','link',number,'--owner',OWNER,'--repo',REPO)
    fields=gh('project','field-list',number,'--owner',OWNER,'--format','json')['fields']
    specs={'담당자':('TEXT',None),'요구사항':('TEXT',None),'의존 작업':('TEXT',None),'실행 증빙':('TEXT',None),
           '목표일':('DATE',None),'우선순위':('SINGLE_SELECT','P0,P1,P2'),
           '진행상태':('SINGLE_SELECT','Ready,Doing,Individual verified,PM review,PM approved,Merged,Integration verified,Done,Blocked,Deferred')}
    for name,(kind,options) in specs.items():
        if not any(x['name']==name for x in fields):
            args=['project','field-create',number,'--owner',OWNER,'--name',name,'--data-type',kind,'--format','json']
            if options:
                args += ['--single-select-options',options]
            fields.append(gh(*args))
    fieldmap={x['name']:x for x in fields}
    items=[]
    allissues=[gov,*epics.values(),*task_issues.values()]
    for item in allissues:
        projectitem=gh('project','item-add',number,'--owner',OWNER,'--url',item['html_url'],'--format','json')
        task=next((x for x in tasks if task_issues[x['id']]['number']==item['number']),None)
        person=task['owner'] if task else next((p for p,e in epics.items() if e['number']==item['number']),'정이량')
        updates={'담당자':person,'요구사항':', '.join(task['requirement_ids']) if task else '담당 Epic/운영 규칙',
                 '의존 작업':', '.join(task['depends_on']) if task else ''}
        if project_created:
            updates['실행 증빙']='미검증 — 작업기록/PR와 실제 실행 증빙 연결 필요'
        for field,value in updates.items():
            if value:
                gh('project','item-edit','--id',projectitem['id'],'--project-id',project['id'], '--field-id',fieldmap[field]['id'],'--text',value)
        if project_created:
            status = 'Ready' if not task or task['status']=='ready' else 'Deferred'
            for name,option in [('우선순위','P0' if not task or not task['depends_on'] else 'P1'),('진행상태',status)]:
                optionid=next(x['id'] for x in fieldmap[name]['options'] if x['name']==option)
                gh('project','item-edit','--id',projectitem['id'],'--project-id',project['id'],'--field-id',fieldmap[name]['id'],'--single-select-option-id',optionid)
            gh('project','item-edit','--id',projectitem['id'],'--project-id',project['id'],'--field-id',fieldmap['목표일']['id'],'--date','2026-10-06' if task and not task['depends_on'] else '2026-10-20')
        items.append({'issue_url':item['html_url'],'item_id':projectitem['id']})
    links={'repo':REPO,'governance':gov['html_url'],'project':project,'epics':{p:x['html_url'] for p,x in epics.items()},
           'tasks':{p:x['html_url'] for p,x in task_issues.items()},'items':items,'updated_at':'2026-10-04',
           'invitation_pending':[p for p,(login,_,_) in TEAM.items() if login not in collaborators]}
    (ROOT/'harness/phase2/github.json').write_text(json.dumps(links,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'governance':links['governance'],'project':project['url'],'issues':len(allissues)},ensure_ascii=False),flush=True)

if __name__=='__main__':
    main()
