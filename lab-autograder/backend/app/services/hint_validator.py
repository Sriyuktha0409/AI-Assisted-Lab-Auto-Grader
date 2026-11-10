"""Validate AI-generated hints before a student sees them.

An LLM hint is untrusted output. It may leak a full solution, wander off topic,
or have been steered by instructions hidden in the student's code. A hint is
shown only if every check below passes.
"""

from __future__ import annotations

import re

MAX_WORDS = 120
MAX_CODE_LIKE_LINES = 2
SHINGLE_SIZE = 8  # this many consecutive tokens shared with the reference = leak

# A hint must talk about the actual failure. At least one keyword must appear.
TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "compile_error": (
        "compile", "compiler", "syntax", "declar", "semicolon", "type", "include", "line",
    ),
    "wrong_answer": (
        "output", "expected", "result", "case", "logic", "check", "format", "condition",
    ),
    "timeout": ("loop", "time", "slow", "complex", "terminat", "efficient", "iteration"),
    "runtime_error": (
        "crash", "segment", "pointer", "bounds", "index", "memory", "null", "array", "uninitial",
    ),
    "output_limit": ("output", "print", "loop", "infinite", "terminat"),
}  # fmt: skip

_TOKEN_RE = re.compile(r"[A-Za-z_]\w*|\d+|==|!=|<=|>=|&&|\|\||[^\s\w]")
_FENCE_RE = re.compile(r"```")
_CODE_LINE_RE = re.compile(r"(;\s*$)|(^\s*[{}]\s*$)|(\)\s*\{\s*$)")


def tokenize(code: str) -> list[str]:
    return _TOKEN_RE.findall(code)


def _shingles(tokens: list[str], size: int) -> set[tuple[str, ...]]:
    return {tuple(tokens[i : i + size]) for i in range(len(tokens) - size + 1)}


def leaks_reference(text: str, reference_solution: str | None) -> bool:
    if not reference_solution:
        return False
    ref = tokenize(reference_solution)
    hint = tokenize(text)
    if len(ref) < SHINGLE_SIZE or len(hint) < SHINGLE_SIZE:
        return False
    return bool(_shingles(ref, SHINGLE_SIZE) & _shingles(hint, SHINGLE_SIZE))


def validate_hint(
    text: str, failure_kind: str, reference_solution: str | None = None
) -> list[str]:
    """Return a list of rejection reasons. Empty list means the hint is acceptable."""
    reasons: list[str] = []
    stripped = text.strip()
    if not stripped:
        return ["empty hint"]

    if len(stripped.split()) > MAX_WORDS:
        reasons.append(f"longer than {MAX_WORDS} words")

    if _FENCE_RE.search(stripped):
        reasons.append("contains a fenced code block")

    code_like = sum(1 for line in stripped.splitlines() if _CODE_LINE_RE.search(line))
    if code_like > MAX_CODE_LIKE_LINES:
        reasons.append("contains too many lines that look like code")

    if leaks_reference(stripped, reference_solution):
        reasons.append("overlaps with the reference solution")

    keywords = TOPIC_KEYWORDS.get(failure_kind, ())
    lowered = stripped.lower()
    if keywords and not any(k in lowered for k in keywords):
        reasons.append("does not address the observed failure")

    return reasons
