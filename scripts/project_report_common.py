"""Authenticated self-reports are data, never executable instructions or PM approval.

The worker uses an independently deployed, PM-owned policy. No code, workflow,
policy or credentials are downloaded from a teammate branch.
"""
# Linux polling host uses Python 3.10; retain compatible datetime parsing.
# ruff: noqa: UP017, FURB162
from __future__ import annotations

import base64
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from urllib.request import Request

PREFIX = "/lgax-report"
REPORT_STATES = {"doing": "Doing", "blocked": "Blocked", "review_requested": "Review requested"}
FORMAL_STATES = {
    "pending": "Deferred", "ready": "Ready", "doing": "Doing", "blocked": "Blocked",
    "deferred": "Deferred", "individual_verified": "Individual verified",
    "pm_review_requested": "PM review", "pm_approved": "PM approved", "merged": "Merged",
    "integration_verified": "Integration verified", "done": "Done",
}
PM_STATES = {"pm_approved", "merged", "integration_verified", "done"}
REQUIRED = {"task_id", "status", "summary", "next_action", "log_url", "evidence_url"}
OPTIONAL = {"pr_url", "reason"}
REPORT_FIELDS = {"Status", "팀원 보고", "최근 보고", "다음 행동"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def safe_text(value):
    if re.search(r"(?:gh[pousr]_[A-Za-z0-9]{15,}|github_pat_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]{15,}|010[- ]?\d{4}[- ]?\d{4})", value):
        raise ValueError("possible credential/contact in public report; redact before sending")


def parse_report(body):
    if not isinstance(body, str) or not body.startswith(PREFIX):
        return None
    match = re.fullmatch(r"/lgax-report\r?\n```json\r?\n([\s\S]+?)\r?\n```\s*", body)
    if not match or len(body) > 9000:
        raise ValueError("use exactly /lgax-report and one fenced JSON object")
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ValueError("duplicate report key")
            result[k] = v
        return result
    report = json.loads(match[1], object_pairs_hook=unique)
    if not isinstance(report, dict) or not REQUIRED <= report.keys() or report.keys() - REQUIRED - OPTIONAL:
        raise ValueError("missing or unsupported report fields")
    if any(not isinstance(v, str) or not v.strip() or len(v) > 2000 for v in report.values()):
        raise ValueError("all report values must be nonempty strings up to 2000 characters")
    if report["status"] not in REPORT_STATES:
        raise ValueError("self-report allows only doing, blocked, review_requested; Done is PM-only")
    if report["status"] == "blocked" and not report.get("reason"):
        raise ValueError("blocked requires reason and next_action")
    if report["status"] == "review_requested" and not report.get("pr_url"):
        raise ValueError("review_requested requires an open PR")
    safe_text(body)
    for value in report.values():
        safe_text(value)
    return report


def report_body(report):
    body = PREFIX + "\n```json\n" + json.dumps(report, ensure_ascii=False, indent=2) + "\n```"
    parse_report(body)
    return body


def repo_url(url, repo):
    p = urlsplit(url)
    if p.scheme != "https" or p.netloc != "github.com" or p.query or p.username or p.password:
        raise ValueError("only direct HTTPS links to this GitHub repository are allowed")
    path = unquote(p.path)
    if not path.startswith("/" + repo + "/"):
        raise ValueError("link must belong to the configured repository")
    return path[len(repo) + 2:], p.fragment


def source_link(url, repo, name, kind):
    path, _ = repo_url(url, repo)
    m = re.fullmatch(r"blob/([0-9a-f]{40})/(.+)", path)
    expected = f"docs/{'작업기록' if kind == 'log' else '작업근거'}/{name}.md"
    if not m or m[2] != expected:
        raise ValueError(f"{kind} must link to your own {expected} at a full immutable commit")
    return m[1], m[2]


class GitHub:
    """Fixed github.com API only; HTTP tokens stay in a mode-0600 private file."""
    def __init__(self, token=None):
        self.token = token

    def api(self, path, data=None, method=None):
        if not path or path.startswith("/") or ":" in path or ".." in path:
            raise ValueError("invalid API path")
        if self.token is None:
            args = ["gh", "api", path]
            if method:
                args += ["--method", method]
            raw = None
            if data is not None:
                args += ["--input", "-"]
                raw = json.dumps(data, ensure_ascii=True).encode()
            p = subprocess.run(args, input=raw, capture_output=True, check=False)
            if p.returncode:
                raise RuntimeError("GitHub request failed; check login/access, no credentials printed")
            return json.loads(p.stdout) if p.stdout else None
        request = Request("https://api.github.com/" + path,
                          data=json.dumps(data).encode() if data is not None else None,
                          method=method or ("POST" if data is not None else "GET"),
                          headers={"Authorization": "Bearer " + self.token,
                                   "Accept": "application/vnd.github+json",
                                   "Content-Type": "application/json", "User-Agent": "lgax-project-reports"})
        # Do not follow redirects with an Authorization header.
        from urllib.request import HTTPRedirectHandler, build_opener
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        with build_opener(NoRedirect).open(request, timeout=25) as response:
            raw = response.read()
        return json.loads(raw) if raw else None

    def graphql(self, query, variables):
        result = self.api("graphql", {"query": query, "variables": variables}, "POST")
        if result.get("errors"):
            raise RuntimeError("GitHub GraphQL failed; no mutation assumed complete")
        return result["data"]

    def pages(self, path):
        result = []
        for page in range(1, 101):
            rows = self.api(path + ("&" if "?" in path else "?") + f"per_page=100&page={page}")
            result.extend(rows)
            if len(rows) < 100:
                return result
        raise RuntimeError("pagination exceeded; refuse a partial snapshot")


def published_tasks(api, policy):
    """Read JSON at main via the API, without checking out or executing any code."""
    owner, name = policy["repo"].split("/")
    variables = {"owner": owner, "name": name}
    head = api.graphql("query($owner:String!,$name:String!){repository(owner:$owner,name:$name){defaultBranchRef{target{oid}}}}",
                       variables)["repository"]["defaultBranchRef"]["target"]["oid"]
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise ValueError("actual full main commit required")
    aliases = "\n".join(f't{i}:object(expression:"{head}:harness/phase2/tasks/{tid}.json"){{... on Blob{{text}}}}'
                        for i, tid in enumerate(policy["tasks"]))
    query = "query($owner:String!,$name:String!){repository(owner:$owner,name:$name){" + aliases + "}}"
    data = api.graphql(query, variables)["repository"]
    tasks = {}
    for i, (tid, registered) in enumerate(policy["tasks"].items()):
        task = json.loads(data[f"t{i}"]["text"])
        if task["id"] != tid or task["owner"] != registered["name"] or task["status"] not in FORMAL_STATES:
            raise ValueError("published task conflicts with PM-deployed policy; PM must reconcile")
        tasks[tid] = task
    return tasks, head


def project_snapshot(api, policy):
    query = """query($id:ID!){node(id:$id){... on ProjectV2{id url title
      fields(first:100){nodes{... on ProjectV2Field{id name}... on ProjectV2SingleSelectField{id name options{id name}}}}
      items(first:100){pageInfo{hasNextPage} nodes{id content{... on Issue{number url state assignees(first:20){nodes{login}}}}
      fieldValues(first:100){nodes{... on ProjectV2ItemFieldTextValue{text field{... on ProjectV2Field{name}}}
      ... on ProjectV2ItemFieldSingleSelectValue{name field{... on ProjectV2SingleSelectField{name}}}}}}}}}}"""
    data = api.graphql(query, {"id": policy["project_id"]})["node"]
    if not data or data["items"]["pageInfo"]["hasNextPage"]:
        raise ValueError("missing project or more than 100 items; refuse incomplete snapshot")
    fields = {f["name"]: f for f in data["fields"]["nodes"] if f}
    items = {}
    for item in data["items"]["nodes"]:
        content = item.get("content") or {}
        if not content.get("number") or content["url"].split("/issues/")[0] != "https://github.com/" + policy["repo"]:
            continue
        values = {v["field"]["name"]: v.get("text", v.get("name")) for v in item["fieldValues"]["nodes"] if v}
        items[content["number"]] = {"id": item["id"], "values": values, "issue": content}
    return {"fields": fields, "items": items, "url": data["url"], "at": now()}


def validate_submission(api, policy, comment, tasks):
    report = parse_report(comment["body"])
    if report is None:
        return None
    registered = policy["tasks"].get(report["task_id"])
    actor = comment["user"]["login"]
    if not registered or actor != registered["account"]:
        raise ValueError("only the registered task owner may report this task")
    issue_number = int(comment["issue_url"].rsplit("/", 1)[-1])
    if comment["issue_url"] != f"https://api.github.com/repos/{policy['repo']}/issues/{registered['issue_number']}":
        raise ValueError("report must be posted to its registered task Issue")
    if comment["created_at"] != comment["updated_at"]:
        raise ValueError("edited report commands are not accepted; post a new report")
    issue = api.api(f"repos/{policy['repo']}/issues/{issue_number}")
    if issue["state"] != "open" or "pull_request" in issue or actor not in {a["login"] for a in issue["assignees"]}:
        raise ValueError("open assigned task Issue required")
    task = tasks[report["task_id"]]
    if task["status"] in PM_STATES:
        raise ValueError("PM-approved/merged/completed task cannot be overwritten; request a follow-up Issue")
    if task.get("scope") == "proposed_extension" and not task.get("adoption"):
        raise ValueError("extension not adopted by PM")
    dependencies = [d for d in task["depends_on"] if tasks[d]["status"] != "done"]
    # A partial implementation/PR may proceed while integration dependencies wait.
    # This reports progress, never verifies completion or unlocks dependent tasks.
    versions = {}
    for key, kind in (("log_url", "log"), ("evidence_url", "evidence")):
        commit, path = source_link(report[key], policy["repo"], registered["name"], kind)
        file = api.api(f"repos/{policy['repo']}/contents/{quote(path, safe='/')}?ref={commit}")
        if file.get("type") != "file" or not file.get("sha"):
            raise ValueError("published log/evidence file required")
        text = base64.b64decode(file["content"]).decode("utf-8")
        if not text.strip():
            raise ValueError("log/evidence cannot be empty")
        versions[key] = {"commit": commit, "path": path, "git_blob": file["sha"], "sha256": digest(text)}
    if versions["log_url"]["commit"] != versions["evidence_url"]["commit"]:
        raise ValueError("log and evidence must use the same commit")
    if report.get("pr_url"):
        tail, fragment = repo_url(report["pr_url"], policy["repo"])
        if not re.fullmatch(r"pull/[1-9]\d*", tail) or fragment:
            raise ValueError("direct PR URL required")
        pr = api.api(f"repos/{policy['repo']}/pulls/{tail.split('/')[1]}")
        if pr["user"]["login"] != actor or pr["head"]["repo"]["full_name"] != policy["repo"]:
            raise ValueError("PR must belong to the reporting owner and this repository")
        if report["status"] == "review_requested" and (
            pr["state"] != "open" or pr["draft"] or pr["base"]["ref"] != "main" or
            pr["head"]["sha"] != versions["log_url"]["commit"]
        ):
            raise ValueError("review requires a non-draft open PR to main, with logs at exact PR head")
    return {"report": report, "actor": actor, "comment_id": comment["id"], "url": comment["html_url"],
            "at": comment["created_at"], "body_sha256": digest(comment["body"]), "versions": versions,
            "waiting_for": dependencies,
            "meaning": "authenticated self-report; execution/PM approval/merge not independently verified"}


def latest_is_current(task, accepted):
    if not accepted or task["status"] in PM_STATES:
        return False
    # A later formal harness update supersedes this report; never replay a stale request.
    stamp = datetime.fromisoformat(accepted["at"].replace("Z", "+00:00"))
    return not any(datetime.fromisoformat(row["at"].replace("Z", "+00:00")) > stamp
                   for row in task.get("history", []))


def projection(task, accepted):
    active = latest_is_current(task, accepted)
    formal = task["status"]
    default = "Done" if formal == "done" else "Todo" if formal in {"pending", "ready", "deferred"} else "In Progress"
    values = {"Status": default}
    if accepted:
        report = accepted["report"]
        if active:
            values["Status"] = "In Progress"
        # The report columns retain historical provenance; formal status always wins.
        values.update({"팀원 보고": REPORT_STATES[report["status"]],
                       "최근 보고": f"{accepted['url']}\n@{accepted['actor']} · {accepted['at']}\n"
                                    f"{'현재 자기보고' if active else '이후 하네스 갱신으로 역사 보고'}: {report['summary']}",
                       "다음 행동": report["next_action"] if active else "하네스/PM 최신 지시를 확인 (이전 보고는 역사)"})
    return values


def update_fields(api, policy, snapshot, item, values):
    if values.keys() - REPORT_FIELDS:
        raise ValueError("worker may update only Status and its three report fields")
    updated = []
    for name, value in values.items():
        if item["values"].get(name) == value:
            continue
        field = snapshot["fields"][name]
        payload = {"text": value}
        if "options" in field:
            payload = {"singleSelectOptionId": next(o["id"] for o in field["options"] if o["name"] == value)}
        query = """mutation($project:ID!,$item:ID!,$field:ID!,$value:ProjectV2FieldValue!){
          updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,fieldId:$field,value:$value}){projectV2Item{id}}}"""
        api.graphql(query, {"project": policy["project_id"], "item": item["id"], "field": field["id"], "value": payload})
        updated.append(name)
    return updated


def load_policy(path):
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if policy["repo"] != "2026-LG-kitchen-chicken-team/lg-ax-2026" or not policy["tasks"]:
        raise ValueError("wrong or empty policy")
    if any(not re.fullmatch(r"P2-[A-Z]+-\d{3}", tid) for tid in policy["tasks"]):
        raise ValueError("invalid policy task ID")
    return policy
