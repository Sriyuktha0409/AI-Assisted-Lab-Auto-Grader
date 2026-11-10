import shutil

import pytest

from app.sandbox.runner import (
    OUTPUT_LIMIT,
    PASS,
    RUNTIME_ERROR,
    TIMEOUT,
    WRONG_ANSWER,
    DockerSandbox,
    normalize_output,
    outputs_match,
)
from app.services.grader import CaseSpec, grade

pytestmark = pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc not installed")


def spec(stdin="", expected="", name="t", hidden=False):
    return CaseSpec(1, name, stdin, expected, hidden)


def run(code, stdin="", expected="", time_ms=1000, mem_mb=64):
    outcome = grade(code, [spec(stdin, expected)], time_ms, mem_mb)
    return outcome


def test_output_normalisation():
    assert normalize_output("a  \r\nb\n\n\n") == ["a", "b"]
    assert outputs_match("1\n2\n", "1  \n2")
    assert not outputs_match("1\n2\n", "1\n3\n")
    # leading whitespace is significant
    assert not outputs_match("x", " x")


def test_correct_program_passes():
    code = '#include <stdio.h>\nint main(void){puts("hi");return 0;}'
    outcome = run(code, expected="hi\n")
    assert outcome.compile.ok
    assert outcome.all_passed
    assert outcome.cases[0].verdict == PASS


def test_reads_stdin():
    code = '#include <stdio.h>\nint main(void){int a;scanf("%d",&a);printf("%d\\n",a*2);return 0;}'
    assert run(code, stdin="21\n", expected="42\n").all_passed


def test_wrong_answer():
    code = '#include <stdio.h>\nint main(void){puts("nope");return 0;}'
    outcome = run(code, expected="yes\n")
    assert outcome.cases[0].verdict == WRONG_ANSWER
    assert not outcome.all_passed


def test_compile_error_reports_line():
    outcome = run("int main(void){ return 0 }")
    assert not outcome.compile.ok
    assert "main.c:1" in outcome.compile.error
    assert outcome.cases == []


def test_infinite_loop_times_out():
    outcome = run("int main(void){ for(;;){} }", time_ms=300)
    assert outcome.cases[0].verdict == TIMEOUT
    assert outcome.cases[0].duration_ms < 3000


def test_segfault_is_runtime_error():
    outcome = run("int main(void){ int *p = 0; return *p; }")
    assert outcome.cases[0].verdict == RUNTIME_ERROR


def test_nonzero_exit_is_runtime_error():
    assert run("int main(void){ return 3; }").cases[0].verdict == RUNTIME_ERROR


def test_output_flood_is_capped():
    code = '#include <stdio.h>\nint main(void){ for(;;) putchar(\'a\'); }'
    outcome = run(code, time_ms=2000)
    case = outcome.cases[0]
    assert case.verdict == OUTPUT_LIMIT
    assert len(case.stdout) <= 64 * 1024


def test_memory_hog_does_not_pass():
    # Checking malloc's result matters: without a use of the pointer, gcc -O2 deletes the
    # whole allocation and the program would never touch the limit.
    code = (
        "#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n"
        "int main(void){\n"
        "  size_t n = 1024UL*1024*1024;\n"
        "  char *p = malloc(n);\n"
        "  if (!p) return 7;\n"
        "  memset(p, 1, n);\n"
        "  printf(\"%d\\n\", p[n-1]);\n"
        "  return 0;\n"
        "}\n"
    )
    case = run(code, expected="1\n", mem_mb=64).cases[0]
    assert case.verdict == RUNTIME_ERROR  # malloc fails under the address-space limit

    # Same program passes when the limit is generous, proving the limit is what stops it.
    assert run(code, expected="1\n", mem_mb=2048).cases[0].verdict == PASS


def test_each_case_is_independent():
    code = (
        '#include <stdio.h>\nint main(void){int a;scanf("%d",&a);'
        'if(a==2){int*p=0;return *p;}printf("%d\\n",a);return 0;}'
    )
    specs = [
        CaseSpec(1, "one", "1\n", "1\n", False),
        CaseSpec(2, "two", "2\n", "2\n", False),
        CaseSpec(3, "three", "3\n", "3\n", False),
    ]
    outcome = grade(code, specs, 1000, 64)
    assert [c.verdict for c in outcome.cases] == [PASS, RUNTIME_ERROR, PASS]
    assert outcome.passed == 2


def test_workdir_is_cleaned_up():
    from app.sandbox.runner import LocalSandbox

    sandbox = LocalSandbox()
    seen = {}
    original = sandbox.workdir

    def tracking():
        seen["dir"] = original()
        return seen["dir"]

    sandbox.workdir = tracking
    grade("int main(void){return 0;}", [spec()], 1000, 64, sandbox=sandbox)
    assert not seen["dir"].exists()


def test_docker_command_is_locked_down(tmp_path):
    """Docker itself is not required: we only assert the flags we pass to it."""
    from app.config import Settings

    sandbox = DockerSandbox(Settings(sandbox_image="gcc:13"))
    args = sandbox._base_args("name", tmp_path, "ro")
    joined = " ".join(args)
    assert "--network none" in joined
    assert "--cap-drop ALL" in joined
    assert "no-new-privileges" in joined
    assert "--pids-limit" in joined
    assert "--user 65534:65534" in joined
    assert f"{tmp_path}:/work:ro" in joined
