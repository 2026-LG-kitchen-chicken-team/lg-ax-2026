"""Explicitly sync the recorded phase2 task state to its existing GitHub items.

No new task, invitation or inferred completion. Shared Project access is handled
separately; the bootstrap script can be rerun when accepted collaborators change.
"""
from __future__ import annotations

import argparse
import json
import subprocess

from bootstrap_github import OWNER, REPO, ROOT, TEAM, api, gh
from phase2 import load, ready_tasks, validate
from project_report_common import GitHub, load_policy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    links = json.loads((ROOT / "harness/phase2/github.json").read_text(encoding="utf-8"))
    tasks = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "harness/phase2/tasks").glob("*.json"))]
    eligible = {t['id'] for t in ready_tasks(load(ROOT))}
    if not args.apply:
        print(json.dumps({"project": links["project"]["url"], "tasks": {t["id"]: t["status"] for t in tasks}}, ensure_ascii=True))
        return
    if api('user')['login'] != OWNER:
        raise ValueError('authenticated PM account required for Project/approval sync')
    main_commit = api(f'repos/{REPO}/branches/main')['commit']['sha']
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, check=True).stdout.decode().strip()
    dirty_tasks = subprocess.run(['git', 'status', '--porcelain', '--', 'harness/phase2/tasks'],
                                 cwd=ROOT, capture_output=True, check=True).stdout
    if head != main_commit or dirty_tasks or validate(ROOT, load(ROOT)):
        raise ValueError('publish and verify exact main task/evidence records before PM-authorized sync')
    collaborators = {x["login"] for x in api(f"repos/{REPO}/collaborators?per_page=100")}
    fields = gh("project", "field-list", str(links["project"]["number"]), "--owner", OWNER, "--format", "json")["fields"]
    progress = next(f for f in fields if f["name"] == "진행상태")
    default_status = next(f for f in fields if f["name"] == "Status")
    evidence_field = next(f for f in fields if f["name"] == "실행 증빙")
    # Deferred in the UI means waiting for the declared dependencies or a PM assignment.
    mapping = {"pending": "Deferred", "ready": "Ready", "doing": "Doing", "blocked": "Blocked", "deferred": "Deferred",
               "individual_verified": "Individual verified", "pm_review_requested": "PM review", "pm_approved": "PM approved",
               "merged": "Merged", "integration_verified": "Integration verified", "done": "Done"}
    for task in tasks:
        url = links["tasks"][task["id"]]
        login = TEAM[task["owner"]][0]
        if login in collaborators:
            api(f"repos/{REPO}/issues/{url.rsplit('/', 1)[1]}/assignees", {"assignees": [login]}, "POST")
        item = next(x for x in links["items"] if x["issue_url"] == url)
        state = 'Ready' if task['status'] in ('pending', 'ready') and task['id'] in eligible else mapping[task['status']]
        option = next(o for o in progress["options"] if o["name"] == state)
        gh("project", "item-edit", "--id", item["item_id"], "--project-id", links["project"]["id"],
           "--field-id", progress["id"], "--single-select-option-id", option["id"])
        # Once report fields exist, the PM-owned report service derives Status from
        # formal main state + authenticated reports. Do not overwrite live reports.
        if not any(f['name'] == '팀원 보고' for f in fields):
            board_state = 'done' if state == 'Done' else 'todo' if state in ('Ready', 'Deferred') else 'inprogress'
            board_option = next(o for o in default_status['options'] if o['name'].lower().replace(' ', '') == board_state)
            gh('project', 'item-edit', '--id', item['item_id'], '--project-id', links['project']['id'],
               '--field-id', default_status['id'], '--single-select-option-id', board_option['id'])
        recorded = [f'{key}: {task[key]["path"]}' for key in ('individual_evidence', 'pm_review', 'integration', 'completion') if task.get(key)]
        if task.get('merge'):
            merge = json.loads((ROOT / task['merge']['path']).read_text(encoding='utf-8'))
            recorded.append(merge['pull_request_url'])
        if recorded:
            gh('project', 'item-edit', '--id', item['item_id'], '--project-id', links['project']['id'],
               '--field-id', evidence_field['id'], '--text', '\n'.join(recorded))
    links["invitation_pending"] = [p for p, (login, _, _) in TEAM.items() if login not in collaborators]
    (ROOT / "harness/phase2/github.json").write_text(json.dumps(links, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    policy_path = ROOT / 'harness/phase2/project-reports.policy.json'
    if policy_path.exists():
        policy = load_policy(policy_path)
        body = '/lgax-sync\n```json\n' + json.dumps({'commit': main_commit}) + '\n```'
        path = f'repos/{REPO}/issues/{policy["governance_issue_number"]}/comments'
        comments = GitHub().pages(path)
        if not any(c['user']['login'] == OWNER and c['body'] == body and
                   c['created_at'] >= policy['accept_reports_after'] for c in comments):
            api(path, {'body': body}, 'POST')
    print(json.dumps({"updated_tasks": len(tasks), "pending_members": links["invitation_pending"]}, ensure_ascii=True))


if __name__ == "__main__":
    main()
