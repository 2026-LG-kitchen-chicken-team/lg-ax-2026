"""Policy tests for the no-host-credential executor; actual proof is opt-in.

Mock metadata verifies fail-closed policy, not real container isolation. The
live test requires LGAX_TEST_EXECUTOR_IMAGE and a reachable Linux Docker engine.
"""
import hashlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from services.automation.isolation import (
    ARTIFACT_NAMES,
    OWNED_LABEL,
    DockerConfig,
    DockerExecutor,
    cleanup_auth_runtime,
    export_workspace,
    prepare_build_context,
    redact_output,
    regular_file,
    snapshot_files,
    verify_canary_boundary,
)


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.work_root = self.root / "jobs"
        self.work = self.work_root / "job/work"
        self.artifacts = self.work_root / "job/artifacts"
        self.auth = self.root / "own-ai-profile"
        for path in (self.work, self.artifacts, self.auth):
            path.mkdir(parents=True)
        self.image = "sha256:" + "a" * 64
        self.config = DockerConfig(self.image, self.work_root, self.auth)

    def executor(self, config=None):
        exe = "C:/Docker/docker.exe" if os.name == "nt" else "/usr/bin/docker"
        with patch("services.automation.isolation.shutil.which", return_value=exe):
            return DockerExecutor(config or self.config)

    def command(self, *, role="model", readonly=False, argv=None):
        executor = self.executor()
        return executor, executor._create_arguments("lgax-executor-test", "own-token",
            argv or ["python", "-c", "print('ok')"], cwd=self.work, artifacts=self.artifacts,
            env={}, role=role, timeout_seconds=25, readonly_workspace=readonly)

    def metadata(self, *, role="model", readonly=False):
        mounts = [{"Type": "bind", "Source": str(self.work), "Destination": "/workspace", "RW": not readonly},
                  {"Type": "bind", "Source": str(self.artifacts), "Destination": "/artifacts", "RW": True}]
        if role == "model":
            mounts.append({"Type": "bind", "Source": str(self.auth), "Destination": "/agent-auth", "RW": True})
        return {"Id": "b" * 64, "Image": self.image,
                "Config": {"User": "1000:1000", "Labels": {OWNED_LABEL: "own-token"}},
                "HostConfig": {"Privileged": False, "ReadonlyRootfs": True,
                    "NetworkMode": "bridge" if role == "model" else "none", "PidMode": "", "IpcMode": "private",
                    "CapDrop": ["ALL"], "SecurityOpt": ["no-new-privileges=true"]}, "Mounts": mounts}

    def test_immutable_image_and_bounded_role_required(self):
        for bad in ("lgax:latest", "repo@sha256:" + "a" * 64, "sha256:" + "g" * 64, ""):
            with self.subTest(image=bad), self.assertRaises(ValueError):
                replace(self.config, image=bad).validate()
        for bad in ("host", "container:x", "default"):
            with self.subTest(network=bad), self.assertRaises(ValueError):
                replace(self.config, model_network=bad).validate()
        for changes in ({"memory_mb": 0}, {"cpus": 99}, {"pids": True}, {"engine": "other"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.config, **changes).validate()
        self.config.validate()

    def test_mount_separators_and_shared_auth_refused(self):
        bad = self.root / "host,path"
        bad.mkdir()
        for config in (replace(self.config, workspace_root=bad), replace(self.config, auth_root=self.work),
                       replace(self.config, auth_root=self.root)):
            with self.subTest(config=config), self.assertRaises(ValueError):
                config.validate()

    def test_dedicated_ai_profile_cannot_link_to_a_publisher_file(self):
        target = self.root / "harmless-publisher-testfile"
        target.write_text("harmless", encoding="utf-8")
        os.link(target, self.auth / "linked-host-file")
        with self.assertRaises(ValueError):
            self.config.validate()

    def test_unavailable_docker_has_no_native_fallback(self):
        with patch("services.automation.isolation.shutil.which", return_value=None), self.assertRaises(ValueError):
            DockerExecutor(self.config)
        exe = self.executor()
        with patch("services.automation.isolation.subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 15)), \
                self.assertRaises(RuntimeError):
            exe.preflight()

    def test_only_exact_linux_image_and_nonroot_preflight_accepted(self):
        exe = self.executor()
        accepted = [{"Id": self.image, "Config": {"User": "1000:1000"}}]
        with patch.object(exe, "_docker", side_effect=[json.dumps({"OSType": "linux"}), json.dumps(accepted)]):
            self.assertFalse(exe.preflight()["native_fallback"])
        for info, image in (({"OSType": "windows"}, accepted),
                            ({"OSType": "linux"}, [{"Id": self.image, "Config": {"User": "root"}}]),
                            ({"OSType": "linux"}, [{"Id": "sha256:" + "b" * 64, "Config": {"User": "1000:1000"}}])):
            with patch.object(exe, "_docker", side_effect=[json.dumps(info), json.dumps(image)]), \
                    self.assertRaises(ValueError):
                exe.preflight()

    def test_model_mounts_only_work_artifacts_and_own_ai_auth(self):
        _, args = self.command()
        mounts = [args[index + 1] for index, value in enumerate(args) if value == "--mount"]
        self.assertEqual(len(mounts), 3)
        self.assertTrue(any("destination=/agent-auth" in row for row in mounts))
        self.assertFalse(any("docker.sock" in row or "publisher" in row or "controller" in row for row in mounts))
        self.assertIn("--read-only", args)
        self.assertEqual(args[args.index("--network") + 1], "bridge")
        self.assertEqual(args[args.index("--user") + 1], "1000:1000")
        self.assertEqual(args[args.index("--cap-drop") + 1], "ALL")
        self.assertIn("no-new-privileges=true", args)
        self.assertIn("--kill-after=5s", args)
        self.assertIn("25.000s", args)

    def test_validator_has_no_network_or_ai_auth(self):
        exe, args = self.command(role="validator")
        mounts = [args[index + 1] for index, value in enumerate(args) if value == "--mount"]
        self.assertEqual(len(mounts), 2)
        self.assertEqual(args[args.index("--network") + 1], "none")
        env = exe._environment({"CODEX_HOME": str(self.auth), "OPENAI_API_KEY": "sensitive",
                                "GH_TOKEN": "sensitive", "LGAX_CONTROLLER_TOKEN": "sensitive"}, "validator")
        self.assertFalse(any(key in env for key in ("CODEX_HOME", "CLAUDE_CONFIG_DIR", "GH_TOKEN",
                                                   "LGAX_CONTROLLER_TOKEN", "OPENAI_API_KEY")))
        self.assertEqual(env["UV_OFFLINE"], "1")
        self.assertEqual(env["UV_CACHE_DIR"], "/home/executor/uv-cache")
        self.assertEqual(env["UV_PROJECT_ENVIRONMENT"], "/opt/lgax-venv")
        self.assertTrue(env["PYTHONPATH"].startswith("/workspace/packages/core/src"))

    def test_review_workspace_is_readonly(self):
        _, args = self.command(readonly=True)
        mounts = [args[index + 1] for index, value in enumerate(args) if value == "--mount"]
        self.assertTrue(any("destination=/workspace,readonly" in row for row in mounts))

    def test_auth_required_only_for_model(self):
        exe = self.executor(replace(self.config, auth_root=None))
        with self.assertRaises(ValueError):
            exe._create_arguments("test", "token", ["python", "-c", "pass"], cwd=self.work,
                artifacts=self.artifacts, env={}, role="model", timeout_seconds=10, readonly_workspace=False)
        args = exe._create_arguments("test", "token", ["python", "-c", "pass"], cwd=self.work,
                artifacts=self.artifacts, env={}, role="validator", timeout_seconds=10, readonly_workspace=False)
        self.assertNotIn("destination=/agent-auth", " ".join(args))

    def test_private_supervisor_files_and_git_metadata_are_not_mountable(self):
        (self.artifacts / "checkpoint.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.command()
        (self.artifacts / "checkpoint.json").unlink()
        (self.work / ".git").write_text("gitdir: secret-host", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.command()
        (self.work / ".git").unlink()
        outside = self.root / "other-work"
        outside.mkdir()
        with self.assertRaises(ValueError):
            self.executor()._paths(outside, self.artifacts)

    def test_artifact_and_workspace_argument_paths_translate_without_arbitrary_mounts(self):
        exe = self.executor()
        argv = exe._translate(["codex", "exec", "--output-schema", str(self.artifacts / "result-schema.json"),
            "--output-last-message", str(self.artifacts / "result.json"), str(self.work / "tests")],
            self.work, self.artifacts)
        self.assertIn("/artifacts/result-schema.json", argv)
        self.assertIn("/artifacts/result.json", argv)
        self.assertIn("/workspace/tests", argv)
        for command in (["powershell", "-c", "pass"], ["python", str(self.auth / "auth.json")],
                        ["python", str(self.artifacts / "checkpoint.json")]):
            with self.subTest(command=command), self.assertRaises(ValueError):
                exe._translate(command, self.work, self.artifacts)

    def test_credential_like_optional_environment_rejected(self):
        exe = self.executor()
        for value in ("http://user:password@example.invalid", "https://example.invalid?a=token", "Bearer " + "x" * 40):
            with self.subTest(value=value), self.assertRaises(ValueError):
                exe._environment({"LGAX_MODEL_ENDPOINT": value}, "model")
        env = exe._environment({"LGAX_MODEL_ID": "qwen3:8b", "ACCESS_TOKEN": "secret"}, "model")
        self.assertEqual(env["LGAX_MODEL_ID"], "qwen3:8b")
        self.assertNotIn("ACCESS_TOKEN", env)

    def test_inspected_privileged_or_extra_mount_metadata_refused(self):
        exe = self.executor()
        good = self.metadata()
        with patch.object(exe, "_docker", return_value=json.dumps([good])):
            exe._inspect_boundary("b" * 64, "own-token", role="model", cwd=self.work,
                                  artifacts=self.artifacts, readonly_workspace=False)
        self.assertFalse(exe.last_boundary["publisher_credentials_mounted"])
        cases = []
        for key, value in (("Privileged", True), ("NetworkMode", "host"), ("ReadonlyRootfs", False),
                           ("PidMode", "host"), ("IpcMode", "host"), ("CapDrop", []), ("SecurityOpt", [])):
            row = self.metadata()
            row["HostConfig"][key] = value
            cases.append(row)
        row = self.metadata()
        row["Mounts"].append({"Type": "bind", "Source": "/var/run/docker.sock", "Destination": "/var/run/docker.sock"})
        cases.append(row)
        row = self.metadata()
        row["Mounts"][0]["Source"] = str(self.root)
        cases.append(row)
        row = self.metadata()
        row["Mounts"][0]["RW"] = False
        cases.append(row)
        for row in cases:
            with self.subTest(row=row), patch.object(exe, "_docker", return_value=json.dumps([row])), \
                    self.assertRaises(ValueError):
                exe._inspect_boundary("b" * 64, "own-token", role="model", cwd=self.work,
                                      artifacts=self.artifacts, readonly_workspace=False)

    def test_docker_desktop_canonical_mount_source_accepted(self):
        if os.name != "nt":
            self.skipTest("Windows bind path normalization fixture")
        exe = self.executor()
        row = self.metadata()
        for mount in row["Mounts"]:
            path = mount["Source"].replace("\\", "/")
            mount["Source"] = "/run/desktop/mnt/host/" + path[0].lower() + path[2:]
        with patch.object(exe, "_docker", return_value=json.dumps([row])):
            exe._inspect_boundary("b" * 64, "own-token", role="model", cwd=self.work,
                                  artifacts=self.artifacts, readonly_workspace=False)

    def test_cleanup_refuses_another_users_container(self):
        exe = self.executor()
        foreign = self.metadata()
        foreign["Config"]["Labels"][OWNED_LABEL] = "someone-else"
        with patch.object(exe, "_docker", return_value=json.dumps([foreign])) as docker:
            with self.assertRaises(ValueError):
                exe._remove_owned("b" * 64, "own-token")
            self.assertEqual(docker.call_count, 1)
        owned = self.metadata()
        with patch.object(exe, "_docker", side_effect=[json.dumps([owned]), ""]) as docker:
            exe._remove_owned("b" * 64, "own-token")
            self.assertEqual(docker.call_args_list[1].args[0], ["rm", "--force", "b" * 64])

    def test_off_before_start_launches_no_container(self):
        exe = self.executor()
        with patch.object(exe, "preflight") as preflight, patch.object(exe, "_docker") as docker:
            result = exe.run(["python", "-c", "pass"], cwd=self.work, artifacts=self.artifacts, env={},
                output=self.root / "private.log", timeout_seconds=10, heartbeat=lambda: False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("before start", result.stopped_reason)
        preflight.assert_not_called()
        docker.assert_not_called()

    def test_guest_cannot_write_supervisor_output_path(self):
        exe = self.executor()
        with patch.object(exe, "preflight"):
            for output in (self.work / "log", self.artifacts / "result.json"):
                with self.subTest(output=output), self.assertRaises(ValueError):
                    exe.run(["python", "-c", "pass"], cwd=self.work, artifacts=self.artifacts, env={},
                        output=output, timeout_seconds=10, heartbeat=lambda: True)

    def test_bounds_checked_before_docker_start(self):
        exe = self.executor()
        for change in ({"timeout_seconds": 0}, {"timeout_seconds": 8000}, {"heartbeat_interval": 0},
                       {"max_output_bytes": 1}, {"input_text": "x" * (1024 * 1024 + 1)}):
            options = {"cwd": self.work, "artifacts": self.artifacts, "env": {}, "output": self.root / "private.log",
                       "timeout_seconds": 10, "heartbeat": lambda: True, **change}
            with self.subTest(change=list(change)), self.assertRaises(ValueError):
                exe.run(["python", "-c", "pass"], **options)

    def test_private_log_redaction_preserves_regular_structured_output(self):
        secret = "ghp_" + "x" * 40
        payload = json.dumps({"access_token": "test-token", "message": "safe", "raw": secret}).encode()
        value = json.loads(redact_output(payload))
        self.assertEqual(value["access_token"], "[REDACTED_CREDENTIAL]")
        self.assertEqual(value["raw"], "[REDACTED_CREDENTIAL]")
        self.assertEqual(value["message"], "safe")

    def test_workspace_export_omits_all_host_git_and_private_files(self):
        source = self.root / "source"
        source.mkdir()
        for name in (".git/config", "private/token", ".venv/secrets", "node_modules/test", "packages/core/a.py"):
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("harmless", encoding="utf-8")
        target = self.root / "export"
        proof = export_workspace(source, target)
        self.assertEqual(proof["exported_files"], 1)
        self.assertEqual(list(snapshot_files(target)), ["packages/core/a.py"])
        self.assertFalse((target / ".git").exists())
        with self.assertRaises(ValueError):
            export_workspace(source, source / "child")

    def test_hardlinks_cannot_enter_export_or_frozen_publisher_input(self):
        source = self.root / "source"
        source.mkdir()
        original = source / "original.txt"
        original.write_text("harmless", encoding="utf-8")
        os.link(original, source / "linked.txt")
        with self.assertRaises(ValueError):
            regular_file(original)
        with self.assertRaises(ValueError):
            export_workspace(source, self.root / "export")
        with self.assertRaises(ValueError):
            snapshot_files(source)

    def test_symlink_outputs_refused(self):
        original = self.root / "original"
        original.write_text("harmless", encoding="utf-8")
        link = self.work / "linked"
        try:
            link.symlink_to(original)
        except OSError:
            self.skipTest("Windows symlink privilege not enabled")
        with self.assertRaises(ValueError):
            snapshot_files(self.work)

    def test_frozen_artifact_total_size_bound(self):
        (self.work / "a").write_bytes(b"12345")
        (self.work / "b").write_bytes(b"12345")
        with self.assertRaises(ValueError):
            snapshot_files(self.work, maximum=8)
        hashes = snapshot_files(self.work)
        self.assertEqual(hashes["a"], hashlib.sha256(b"12345").hexdigest())

    def test_minimal_build_context_never_sends_private_or_git(self):
        source = self.root / "repo"
        for name in ("services/automation/Dockerfile.executor", "pyproject.toml", "uv.lock", "apps/web/package.json",
                     "apps/web/package-lock.json", "private/token", ".git/config"):
            target = source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("harmless", encoding="utf-8")
        result = prepare_build_context(source, self.root / "context")
        self.assertEqual(len(result["whitelisted_files"]), 5)
        self.assertFalse(result["private_files_included"])
        self.assertFalse((self.root / "context/private").exists())
        self.assertFalse((self.root / "context/.git").exists())

    def test_harmless_proof_requires_an_unmounted_publisher_canary(self):
        executor = self.executor()
        bad_canary = self.auth / "bad-canary"
        bad_canary.write_text("harmless", encoding="utf-8")
        with self.assertRaises(ValueError):
            verify_canary_boundary(executor, cwd=self.work, artifacts=self.artifacts,
                protected_canary=bad_canary, output_dir=self.root / "probe-output")
        self.assertEqual(ARTIFACT_NAMES, {"result-schema.json", "result.json", "empty-mcp.json", "empty-settings.json",
                                         "product-request.json", "product-response.json"})


class MockExecutionTests(unittest.TestCase):
    setUp = IsolationTests.setUp
    executor = IsolationTests.executor
    metadata = IsolationTests.metadata

    def test_actual_container_exit_checked_and_owned_container_removed(self):
        executor = self.executor()
        identifier = "b" * 64
        response = self.metadata(role="validator")
        response["State"] = {"Running": False, "ExitCode": 7, "OOMKilled": False}

        class FakeProcess:
            def __init__(self):
                self.stdin = io.BytesIO()
                self.stdout = io.BytesIO(b'{"message":"harmless"}\n')
                self.returncode = 0  # Attachment success is not container success.

            def poll(self):
                return self.returncode

            def wait(self, timeout=None):
                return self.returncode

        with patch.object(executor, "preflight"), patch.object(executor, "_inspect_boundary"), \
                patch.object(executor, "_remove_owned") as remove, \
                patch.object(executor, "_docker", side_effect=[identifier, json.dumps([response])]), \
                patch("services.automation.isolation.subprocess.Popen", return_value=FakeProcess()):
            result = executor.run(["python", "-c", "pass"], cwd=self.work, artifacts=self.artifacts,
                env={}, output=self.root / "private.log", timeout_seconds=10, heartbeat=lambda: True)
        self.assertEqual(result.returncode, 7)
        self.assertIsNone(result.stopped_reason)
        remove.assert_called_once()

    def test_daemon_timeout_classified_even_when_attachment_succeeded(self):
        executor = self.executor()
        row = self.metadata(role="validator")
        row["State"] = {"Running": False, "ExitCode": 124, "OOMKilled": False}

        class CompletedProcess:
            returncode = 0
            stdin = io.BytesIO()
            stdout = io.BytesIO(b"daemon deadline\n")

            def poll(self):
                return 0

            def wait(self, timeout=None):
                return 0

        with patch.object(executor, "preflight"), patch.object(executor, "_inspect_boundary"), \
                patch.object(executor, "_remove_owned"), \
                patch.object(executor, "_docker", side_effect=["b" * 64, json.dumps([row])]), \
                patch("services.automation.isolation.subprocess.Popen", return_value=CompletedProcess()):
            result = executor.run(["python", "-c", "pass"], cwd=self.work, artifacts=self.artifacts,
                env={}, output=self.root / "private.log", timeout_seconds=10, heartbeat=lambda: True)
        self.assertEqual(result.returncode, 124)
        self.assertIn("daemon-side", result.stopped_reason)

    def test_off_and_timeout_terminate_only_the_owned_container(self):
        for mode in ("off", "timeout"):
            executor = self.executor()

            class RunningProcess:
                returncode = None
                stdin = io.BytesIO()
                stdout = io.BytesIO(b"harmless waiting\n")

                def poll(self):
                    return self.returncode

                def wait(self, timeout=None):
                    return self.returncode

            process = RunningProcess()

            def stop(*_args, owned=process):
                owned.returncode = 137

            beats = iter((True, False))
            heartbeat = (lambda sequence=beats: next(sequence)) if mode == "off" else (lambda: True)
            with self.subTest(mode=mode), patch.object(executor, "preflight"), \
                    patch.object(executor, "_inspect_boundary"), \
                    patch.object(executor, "_remove_owned", side_effect=stop) as remove, \
                    patch.object(executor, "_docker", return_value="b" * 64), \
                    patch("services.automation.isolation.subprocess.Popen", return_value=process):
                result = executor.run(["python", "-c", "pass"], cwd=self.work, artifacts=self.artifacts,
                    env={}, output=self.root / (mode + ".log"), timeout_seconds=0.08, heartbeat=heartbeat,
                    heartbeat_interval=0.02, poll_interval=0.01)
            self.assertEqual(result.returncode, 137)
            self.assertIsNotNone(result.stopped_reason)
            self.assertIn("OFF/STOP" if mode == "off" else "timeout", result.stopped_reason)
            remove.assert_called_once()

    def test_oversized_unterminated_stdout_stops_without_disclosing_it(self):
        executor = self.executor()

        class RunningProcess:
            returncode = None
            stdin = io.BytesIO()
            stdout = io.BytesIO(b"x" * (1024 * 1024))

            def poll(self):
                return self.returncode

            def wait(self, timeout=None):
                return self.returncode

        process = RunningProcess()

        def stop(*_args):
            process.returncode = 137

        output = self.root / "private.log"
        with patch.object(executor, "preflight"), patch.object(executor, "_inspect_boundary"), \
                patch.object(executor, "_remove_owned", side_effect=stop), \
                patch.object(executor, "_docker", return_value="b" * 64), \
                patch("services.automation.isolation.subprocess.Popen", return_value=process):
            result = executor.run(["python", "-c", "pass"], cwd=self.work, artifacts=self.artifacts,
                env={}, output=output, timeout_seconds=5, heartbeat=lambda: True)
        self.assertIsNotNone(result.stopped_reason)
        self.assertLess(output.stat().st_size, 1024)
        self.assertIn("suppressed", output.read_text(encoding="utf-8"))


class RuntimeCacheCleanupTests(unittest.TestCase):
    setUp = IsolationTests.setUp

    def cache_fixture(self):
        launch = self.auth / "tmp/arg0/codex-arg0ABC123"
        launch.mkdir(parents=True)
        (launch / ".lock").touch()
        (launch / "apply_patch").write_text("harmless generated launcher", encoding="utf-8")
        return launch

    def test_absent_runtime_cache_does_not_touch_docker_or_credentials(self):
        with patch("services.automation.isolation.subprocess.run") as run:
            result = cleanup_auth_runtime(self.auth, self.root / "cache")
        self.assertEqual(result["cleanup"], "not_needed")
        run.assert_not_called()

    def test_exact_tmp_moved_after_container_absence_without_auth_copy(self):
        self.cache_fixture()
        auth_file = self.auth / "auth.json"
        original = b'{"fixture":"harmless authentication placeholder"}'
        auth_file.write_bytes(original)
        calls = []

        def docker(arguments):
            calls.append(arguments)
            return ""

        result = cleanup_auth_runtime(self.auth, self.root / "cache", docker_call=docker)
        self.assertEqual(result["cleanup"], "quarantined")
        self.assertEqual(auth_file.read_bytes(), original)
        self.assertFalse(result["credentials_moved"])
        self.assertFalse(result["credentials_read"])
        self.assertFalse((self.auth / "tmp").exists())
        cached = Path(result["cache_directory"])
        self.assertTrue((cached / "arg0/codex-arg0ABC123/apply_patch").is_file())
        self.assertFalse((cached / "auth.json").exists())
        self.assertEqual(calls, [["ps", "--quiet"]])
        self.config.validate()

    def test_active_profile_container_refuses_cleanup(self):
        self.cache_fixture()
        rows = [{"Mounts": [{"Source": str(self.auth), "Destination": "/agent-auth"}]}]
        with self.assertRaises(ValueError):
            cleanup_auth_runtime(self.auth, self.root / "cache", docker_call=lambda args:
                "a" * 64 if args[0] == "ps" else json.dumps(rows))
        self.assertTrue((self.auth / "tmp").is_dir())

    def test_running_unrelated_container_is_not_stopped_or_mutated(self):
        self.cache_fixture()
        calls = []

        def docker(arguments):
            calls.append(arguments)
            return "a" * 64 if arguments[0] == "ps" else json.dumps([{
                "Mounts": [{"Source": str(self.root / "unrelated"), "Destination": "/other"}]}])

        result = cleanup_auth_runtime(self.auth, self.root / "cache", docker_call=docker)
        self.assertEqual(result["cleanup"], "quarantined")
        self.assertEqual([call[0] for call in calls], ["ps", "inspect"])

    def test_unknown_layout_never_relaxes_no_link_policy(self):
        for name in ("unexpected/token.json", "arg0/wrong-name/apply_patch", "arg0/codex-arg0ABC123/unrecognized"):
            with tempfile.TemporaryDirectory() as temporary:
                profile = Path(temporary).resolve()
                target = profile / "tmp" / name
                target.parent.mkdir(parents=True)
                target.write_text("harmless", encoding="utf-8")
                with self.subTest(name=name), self.assertRaises(ValueError):
                    cleanup_auth_runtime(profile, self.root / "cache", docker_call=lambda args: "")
                self.assertTrue(target.is_file())

    def test_running_desktop_mount_alias_refuses_cleanup(self):
        if os.name != "nt":
            self.skipTest("Windows Docker source alias fixture")
        self.cache_fixture()
        windows = str(self.auth).replace("\\", "/")
        alias = "/run/desktop/mnt/host/" + windows[0].lower() + windows[2:]
        with self.assertRaises(ValueError):
            cleanup_auth_runtime(self.auth, self.root / "cache", docker_call=lambda args:
                "a" * 64 if args[0] == "ps" else json.dumps([{"Mounts": [{"Source": alias}]}]))

    def test_docker_unreachable_retains_runtime(self):
        self.cache_fixture()
        with self.assertRaises(RuntimeError):
            cleanup_auth_runtime(self.auth, self.root / "cache", docker_call=lambda args:
                (_ for _ in ()).throw(RuntimeError("unavailable")))
        self.assertTrue((self.auth / "tmp").is_dir())

    def test_generated_linux_launcher_link_quarantined_without_following(self):
        launch = self.cache_fixture()
        (launch / "apply_patch").unlink()
        try:
            (launch / "apply_patch").symlink_to("/opt/unmounted/known-native-codex")
        except OSError:
            self.skipTest("Windows symlink privilege unavailable")
        result = cleanup_auth_runtime(self.auth, self.root / "cache", docker_call=lambda args: "")
        cached_link = Path(result["cache_directory"]) / "arg0/codex-arg0ABC123/apply_patch"
        self.assertTrue(cached_link.is_symlink())
        self.assertEqual(os.readlink(cached_link), "/opt/unmounted/known-native-codex")

    def test_cache_inside_profile_is_refused(self):
        self.cache_fixture()
        with self.assertRaises(ValueError):
            cleanup_auth_runtime(self.auth, self.auth / "cache", docker_call=lambda args: "")
        self.assertTrue((self.auth / "tmp").is_dir())


@unittest.skipUnless(os.environ.get("LGAX_TEST_EXECUTOR_IMAGE"), "explicit reviewed Docker image required for real proof")
class LiveIsolationTests(unittest.TestCase):
    def test_actual_not_mounted_canary_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            work = root / "jobs/job/work"
            artifacts = root / "jobs/job/artifacts"
            auth = root / "own-ai-profile"
            for path in (work, artifacts, auth):
                path.mkdir(parents=True)
                if os.name != "nt":
                    path.chmod(0o777)
            canary = root / "publisher-canary.txt"
            canary.write_text("not-a-real-credential-" + "x" * 32, encoding="utf-8")
            executor = DockerExecutor(DockerConfig(os.environ["LGAX_TEST_EXECUTOR_IMAGE"], root / "jobs", auth))
            proof = verify_canary_boundary(executor, cwd=work, artifacts=artifacts,
                protected_canary=canary, output_dir=root / "proof")
            self.assertTrue(proof["publisher_readable"])
            self.assertFalse(proof["real_secret_used"])
            self.assertFalse(proof["model_generation_executed"])


if __name__ == "__main__":
    unittest.main()
