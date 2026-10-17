"""Synthetic native records only; no model, user log, or product DB."""
import json
from pathlib import Path
import tempfile
import unittest
from backend.release_activity import project_activity, native_activity, SKILLS

SESSION='11111111-1111-1111-1111-111111111111'
TURN='22222222-2222-2222-2222-222222222222'
TS='2026-10-16T05:10:00Z'
def row(kind,payload):return {'type':kind,'timestamp':TS,'payload':payload}
def base(workspace='/example/product',turn=TURN):
    return [row('session_meta',{'id':SESSION,'cwd':str(workspace)}),row('event_msg',{'type':'task_started','turn_id':turn})]
def report(text):return row('response_item',{'type':'message','role':'assistant','phase':'commentary','content':[{'text':text}]})
def command(text,output,exit_code=0):return row('event_msg',{'type':'item_completed','item':{'id':'command-1','type':'CommandExecution','status':'completed','exit_code':exit_code,'command':text,'aggregated_output':output}})

class ActivityTests(unittest.TestCase):
    def project(self,rows):return project_activity(rows,Path('/example/product'),SESSION,TURN)
    def test_native_task_start_is_working_without_fabricating_a_skill(self):
        data=self.project(base()+[report('설치 지침과 6개 Skill 및 실행 준비를 확인하겠습니다.')])
        self.assertEqual(data['state'],'working');self.assertEqual(data['intent'],'readiness')
        self.assertIsNone(data['reported_stage']);self.assertEqual(data['command_count'],0)
    def test_variable_path_read_uses_completed_command_frontmatter(self):
        output='\n'.join('---\nname: '+s+'\n---' for s in SKILLS)
        data=self.project(base()+[command('foreach($n in $names){Get-Content (Join-Path .agents/skills "$n/SKILL.md")}',output)])
        self.assertEqual({r['id'] for r in data['skill_reads']},set(SKILLS))
        self.assertNotIn('operations',data);self.assertIsNone(data['reported_stage'])
    def test_failed_read_never_becomes_loaded(self):
        self.assertEqual(self.project(base()+[command('Get-Content SKILL.md','name: evidence-retrieval',1)])['skill_reads'],[])
    def test_installed_does_not_mean_read(self):
        output=json.dumps({'installed_skills':list(SKILLS),'errors':[],'common_tool_exit_code':0})
        data=self.project(base()+[command('uv run python product-doctor.py',output)])
        self.assertEqual(len(data['installed_skills']),6);self.assertEqual(data['skill_reads'],[])
    def test_ready_results_and_completion_are_from_native_output(self):
        data=self.project(base()+[command('uv run python product-doctor.py',json.dumps({'installed_skills':list(SKILLS),'errors':[],'common_tool_exit_code':0})),command('python storage-probe.py',json.dumps({'file_read_write':True,'sqlite_disk_commit_read':True})),row('event_msg',{'type':'task_complete','turn_id':TURN})])
        self.assertEqual(data['checks'],{'installation':True,'file':True,'sqlite':True});self.assertEqual(data['state'],'finished')
    def test_other_turn_completion_is_ignored(self):
        self.assertEqual(self.project(base()+[row('event_msg',{'type':'task_complete','turn_id':'other'})])['state'],'working')
    def test_new_turn_does_not_reuse_previous_checks(self):
        rows=base()+[command('python x',json.dumps({'file_read_write':True})),row('event_msg',{'type':'task_started','turn_id':'other'})]
        self.assertIsNone(self.project(rows))
    def test_reasoning_and_raw_secrets_never_reach_output(self):
        secret='PRIVATE_KEY_AND_PROMPT'
        rows=base()+[row('response_item',{'type':'reasoning','text':secret+' 기능 대조를 진행하겠습니다'}),row('response_item',{'type':'message','role':'assistant','phase':'commentary','channel':'analysis','content':[{'text':secret}]}),command('python '+secret,json.dumps({'unknown':secret}))]
        out=self.project(rows);self.assertNotIn(secret,json.dumps(out));self.assertIsNone(out['reported_stage'])
    def test_public_stage_report_is_distinguished_from_skill_call(self):
        data=self.project(base()+[report('기능 대조를 진행하겠습니다.')])
        self.assertEqual(data['reported_stage'],'compare');self.assertEqual(data['intent'],'planning');self.assertEqual(data['command_count'],0)
    def test_wrong_workspace_or_session_fails_closed(self):
        self.assertIsNone(project_activity(base(),Path('/other'),SESSION,TURN))
        self.assertIsNone(project_activity(base(),Path('/example/product'),'other',TURN))
    def test_scoped_file_and_incomplete_last_line(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);workspace=root/'product';sessions=root/'sessions';out=workspace/'runtime-data/agent-office';out.mkdir(parents=True)
            name=f'rollout-2026-10-16T14-00-00-{SESSION}.jsonl'
            folder=sessions/'2026/10/16';folder.mkdir(parents=True)
            (out/'codex-follow.json').write_text(json.dumps({'sessions':{SESSION:{'threads':{name:{'id':SESSION}}}}}))
            target=folder/name;target.write_text('\n'.join(json.dumps(r) for r in base(workspace))+'\n'+ '{"type":"event_msg"',encoding='utf-8')
            self.assertEqual(native_activity(workspace,sessions,SESSION,TURN)['state'],'working')
            target.write_text('\n'.join(json.dumps(r) for r in base('/other'))+'\n',encoding='utf-8')
            self.assertIsNone(native_activity(workspace,sessions,SESSION,TURN))

if __name__=='__main__':unittest.main()
