"""Bounded child execution. OS user/VM isolation remains a deployment requirement.

Process groups/job objects stop descendants that belong to this worker. They do
not make arbitrary repository code safe against the operating-system user.
"""
from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    elapsed_seconds: float
    stopped_reason: str | None


class OwnedProcess:
    """A process tree we started; never enumerate or terminate other services."""

    def __init__(self, argv: list[str], *, cwd: Path, env: dict[str, str], output: Path,
                 input_text: str | None = None):
        output.parent.mkdir(parents=True, exist_ok=True)
        self.stream = output.open("wb")
        self.job = None
        options = {"start_new_session": True} if os.name != "nt" else {
            "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
        }
        try:
            self.process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                            stdout=self.stream, stderr=subprocess.STDOUT, **options)
            if os.name == "nt":
                self._attach_windows_job()
            if input_text is not None:
                self.process.stdin.write(input_text.encode("utf-8"))
            self.process.stdin.close()
        except BaseException:
            if hasattr(self, "process") and self.process.poll() is None:
                self.process.kill()
                self.process.wait(timeout=10)
            self.stream.close()
            raise

    def _attach_windows_job(self):
        from ctypes import wintypes

        class BasicLimits(ctypes.Structure):
            _fields_ = [("ProcessTime", ctypes.c_longlong), ("JobTime", ctypes.c_longlong),
                        ("LimitFlags", wintypes.DWORD), ("MinWorkingSet", ctypes.c_size_t),
                        ("MaxWorkingSet", ctypes.c_size_t), ("ActiveProcesses", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("Priority", wintypes.DWORD),
                        ("Scheduling", wintypes.DWORD)]

        class IOCounts(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in
                        ("Reads", "Writes", "Other", "ReadBytes", "WriteBytes", "OtherBytes")]

        class Limits(ctypes.Structure):
            _fields_ = [("Basic", BasicLimits), ("IO", IOCounts), ("ProcessMemory", ctypes.c_size_t),
                        ("JobMemory", ctypes.c_size_t), ("PeakProcess", ctypes.c_size_t),
                        ("PeakJob", ctypes.c_size_t)]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                                   wintypes.DWORD]
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        job = kernel.CreateJobObjectW(None, None)
        if not job:
            raise OSError("cannot create owned Windows job object")
        limits = Limits()
        limits.Basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if (not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)) or
                not kernel.AssignProcessToJobObject(job, wintypes.HANDLE(int(self.process._handle)))):
            kernel.CloseHandle(job)
            raise OSError("cannot isolate Windows descendants; refuse an unbounded fallback")
        self.job = (kernel, job)

    def stop(self):
        if self.job:
            kernel, handle = self.job
            kernel.TerminateJobObject(handle, 1)
        else:
            # The group was created by us. Even when the leader exited, its
            # surviving descendants must not remain after the worker finishes.
            try:
                os.killpg(self.process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=10)

    def close(self):
        self.stop()
        if self.job:
            kernel, handle = self.job
            kernel.CloseHandle(handle)
            self.job = None
        self.stream.close()


def run_bounded(argv: list[str], *, cwd: Path, env: dict[str, str], output: Path,
                timeout_seconds: float, heartbeat: Callable[[], bool], input_text: str | None = None,
                heartbeat_interval: float = 15, poll_interval: float = 0.25,
                max_output_bytes: int = 64 * 1024 * 1024) -> ProcessResult:
    """Fail closed on OFF, revoked lease, unreachable controller, or timeout."""
    if timeout_seconds <= 0 or heartbeat_interval <= 0:
        raise ValueError("positive execution bounds are required")
    if not heartbeat():
        return ProcessResult(1, 0, "controller stopped execution before start")
    started = time.monotonic()
    child = OwnedProcess(argv, cwd=cwd, env=env, output=output, input_text=input_text)
    next_heartbeat = started + heartbeat_interval
    reason = None
    try:
        while child.process.poll() is None:
            current = time.monotonic()
            if current - started >= timeout_seconds:
                reason = "bounded execution timeout"
                break
            if output.stat().st_size > max_output_bytes:
                reason = "bounded output storage exceeded"
                break
            if current >= next_heartbeat:
                try:
                    keep_running = heartbeat()
                except Exception:  # noqa: BLE001 - every controller failure must stop the owned child.
                    keep_running = False
                if not keep_running:
                    reason = "controller OFF/STOP, revoked lease, or connection unavailable"
                    break
                next_heartbeat = current + heartbeat_interval
            time.sleep(poll_interval)
        if reason:
            child.stop()
        return ProcessResult(child.process.wait(), time.monotonic() - started, reason)
    finally:
        child.close()
