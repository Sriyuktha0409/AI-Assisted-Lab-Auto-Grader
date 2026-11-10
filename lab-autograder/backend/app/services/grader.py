"""Grade one source file against a list of test cases."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..sandbox.runner import (
    PASS,
    WRONG_ANSWER,
    CompileResult,
    RunResult,
    get_sandbox,
    outputs_match,
)


@dataclass
class CaseSpec:
    id: int
    name: str
    stdin: str
    expected_stdout: str
    is_hidden: bool


@dataclass
class CaseOutcome:
    spec: CaseSpec
    verdict: str
    stdout: str
    stderr: str
    duration_ms: int


@dataclass
class GradeOutcome:
    compile: CompileResult
    cases: list[CaseOutcome] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.cases if c.verdict == PASS)

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def all_passed(self) -> bool:
        return self.compile.ok and self.total > 0 and self.passed == self.total

    @property
    def first_failure(self) -> CaseOutcome | None:
        return next((c for c in self.cases if c.verdict != PASS), None)


def _judge(spec: CaseSpec, run: RunResult) -> str:
    if run.verdict != PASS:
        return run.verdict
    return PASS if outputs_match(spec.expected_stdout, run.stdout) else WRONG_ANSWER


def grade(
    code: str,
    specs: list[CaseSpec],
    time_limit_ms: int,
    memory_limit_mb: int,
    sandbox=None,
) -> GradeOutcome:
    sandbox = sandbox or get_sandbox()
    workdir = sandbox.workdir()
    try:
        compiled = sandbox.compile(code, workdir)
        outcome = GradeOutcome(compile=compiled)
        if not compiled.ok:
            return outcome
        for spec in specs:
            run = sandbox.run(workdir, spec.stdin, time_limit_ms, memory_limit_mb)
            outcome.cases.append(
                CaseOutcome(
                    spec=spec,
                    verdict=_judge(spec, run),
                    stdout=run.stdout,
                    stderr=run.stderr,
                    duration_ms=run.duration_ms,
                )
            )
        return outcome
    finally:
        sandbox.cleanup(workdir)
