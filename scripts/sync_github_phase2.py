"""Explicitly sync the recorded phase2 task state to its existing GitHub items.

No new task, invitation or inferred completion. Shared Project access is handled
separately; the bootstrap script can be rerun when accepted collaborators change.
"""
from __future__ import annotations

import argparse
import json

from bootstrap_github import OWNER, REPO, ROOT, TEAM, api, gh


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    links = json.loads((ROOT / "harness/phase2/github.json").read_text(encoding="utf-8"))
    tasks = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "harness/phase2/tasks").glob("*.json"))]
    if not args.apply:
        print(json.dumps({"project": links["project"]["url"], "tasks": {t["id"]: t["status"] for t in tasks}}, ensure_ascii=True))
        return
    collaborators = {x["login"] for x in api(f"repos/{REPO}/collaborators?per_page=100")}
    fields = gh("project", "field-list", str(links["project"]["number"]), "--owner", OWNER, "--format", "json")["fields"]
    progress = next(f for f in fields if f["name"] == "진행상태")
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
        option = next(o for o in progress["options"] if o["name"] == mapping[task["status"]])
        gh("project", "item-edit", "--id", item["item_id"], "--project-id", links["project"]["id"],
           "--field-id", progress["id"], "--single-select-option-id", option["id"])
    links["invitation_pending"] = [p for p, (login, _, _) in TEAM.items() if login not in collaborators]
    (ROOT / "harness/phase2/github.json").write_text(json.dumps(links, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"updated_tasks": len(tasks), "pending_members": links["invitation_pending"]}, ensure_ascii=True))


if __name__ == "__main__":
    main()
