"""Compile and run untrusted C programs.

Two backends:

* ``DockerSandbox`` (production): every compile and every test run happens in a
  throwaway container with no network, a read-only root filesystem, a memory cap,
  a PID cap, all capabilities dropped, and a hard wall-clock timeout.
* ``LocalSandbox`` (development / CI only): runs the compiled binary directly with
  POSIX resource limits (CPU time, address space, file size) in its own process
  group. This is NOT a security boundary. Never expose it to untrusted users.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..config import Settings, get_settings

PASS = "pass"
WRONG_ANSWER = "wrong_answer"
TIMEOUT = "timeout"
RUNTIME_ERROR = "runtime_error"
OUTPUT_LIMIT = "output_limit"

_STDERR_LIMIT = 4096


@dataclass
class CompileResult:
    ok: bool
    error: str = ""


@dataclass
class RunResult:
    verdict: str  # pass is decided by the caller after comparing output
    stdout: str
    stderr: str
    duration_ms: int
    exit_code: int | None


class Sandbox(Protocol):
    def workdir(self) -> Path: ...

    def compile(self, code: str, workdir: Path) -> CompileResult: ...

    def run(
        self, workdir: Path, stdin: str, time_limit_ms: int, memory_limit_mb: int
    ) -> RunResult: ...


def normalize_output(text: str) -> list[str]:
    """Compare ignoring trailing whitespace on each line and trailing blank lines."""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def outputs_match(expected: str, actual: str) -> bool:
    return normalize_output(expected) == normalize_output(actual)


def _read_capped(path: Path, limit: int) -> str:
    try:
        with open(path, "rb") as fh:
            return fh.read(limit).decode("utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def _classify(returncode: int | None, timed_out: bool, out_size: int, limit: int) -> str:
    if timed_out:
        return TIMEOUT
    if out_size > limit or returncode == -signal.SIGXFSZ:
        return OUTPUT_LIMIT
    if returncode == -signal.SIGXCPU:
        return TIMEOUT
    if returncode not in (0, None):
        return RUNTIME_ERROR
    return PASS  # "ran to completion"; caller compares output


def _kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


class _BaseSandbox:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def workdir(self) -> Path:
        root = self.settings.sandbox_workdir_root or None
        if root:
            Path(root).mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix="grader-", dir=root))

    @staticmethod
    def cleanup(workdir: Path) -> None:
        shutil.rmtree(workdir, ignore_errors=True)

    def _spawn(
        self,
        cmd: list[str],
        workdir: Path,
        stdin: str,
        time_limit_ms: int,
        on_timeout=None,
        cwd: Path | None = None,
    ) -> RunResult:
        """Run ``cmd`` with stdout/stderr redirected to files so output size is bounded."""
        import time

        limit = self.settings.max_output_bytes
        out_path = workdir / f".stdout-{uuid.uuid4().hex}"
        err_path = workdir / f".stderr-{uuid.uuid4().hex}"
        timed_out = False
        start = time.monotonic()
        with open(out_path, "wb") as out_fh, open(err_path, "wb") as err_fh:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=out_fh,
                stderr=err_fh,
                cwd=cwd or workdir,
                env={"PATH": "/usr/bin:/bin"},
                start_new_session=True,
            )
            try:
                proc.communicate(stdin.encode(), timeout=time_limit_ms / 1000)
            except subprocess.TimeoutExpired:
                timed_out = True
                if on_timeout:
                    on_timeout()
                _kill_group(proc)
                proc.communicate()
            except BrokenPipeError:
                proc.wait()
        duration_ms = int((time.monotonic() - start) * 1000)
        out_size = out_path.stat().st_size if out_path.exists() else 0
        verdict = _classify(proc.returncode, timed_out, out_size, limit)
        result = RunResult(
            verdict=verdict,
            stdout=_read_capped(out_path, limit),
            stderr=_read_capped(err_path, _STDERR_LIMIT),
            duration_ms=duration_ms,
            exit_code=proc.returncode,
        )
        out_path.unlink(missing_ok=True)
        err_path.unlink(missing_ok=True)
        return result


class LocalSandbox(_BaseSandbox):
    """Dev/CI backend. Resource limits only, not isolation."""

    def compile(self, code: str, workdir: Path) -> CompileResult:
        src = workdir / "main.c"
        src.write_text(code)
        try:
            proc = subprocess.run(
                ["gcc", "-O2", "-std=c11", "-o", "prog", "main.c", "-lm"],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=self.settings.compile_timeout_s,
                env={"PATH": "/usr/bin:/bin"},
            )
        except subprocess.TimeoutExpired:
            return CompileResult(False, "Compilation timed out.")
        if proc.returncode != 0:
            return CompileResult(False, proc.stderr[:_STDERR_LIMIT])
        return CompileResult(True)

    def run(
        self, workdir: Path, stdin: str, time_limit_ms: int, memory_limit_mb: int
    ) -> RunResult:
        # `prlimit` (util-linux) applies the limits and then execs the program. Unlike
        # subprocess's preexec_fn it is safe to use from a multi-threaded server.
        cpu_seconds = max(1, time_limit_ms // 1000 + 1)
        mem_bytes = memory_limit_mb * 1024 * 1024
        out_limit = self.settings.max_output_bytes
        cmd = [
            "prlimit",
            f"--cpu={cpu_seconds}",
            f"--as={mem_bytes}",
            f"--fsize={out_limit + 1}",
            "--core=0",
            str(workdir / "prog"),
        ]
        return self._spawn(cmd, workdir, stdin, time_limit_ms)


class DockerSandbox(_BaseSandbox):
    """Production backend: each step runs in a locked-down, disposable container."""

    def _base_args(self, name: str, workdir: Path, mount_mode: str) -> list[str]:
        return [
            "docker", "run", "--rm", "--name", name,
            "--network", "none",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", "64",
            "--user", "65534:65534",
            "-v", f"{workdir}:/work:{mount_mode}",
            "-w", "/work",
        ]  # fmt: skip

    def compile(self, code: str, workdir: Path) -> CompileResult:
        (workdir / "main.c").write_text(code)
        os.chmod(workdir, 0o777)  # container runs as nobody and must write ./prog
        name = f"grader-c-{uuid.uuid4().hex[:12]}"
        cmd = self._base_args(name, workdir, "rw") + [
            "--memory", "512m", "--memory-swap", "512m", "--cpus", "1",
            self.settings.sandbox_image,
            "gcc", "-O2", "-std=c11", "-o", "prog", "main.c", "-lm",
        ]  # fmt: skip
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.settings.compile_timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "kill", name], capture_output=True, check=False)
            return CompileResult(False, "Compilation timed out.")
        if proc.returncode != 0:
            return CompileResult(False, proc.stderr[:_STDERR_LIMIT])
        return CompileResult(True)

    def run(
        self, workdir: Path, stdin: str, time_limit_ms: int, memory_limit_mb: int
    ) -> RunResult:
        name = f"grader-r-{uuid.uuid4().hex[:12]}"
        cmd = self._base_args(name, workdir, "ro") + [
            "-i", "--read-only",
            "--memory", f"{memory_limit_mb}m", "--memory-swap", f"{memory_limit_mb}m",
            "--cpus", "1",
            self.settings.sandbox_image,
            "./prog",
        ]  # fmt: skip

        def kill_container() -> None:
            subprocess.run(["docker", "kill", name], capture_output=True, check=False)

        # The `docker run` client gets the output-size limit; the container gets the rest.
        out_limit = self.settings.max_output_bytes
        cmd = ["prlimit", f"--fsize={out_limit + 1}", *cmd]

        # Extra second for container start-up so slow starts are not blamed on students.
        result = self._spawn(cmd, workdir, stdin, time_limit_ms + 1000, on_timeout=kill_container)
        if result.exit_code == 137 and result.verdict == RUNTIME_ERROR:
            result.stderr = (result.stderr + "\nKilled (likely memory limit).").strip()
        return result


def get_sandbox(settings: Settings | None = None) -> _BaseSandbox:
    settings = settings or get_settings()
    if settings.sandbox_mode == "docker":
        return DockerSandbox(settings)
    return LocalSandbox(settings)
