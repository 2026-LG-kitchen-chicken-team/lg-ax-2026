"""Fixed PM metadata publication. Never execute checkout code on the host.

A candidate is not Done. This broker exports its immutable evidence, creates a
metadata-only PR, requires an isolated offline validation and exact-head CI,
then obtains both actual Project and controller acknowledgments. Every remote
effect is durably reserved; a lost response is observed, never blindly retried.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path

from services.automation.artifacts import secret_check
from services.automation.completion import (
    DIGEST,
    ID,
    MEMBERS,
    PM,
    REPO,
    SHA,
    ArtifactRef,
    CompletionError,
    digest,
)
from services.automation.isolation import regular_file
from services.automation.pm import Journal, PMError, canonical, fingerprint, protected_path
from services.automation.worker import exclusive_lock, write_json

PROTOCOL = "trusted_auto_parent_v1"
MAX_FILE = 2 * 1024 * 1024
MAX_TOTAL = 16 * 1024 * 1024
MAX_FILES = 256
PREFIX = "evals/automation-completion/"


def _require(value, reason):
    if not value:
        raise CompletionError(reason)


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "duplicate publication JSON field")
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(CompletionError("nonfinite publication JSON")))
    _require(isinstance(value, dict), "publication JSON must be an object")
    return value


class CompletionPublisher:
    """Callable reviewed host adapter: (contract, candidate, store)->Publication|None.

    Instantiate only from fixed broker wiring. Paths, validators, GitHub targets
    and commands cannot be selected by model decisions or repository content.
    The caller holds the PM loop lock; this additional OS lock serializes manual
    and scheduled publication against the same private registry.
    """

    def __init__(self, broker):
        self.broker = broker
        self.root = protected_path(broker.state_dir / "completion-publication" / "state.json").parent
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "state.json"
        self.journal = Journal(broker.config["journal_file"], broker.config["policy_sha256"])
        self.state = _json(regular_file(self.path)) if self.path.exists() else {"schema_version": 1, "publications": {}}
        _require(self.state.get("schema_version") == 1, "invalid publication state")

    def _save(self):
        write_json(self.path, self.state)

    def _git(self, argv, *, data=None, index=None):
        # Git object plumbing does not checkout/import repository code. Hooks,
        # global includes, textconv, file/ext protocols and signing are disabled.
        env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
               "GIT_TERMINAL_PROMPT": "0", "GIT_AUTHOR_NAME": PM, "GIT_COMMITTER_NAME": PM,
               "GIT_AUTHOR_EMAIL": PM + "@users.noreply.github.com",
               "GIT_COMMITTER_EMAIL": PM + "@users.noreply.github.com"}
        if index is not None:
            env["GIT_INDEX_FILE"] = str(index)
        args = ["git", "-c", "core.hooksPath=" + str(self.root / "empty-hooks"),
                "-c", "core.fsmonitor=false", "-c", "commit.gpgsign=false",
                "-c", "protocol.ext.allow=never", "-c", "protocol.file.allow=never",
                "-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential", *argv]
        try:
            row = subprocess.run(args, cwd=self.broker.repository, env=env, input=data,
                                 capture_output=True, timeout=120, check=False,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        except (OSError, subprocess.TimeoutExpired):
            raise PMError("fixed metadata Git operation unavailable; reconcile before retry") from None
        if row.returncode or len(row.stdout) > MAX_TOTAL:
            raise PMError("fixed metadata Git operation refused; no output body logged")
        return row.stdout

    def _origin(self):
        origin = self._git(["remote", "get-url", "origin"]).decode().strip()
        _require(origin in {f"https://github.com/{REPO}", f"https://github.com/{REPO}.git"},
                 "publication clone must have the fixed GitHub origin")

    def _main(self):
        value = self.broker.github.request("GET", f"repos/{REPO}/commits/main").get("sha")
        _require(isinstance(value, str) and SHA.fullmatch(value), "actual fixed main unavailable")
        return value

    def _authority(self, expected_main):
        self.broker.authenticate()
        _require(self.broker.enabled() and self.broker.policy.get("allow_auto_merge") is True,
                 "PM publication disabled or automatic merge delegation absent")
        _require(self._main() == expected_main, "main raced; require fresh independent parent collection")

    def _reserve(self, entry, operation, task):
        """One remote intent, charged to the existing immutable PM journal."""
        _require(operation not in entry.setdefault("operations", {}), "unknown operation cannot be repeated")
        day = "day:" + time.strftime("%Y-%m-%d", time.gmtime())
        scope = "task:" + task
        action_id = "publication-" + fingerprint({"candidate": entry["candidate"], "operation": operation})
        with self.journal.connect() as db:
            daily = self.journal.budget(db, day)
            logical = self.journal.budget(db, scope)
            limits = self.broker.policy["limits"]
            _require(daily["actions"] < min(100, limits["max_actions_per_day"]) and
                     logical["actions"] < min(20, limits["max_actions_per_task"]), "publication action budget exhausted")
            _require(db.execute("SELECT 1 FROM actions WHERE action_id=?", (action_id,)).fetchone() is None,
                     "publication intent already recorded; no replay")
            body = {"task_id": task, "candidate_sha256": entry["candidate"], "operation": operation}
            db.execute("INSERT INTO actions VALUES(?,?,?,?,?,?)",
                       (action_id, task, "parent_publication", "intent", canonical(body), None))
            for budget_scope in (day, scope):
                db.execute("UPDATE budgets SET actions=actions+1 WHERE scope=?", (budget_scope,))
            self.journal.append(db, "parent_publication_intent", {"action_id": action_id, **body})
        entry["operations"][operation] = {"state": "unknown", "action_id": action_id}
        self._save()

    def _confirmed(self, entry, operation, detail):
        old = entry["operations"][operation]
        old.update(state="confirmed", detail=detail)
        with self.journal.connect() as db:
            db.execute("UPDATE actions SET state='applied',receipt=? WHERE action_id=?",
                       (canonical(detail), old["action_id"]))
            self.journal.append(db, "parent_publication_confirmed", {"action_id": old["action_id"], **detail})
        self._save()

    def _export(self, contract, candidate, store):
        from services.automation.completion import validate_completion_bundle

        _require(ID.fullmatch(contract.task_id) and DIGEST.fullmatch(candidate.sha256) and
                 digest(candidate.raw) == candidate.sha256, "invalid fixed candidate identity")
        bundle = _json(regular_file(store.root / "bundles" / (candidate.sha256 + ".json"), maximum=MAX_FILE))
        _require(bundle.get("protocol") == PROTOCOL and bundle.get("tested_commit") == candidate.payload["tested_commit"],
                 "protected bundle candidate/source mismatch")
        validated = validate_completion_bundle(bundle, store.read, expected_task_id=contract.task_id,
                                               expected_receipt_sha256=candidate.sha256)
        _require(validated.raw == candidate.raw and candidate.payload.get("contract_fingerprint") == contract.fingerprint,
                 "candidate differs from independently collected contract")
        artifacts = bundle.get("artifacts")
        _require(isinstance(artifacts, list) and 0 < len(artifacts) <= MAX_FILES, "complete bounded artifact closure required")
        prefix = PREFIX + contract.task_id + "/" + candidate.sha256 + "/"
        files, asset_map, identities = {}, {}, set()
        for value in artifacts:
            ref = ArtifactRef.parse(value)
            identity = (ref.commit, ref.path)
            _require(identity not in identities, "duplicate artifact logical identity")
            identities.add(identity)
            raw = store.read(ref)
            _require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_FILE and digest(raw) == ref.sha256,
                     "bounded exact artifact bytes required")
            secret_check(raw, [])
            path = prefix + "assets/" + ref.sha256 + ".blob"
            _require(path not in files or files[path] == raw, "conflicting artifact bytes")
            files[path] = raw
            asset_map[ref.sha256] = path
        bundle["artifact_files"] = asset_map
        bundle_path = prefix + "bundle.json"
        files[bundle_path] = canonical(bundle).encode() + b"\n"
        _require(len(files[bundle_path]) <= MAX_FILE, "exported bundle exceeds per-file bounds")
        secret_check(files[bundle_path], [])
        _require(sum(map(len, files.values())) <= MAX_TOTAL, "publication export exceeds total bounds")
        return files, {"path": bundle_path, "sha256": digest(files[bundle_path]),
                       "parent_receipt_sha256": candidate.sha256}

    def _read_blob(self, commit, path):
        ref = ArtifactRef(path, "0" * 64, commit)
        raw = self._git(["ls-tree", "-z", commit, "--", ":(literal)" + ref.path])
        _require(raw.endswith(b"\0") and raw.count(b"\0") == 1, "exact ordinary metadata file required")
        metadata, name = raw[:-1].split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        _require(mode == "100644" and kind == "blob" and name.decode() == path and SHA.fullmatch(oid),
                 "metadata source must be an ordinary non-executable blob")
        result = self._git(["cat-file", "blob", oid])
        _require(0 < len(result) <= MAX_FILE, "metadata blob exceeds per-file bounds")
        _require(hashlib.sha1(b"blob " + str(len(result)).encode() + b"\0" + result).hexdigest() == oid,
                 "Git metadata blob identity mismatch")
        return result

    def _prepare(self, contract, candidate, entry, files, completion):
        main = candidate.payload["tested_commit"]
        self._origin()
        self._git(["fetch", "--no-tags", "origin", main])
        task_path = f"harness/phase2/tasks/{contract.task_id}.json"
        old = _json(self._read_blob(main, task_path))
        _require(old.get("id") == contract.task_id and MEMBERS.get(old.get("owner")) == contract.owner and
                 old.get("scope") == "required" and old.get("status") != "done" and
                 set(old.get("requirement_ids", [])) == set(dict(contract.requirements)),
                 "current formal task differs from accepted contract")
        new = {**old, "status": "done", "completion_protocol": PROTOCOL, "completion": completion}
        files[task_path] = canonical(new).encode() + b"\n"
        for path in files:
            if path != task_path:
                _require(not self._git(["ls-tree", "-z", main, "--", ":(literal)" + path]),
                         "immutable publication artifact already exists")
        index = self.root / ("index-" + uuid.uuid4().hex)
        try:
            self._git(["read-tree", main], index=index)
            for path, raw in sorted(files.items()):
                oid = self._git(["hash-object", "-w", "--stdin"], data=raw).decode().strip()
                _require(SHA.fullmatch(oid), "metadata object write failed")
                self._git(["update-index", "--add", "--cacheinfo", "100644," + oid + "," + path], index=index)
            tree = self._git(["write-tree"], index=index).decode().strip()
            commit = self._git(["commit-tree", tree, "-p", main, "-m",
                                "PM parent completion " + contract.task_id + " " + candidate.sha256]).decode().strip()
        finally:
            if index.exists():
                index.unlink()
        _require(SHA.fullmatch(commit), "fixed metadata commit unavailable")
        entry.update(head=commit, tree=tree, files={p: digest(raw) for p, raw in files.items()},
                     completion=completion, branch="codex/auto-parent-" + contract.task_id.lower() + "-" + candidate.sha256[:20])
        self._save()
        self._verify_metadata(entry)

    def _verify_metadata(self, entry):
        raw = self._git(["diff", "--raw", "-z", "--no-ext-diff", "--no-textconv", "--no-renames", "--abbrev=40",
                         entry["base"], entry["head"], "--"])
        fields = raw.split(b"\0")
        _require(fields[-1] == b"" and (len(fields) - 1) % 2 == 0, "complete metadata change list required")
        actual = {}
        task = f"harness/phase2/tasks/{entry['task_id']}.json"
        for index in range(0, len(fields) - 1, 2):
            match = re.fullmatch(rb":(100644|000000) 100644 ([0-9a-f]{40}) ([0-9a-f]{40}) ([AM])", fields[index])
            _require(match is not None, "only ordinary added evidence and modified task metadata allowed")
            path = fields[index + 1].decode("utf-8", errors="strict")
            _require(path in entry["files"] and path.casefold() not in actual and
                     match[4] == (b"M" if path == task else b"A"), "unexpected metadata scope/change")
            actual[path.casefold()] = path
            _require(digest(self._read_blob(entry["head"], path)) == entry["files"][path], "fixed metadata bytes changed")
        _require(set(actual.values()) == set(entry["files"]), "missing or extra metadata changes")

    def _offline(self, entry):
        """Run only the deployed pure validator in a credential-free container."""
        _require(not entry.get("offline_started"), "unknown or failed isolated validation cannot be retried automatically")
        entry["offline_started"] = True
        self._save()
        run = self.broker.executor.config.workspace_root / ("parent-validate-" + uuid.uuid4().hex)
        work, artifacts = run / "workspace", run / "artifacts"
        work.mkdir(parents=True)
        artifacts.mkdir()
        for path in entry["files"]:
            target = work.joinpath(*path.split("/"))
            if os.name == "nt":
                # The immutable SHA-based evidence subtree can exceed Win32's
                # historical 260-character limit. Only this already bounded,
                # freshly created export receives the extended-path prefix.
                target = Path("\\\\?\\" + str(target.resolve()))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self._read_blob(entry["head"], path))
        # Fixed deployed bytes, not tools from the proposed PR or checkout.
        from services.automation import completion as completion_module

        tool = work / "_trusted_completion.py"
        tool.write_bytes(regular_file(Path(completion_module.__file__), maximum=MAX_FILE))
        script = ("import hashlib,json,pathlib,runpy; "
                  "m=runpy.run_path('_trusted_completion.py'); "
                  "root=pathlib.Path('.'); b=json.loads((root/" + repr(entry["completion"]["path"]) + ").read_bytes()); "
                  "r=lambda ref:(root/b['artifact_files'][ref.sha256]).read_bytes(); "
                  "v=m['validate_completion_bundle'](b,r,expected_task_id=" + repr(entry["task_id"]) +
                  ",expected_receipt_sha256=" + repr(entry["candidate"]) + "); "
                  "assert v.sha256==" + repr(entry["candidate"]) + "; print('fixed parent bundle validation passed')")
        log = self.root / (entry["candidate"] + "-offline.log")
        result = self.broker.executor.run(["python", "-I", "-c", script], cwd=work, artifacts=artifacts,
            env={}, output=log, timeout_seconds=120, heartbeat=self.broker.enabled,
            role="validator", readonly_workspace=True)
        boundary = self.broker.executor.last_boundary
        _require(result.returncode == 0 and not result.stopped_reason and
                 boundary.get("backend") == "docker" and boundary.get("role") == "validator" and
                 boundary.get("image_id") == self.broker.executor.config.image and
                 boundary.get("publisher_credentials_mounted") is False and boundary.get("ai_profile_mounted") is False and
                 boundary.get("network") == "none" and boundary.get("uid") == 1000 and boundary.get("readonly_root") is True and
                 boundary.get("caps_dropped") is True and boundary.get("no_new_privileges") is True,
                 "actual isolated offline bundle validation failed")
        entry["offline"] = {"head": entry["head"], "log_sha256": digest(regular_file(log)), "boundary": boundary}
        self._save()

    def _pr(self, entry):
        if entry.get("pr_number"):
            row = self.broker.github.request("GET", f"repos/{REPO}/pulls/{entry['pr_number']}")
        else:
            rows = self.broker.github.pages(f"repos/{REPO}/pulls?state=all&head={REPO.split('/')[0]}:{entry['branch']}")
            matches = [r for r in rows if r.get("head", {}).get("ref") == entry["branch"]]
            _require(len(matches) <= 1, "conflicting publication PRs")
            if not matches:
                return None
            row = matches[0]
        _require(row.get("user", {}).get("login") == PM and row.get("head", {}).get("sha") == entry["head"] and
                 row.get("base", {}).get("ref") == "main" and
                 row.get("base", {}).get("repo", {}).get("full_name") == REPO and
                 row.get("head", {}).get("repo", {}).get("full_name") == REPO and not row.get("draft") and
                 type(row.get("number")) is int and row["number"] > 0, "publication PR identity/head mismatch")
        entry["pr_number"] = row["number"]
        self._save()
        return row

    def _ci(self, entry, contract):
        response = self.broker.github.request("GET", f"repos/{REPO}/commits/{entry['head']}/check-runs?per_page=100")
        checks = response.get("check_runs", [])
        _require(type(response.get("total_count")) is int and response["total_count"] == len(checks) <= 100,
                 "complete bounded exact-head CI required")
        required = ({name for cap in contract.capabilities for name in cap.required_checks} |
                    set(self.broker.policy.get("required_ci_contexts", [])))
        by_name = {}
        for row in checks:
            _require(row.get("head_sha") == entry["head"] and isinstance(row.get("name"), str), "stale CI evidence")
            by_name.setdefault(row["name"], []).append(row)
        if not required <= set(by_name) or any(row.get("status") != "completed" for row in checks):
            return False
        _require(all(row.get("app", {}).get("id") == self.broker.config.get("required_ci_app_id", 15368)
                     for name in required for row in by_name[name]), "required CI must come from trusted GitHub Actions")
        _require(all(len(rows) == 1 for rows in by_name.values()) and
                 all(row.get("conclusion") == "success" for row in checks), "CI failure, duplicate or non-success blocks publication")
        return True

    def __call__(self, contract, candidate, store):
        with exclusive_lock(self.root / "publisher.lock"):
            return self._tick(contract, candidate, store)

    def resume_pending(self, store):
        """Continue fixed candidates even after their metadata advances main.

        This runs before collecting a new candidate. Neither changed main nor a
        missing response causes rebuilding/resending a PR, merge or snapshot.
        """
        from services.automation.completion import CompletionReceipt, load_contract

        publications = []
        with exclusive_lock(self.root / "publisher.lock"):
            for key, entry in list(self.state["publications"].items())[:MAX_FILES]:
                if entry.get("complete") or not self.broker.enabled():
                    continue
                raw = regular_file(self.root / (key + ".candidate.json"), maximum=MAX_FILE)
                _require(digest(raw) == key, "immutable pending candidate changed")
                candidate = CompletionReceipt(raw, key)
                sources = [ArtifactRef.parse(ref) for ref in candidate.payload["sources"]]
                _require(len(sources) == 3, "complete pending candidate sources required")
                contract = load_contract(entry["task_id"], candidate.payload["source_commit"], *sources,
                                         store.registry, store.read)
                publication = self._tick(contract, candidate, store)
                if publication is not None:
                    publications.append({"task_id": entry["task_id"], "publication": publication})
        return publications

    def _project(self, entry, commit):
        """Post at most once; exact authenticated current-commit ACK is required."""
        route = f"repos/{REPO}/issues/28/comments"
        body = '/lgax-sync\n```json\n' + canonical({"commit": commit}) + '\n```'
        rows = self.broker.github.pages(route)
        found = [r for r in rows if r.get("user", {}).get("login") == PM and r.get("body") == body]
        _require(len(found) <= 1, "ambiguous Project approval sources")
        if not found:
            if "project" in entry["operations"]:
                return None
            self._authority(commit)
            self._reserve(entry, "project", entry["task_id"])
            try:
                self.broker.github.request("POST", route, {"body": body})
            except PMError:
                return None
            rows = self.broker.github.pages(route)
            found = [r for r in rows if r.get("user", {}).get("login") == PM and r.get("body") == body]
            if not found:
                return None
            _require(len(found) == 1, "ambiguous actual Project approval")
        source = found[0]
        _require(source.get("updated_at") == source.get("created_at") and type(source.get("id")) is int,
                 "edited Project approval cannot authorize publication")
        prefix = f"LGAX-RECEIPT {source['id']} "
        received = [r for r in rows if r.get("user", {}).get("login") == PM and r.get("body", "").startswith(prefix)]
        _require(len(received) <= 1, "ambiguous actual Project ACK")
        if not received:
            return None
        receipt = received[0]
        _require(receipt["body"].startswith(prefix + "ACCEPTED\n") and f"`{commit}`" in receipt["body"],
                 "Project refused or mismatched exact publication commit")
        pattern = r"https://github\.com/" + re.escape(REPO) + r"/issues/28#issuecomment-[1-9][0-9]*"
        _require(all(re.fullmatch(pattern, r.get("html_url", "")) for r in (source, receipt)),
                 "fixed Project receipt URL required")
        project = {"approval_url": source["html_url"], "receipt_url": receipt["html_url"], "commit": commit}
        if "project" not in entry["operations"]:
            # This exact current-commit approval was independently observed; do
            # not send another comment simply to create a local reservation.
            self._reserve(entry, "project", entry["task_id"])
        if entry["operations"]["project"]["state"] != "confirmed":
            self._confirmed(entry, "project", project)
        return project

    def _tick(self, contract, candidate, store):
        key = candidate.sha256
        files, completion = self._export(contract, candidate, store)
        base = candidate.payload["tested_commit"]
        entry = self.state["publications"].setdefault(key, {"candidate": key, "base": base,
            "task_id": contract.task_id, "contract_fingerprint": contract.fingerprint, "operations": {}})
        _require(entry["base"] == base and entry["task_id"] == contract.task_id and
                 entry["contract_fingerprint"] == contract.fingerprint, "publication identity changed")
        self._save()
        candidate_path = self.root / (key + ".candidate.json")
        if candidate_path.exists():
            _require(regular_file(candidate_path, maximum=MAX_FILE) == candidate.raw, "immutable candidate file changed")
        else:
            with candidate_path.open("xb") as output:
                output.write(candidate.raw)
        if not self.broker.enabled():
            return None
        expected_main = entry.get("merged_commit", base)
        if entry.get("head") and "merge" in entry["operations"] and not entry.get("merged_commit"):
            # A conditional merge can succeed while its response is lost. Read
            # the exact reserved PR before deciding that main has raced; no
            # second merge is ever attempted. Parent/tree checks below still
            # authenticate the observed squash commit before any admission.
            self.broker.authenticate()
            observed = self._pr(entry)
            if observed and observed.get("merged"):
                merged = observed.get("merge_commit_sha")
                _require(isinstance(merged, str) and SHA.fullmatch(merged), "unknown merge lacks an immutable commit")
                expected_main = merged
        self._authority(expected_main)
        if not entry.get("head"):
            self._prepare(contract, candidate, entry, files, completion)
        else:
            self._origin()
            self._verify_metadata(entry)
        if not entry.get("offline"):
            self._offline(entry)
        _require(entry["offline"].get("head") == entry["head"], "isolated validation head mismatch")
        branch_route = f"repos/{REPO}/git/ref/heads/{entry['branch']}"
        pushed = entry["operations"].get("push")
        if not pushed:
            self._authority(base)
            self._reserve(entry, "push", contract.task_id)
            try:
                self._git(["push", "--porcelain", "--force-with-lease=refs/heads/" + entry["branch"] + ":",
                           "origin", entry["head"] + ":refs/heads/" + entry["branch"]])
            except PMError:
                return None
        if not pushed or pushed["state"] != "confirmed":
            try:
                remote = self.broker.github.request("GET", branch_route)
            except PMError:
                return None
            _require(remote.get("object", {}).get("sha") == entry["head"], "published branch did not match exact metadata head")
            self._confirmed(entry, "push", {"head": entry["head"]})
        pr = self._pr(entry)
        if pr is None:
            if "pr" in entry["operations"]:
                return None
            self._authority(base)
            body = self.root / (key + "-pr-body.md")
            body.write_text("PM metadata publication for " + contract.task_id + ".\n\n"
                            "Independent parent receipt: `" + key + "`.\n"
                            "Product source remains at `" + base + "`; immutable evidence and formal status only.\n",
                            encoding="utf-8")
            self._reserve(entry, "pr", contract.task_id)
            try:
                self.broker.github.command(["pr", "create", "--repo", REPO, "--base", "main", "--head", entry["branch"],
                    "--title", "PM parent completion: " + contract.task_id, "--body-file", str(body)])
            except PMError:
                return None
            pr = self._pr(entry)
            if pr is None:
                return None
        if entry["operations"].get("pr", {}).get("state") != "confirmed":
            if "pr" not in entry["operations"]:
                raise CompletionError("unreserved metadata PR exists")
            self._confirmed(entry, "pr", {"pr_number": entry["pr_number"], "head": entry["head"]})
        if not pr.get("merged"):
            if "merge" in entry["operations"] or not self._ci(entry, contract):
                return None
            _require(pr.get("state") == "open" and pr.get("base", {}).get("sha") == base,
                     "metadata PR base moved before conditional merge")
            self._authority(base)
            self._verify_metadata(entry)
            admin = self.broker.config.get("parent_publication_administrator_bypass") is True
            if admin:
                _require(self.broker.policy.get("allow_admin_bypass") is True and
                         bool(self.broker.policy.get("admin_bypass_delegation")), "automatic administrator bypass delegation absent")
            self._reserve(entry, "merge", contract.task_id)
            args = ["pr", "merge", str(entry["pr_number"]), "--repo", REPO, "--squash",
                    "--match-head-commit", entry["head"]]
            if admin:
                args.append("--admin")
            try:
                self.broker.github.command(args)
            except PMError:
                return None
            pr = self._pr(entry)
            if not pr.get("merged"):
                return None
        merged = pr.get("merge_commit_sha")
        _require(isinstance(merged, str) and SHA.fullmatch(merged), "actual published squash commit unavailable")
        parents = self.broker.github.request("GET", f"repos/{REPO}/commits/{merged}").get("parents", [])
        _require([p.get("sha") for p in parents] == [base] and self._main() == merged,
                 "actual metadata merge raced; no formal dependency release")
        self._git(["fetch", "--no-tags", "origin", merged])
        _require(self._git(["rev-parse", merged + "^{tree}"]).decode().strip() == entry["tree"],
                 "published metadata tree differs from validated exact head")
        entry["merged_commit"] = merged
        self._save()
        if entry["operations"].get("merge", {}).get("state") != "confirmed":
            _require("merge" in entry["operations"], "unreserved metadata merge")
            self._confirmed(entry, "merge", {"commit": merged})
        self._authority(merged)
        project = self._project(entry, merged)
        if project is None:
            return None
        status = self.broker.controller.request("/v1/status")
        snapshot = status.get("formal_snapshot", {})
        tasks = snapshot.get("tasks", {})
        _require(contract.task_id in tasks and tasks[contract.task_id].get("owner") == contract.owner,
                 "actual formal controller ownership mismatch")
        expected = {k: dict(v) for k, v in tasks.items()}
        expected[contract.task_id]["status"] = "done"
        self.broker._formal_source_matches(merged, {"tasks": expected})
        already = snapshot.get("approved_commit") == merged and tasks == expected
        if not already:
            if "snapshot" in entry["operations"]:
                return None
            self._authority(merged)
            self._reserve(entry, "snapshot", contract.task_id)
            try:
                self.broker.controller.request("/v1/formal-snapshot", {"approved_commit": merged,
                    "tasks": expected, "approval_reference": project["receipt_url"] + " · independently accepted parent " + key})
            except (PMError, ValueError, OSError):
                return None
            status = self.broker.controller.request("/v1/status")
            snapshot = status.get("formal_snapshot", {})
            if snapshot.get("approved_commit") != merged or snapshot.get("tasks") != expected:
                return None
        if "snapshot" not in entry["operations"]:
            raise CompletionError("unreserved formal snapshot cannot admit parent completion")
        if entry["operations"]["snapshot"]["state"] != "confirmed":
            self._confirmed(entry, "snapshot", {"approved_commit": merged, "tasks_sha256": fingerprint(expected)})
        self._authority(merged)
        completed = store.admit("parent_completion", merged, candidate.raw)
        ack = store.admit("snapshot_ack", merged, {"schema_version": 1, "kind": "snapshot_ack", "repo": REPO,
            "approved_commit": merged, "outcome": "accepted", "project_receipt": project["receipt_url"],
            "controller_receipt": fingerprint(snapshot), "task_states": {k: v["status"] for k, v in expected.items()},
            "completion_digests": {contract.task_id: key}})
        store.index.setdefault("published_completions", {})[contract.task_id] = {
            "completion": completed.as_dict(), "snapshot_ack": ack.as_dict()}
        store.save()
        entry["complete"] = True
        entry["snapshot_ack"] = ack.as_dict()
        self._save()
        from services.automation.parent_collector import Publication

        return Publication(merged, ack)
