import copy
import json
from pathlib import Path
import tempfile
import unittest
from scripts.ax_workflow import ROOT, CONFIG, packet, finish, completed
from scripts.flow_audit import audit, trace


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        (self.root/"harness").mkdir()
        (self.root/CONFIG).write_bytes((ROOT/CONFIG).read_bytes())
        self.config=json.loads((self.root/CONFIG).read_text(encoding="utf-8"))
        self.state={"request":"test goal","completed":{}}
        (self.root/"evidence.md").write_text("observed result",encoding="utf-8")

    def artifact(self, sid):
        stage=next(s for s in self.config["stages"] if s["id"]==sid)
        data={"stage":sid,"content":{f:["observed"] for f in stage["fields"]},
              "evidence_paths":["evidence.md"],"review":{"by":"test","limitations":["fixture"]}}
        if sid=="research":
            data["content"]["sources"]=[{"id":str(i),"url":"https://example.com/"+str(i),
                "supports":"test evidence","limitations":"fixture"} for i in range(4)]
        path=f"{sid}.json"
        (self.root/path).write_text(json.dumps(data),encoding="utf-8")
        return path

    def test_cannot_skip_discovery_to_selection(self):
        with self.assertRaises(ValueError):
            packet(self.root,self.config,self.state,"select")

    def test_finish_advances_to_real_next_packet(self):
        finish(self.root,self.config,self.state,"brief",self.artifact("brief"))
        result=packet(self.root,self.config,self.state)
        self.assertEqual(result["stage"],"research")
        self.assertTrue(result["actions"])
        self.assertEqual(result["inputs"][0]["path"],"brief.json")

    def test_source_change_invalidates_descendants(self):
        for sid in ("brief","research"):
            finish(self.root,self.config,self.state,sid,self.artifact(sid))
        (self.root/"evidence.md").write_text("changed evidence",encoding="utf-8")
        self.assertEqual(completed(self.root,self.config,self.state),set())

    def test_revised_brief_reopens_research(self):
        for sid in ("brief","research"):
            finish(self.root,self.config,self.state,sid,self.artifact(sid))
        finish(self.root,self.config,self.state,"brief",self.artifact("brief"))
        self.assertNotIn("research",self.state["completed"])

    def test_placeholder_is_not_completion(self):
        path=self.artifact("brief")
        content=json.loads((self.root/path).read_text())
        content["content"]["objective"]="REPLACE_WITH_ACTUAL_RESULT"
        (self.root/path).write_text(json.dumps(content))
        with self.assertRaises(ValueError):
            finish(self.root,self.config,self.state,"brief",path)

    def test_new_user_goal_invalidates_old_decision_chain(self):
        finish(self.root,self.config,self.state,"brief",self.artifact("brief"))
        self.state["request"]="different goal"
        self.assertEqual(completed(self.root,self.config,self.state),set())

    def test_external_evidence_cannot_complete_stage(self):
        path=self.artifact("brief")
        content=json.loads((self.root/path).read_text())
        content["evidence_paths"]=["../outside.md"]
        (self.root/path).write_text(json.dumps(content))
        with self.assertRaises(ValueError):
            finish(self.root,self.config,self.state,"brief",path)


class FlowChecks(unittest.TestCase):
    def setUp(self):
        data=json.loads((ROOT/"research/atoz/flow_trials.json").read_text(encoding="utf-8"))
        self.flow=copy.deepcopy(data["cases"][0]["after"])

    def test_offline_does_not_mean_success(self):
        self.assertEqual(trace(self.flow,["confirmed","offline"])["status"],"pending")

    def test_missing_failure_branch_is_detected(self):
        del self.flow["nodes"][1]["on"]["offline"]
        self.assertIn("request:offline:missing_branch",audit(self.flow,{"S17"}))

    def test_unknown_evidence_is_detected(self):
        self.flow["nodes"][1]["sources"]=["invented"]
        self.assertIn("request:unknown_source",audit(self.flow,{"S17"}))

    def test_unsupported_event_stays_unhandled(self):
        self.assertEqual(trace(self.flow,["automatic_heat"])["status"],"unhandled_event")


if __name__=="__main__":
    unittest.main()
