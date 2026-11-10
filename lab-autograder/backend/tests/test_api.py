import pytest

from app.config import get_settings
from app.services import hints as hints_module

from .conftest import SUM_SOLUTION, SUM_TESTS

WRONG = (
    '#include <stdio.h>\n'
    'int main(void){int a,b;scanf("%d %d",&a,&b);printf("%d\\n",a-b);return 0;}'
)
BROKEN = "int main(void){ return 0 }"
LOOP = "int main(void){ for(;;){} }"


def submit(client, headers, assignment_id, code):
    return client.post(
        f"/api/assignments/{assignment_id}/submissions", headers=headers, json={"code": code}
    )


# ---------- assignments ----------
def test_requires_authentication(client, assignment):
    assert client.get("/api/assignments").status_code == 401
    assert client.get(f"/api/assignments/{assignment['id']}").status_code == 401


def test_student_cannot_create_assignment(client, student_headers):
    resp = client.post(
        "/api/assignments",
        headers=student_headers,
        json={
            "title": "x",
            "description": "y",
            "test_cases": [{"name": "a", "stdin": "", "expected_stdout": ""}],
        },
    )
    assert resp.status_code == 403


def test_assignment_needs_at_least_one_test(client, instructor_headers):
    resp = client.post(
        "/api/assignments",
        headers=instructor_headers,
        json={"title": "x", "description": "y", "test_cases": []},
    )
    assert resp.status_code == 422


def test_reference_solution_must_pass_its_own_tests(client, instructor_headers):
    resp = client.post(
        "/api/assignments",
        headers=instructor_headers,
        json={
            "title": "Bad reference",
            "description": "d",
            "reference_solution": WRONG,
            "test_cases": SUM_TESTS,
        },
    )
    assert resp.status_code == 422
    assert "fails test" in resp.json()["detail"]


def test_reference_solution_must_compile(client, instructor_headers):
    resp = client.post(
        "/api/assignments",
        headers=instructor_headers,
        json={
            "title": "Bad reference",
            "description": "d",
            "reference_solution": BROKEN,
            "test_cases": SUM_TESTS,
        },
    )
    assert resp.status_code == 422
    assert "does not compile" in resp.json()["detail"]


def test_students_never_see_hidden_tests_or_reference(client, assignment, student_headers):
    resp = client.get(f"/api/assignments/{assignment['id']}", headers=student_headers)
    body = resp.json()
    assert "reference_solution" not in body
    by_name = {t["name"]: t for t in body["test_cases"]}
    assert by_name["small"]["expected_stdout"] == "5\n"
    assert by_name["big"]["is_hidden"] is True
    assert by_name["big"]["expected_stdout"] is None
    assert by_name["big"]["stdin"] is None


def test_instructor_sees_everything(client, assignment, instructor_headers):
    body = client.get(f"/api/assignments/{assignment['id']}", headers=instructor_headers).json()
    assert body["reference_solution"] == SUM_SOLUTION
    assert {t["name"]: t["expected_stdout"] for t in body["test_cases"]}["big"] == "3000000\n"


def test_unknown_assignment_404(client, student_headers):
    assert client.get("/api/assignments/999", headers=student_headers).status_code == 404


# ---------- submissions ----------
def test_accepted_submission(client, assignment, student_headers):
    resp = submit(client, student_headers, assignment["id"], SUM_SOLUTION)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "accepted"
    assert (body["passed"], body["total"]) == (3, 3)
    assert body["hint"] is None


def test_wrong_answer_gets_validated_hint(client, assignment, student_headers):
    body = submit(client, student_headers, assignment["id"], WRONG).json()
    assert body["status"] == "failed"
    assert body["passed"] < body["total"]
    assert body["hint"]
    assert body["hint_source"] == "rule"  # no API key in tests
    assert "scanf" not in body["hint"]


def test_compile_error_submission(client, assignment, student_headers):
    body = submit(client, student_headers, assignment["id"], BROKEN).json()
    assert body["status"] == "compile_error"
    assert body["compile_error"]
    assert body["results"] == []
    assert body["hint"]


def test_timeout_submission(client, assignment, student_headers):
    body = submit(client, student_headers, assignment["id"], LOOP).json()
    assert body["status"] == "failed"
    assert {r["verdict"] for r in body["results"]} == {"timeout"}


def test_hidden_test_details_are_not_leaked_to_students(client, assignment, student_headers):
    body = submit(client, student_headers, assignment["id"], WRONG).json()
    hidden = next(r for r in body["results"] if r["is_hidden"])
    assert hidden["verdict"] == "wrong_answer"  # verdict is visible
    assert hidden["actual_stdout"] is None
    assert hidden["expected_stdout"] is None
    assert hidden["stderr"] is None
    visible = next(r for r in body["results"] if not r["is_hidden"])
    assert visible["expected_stdout"] is not None


def test_instructor_can_see_hidden_details(client, assignment, student_headers, instructor_headers):
    sub_id = submit(client, student_headers, assignment["id"], WRONG).json()["id"]
    body = client.get(f"/api/submissions/{sub_id}", headers=instructor_headers).json()
    hidden = next(r for r in body["results"] if r["is_hidden"])
    assert hidden["expected_stdout"] == "3000000\n"


def test_students_cannot_read_each_others_submissions(
    client, assignment, student_headers, other_student_headers
):
    sub_id = submit(client, student_headers, assignment["id"], SUM_SOLUTION).json()["id"]
    assert client.get(f"/api/submissions/{sub_id}", headers=student_headers).status_code == 200
    assert (
        client.get(f"/api/submissions/{sub_id}", headers=other_student_headers).status_code == 404
    )


def test_submission_list_is_scoped_to_the_student(
    client, assignment, student_headers, other_student_headers
):
    submit(client, student_headers, assignment["id"], SUM_SOLUTION)
    submit(client, other_student_headers, assignment["id"], WRONG)
    mine = client.get("/api/submissions", headers=student_headers).json()
    assert len(mine) == 1 and mine[0]["status"] == "accepted"


def test_instructor_cannot_submit(client, assignment, instructor_headers):
    assert submit(client, instructor_headers, assignment["id"], SUM_SOLUTION).status_code == 403


def test_oversized_code_rejected(client, assignment, student_headers):
    huge = "/*" + "a" * (get_settings().max_code_bytes + 10) + "*/"
    assert submit(client, student_headers, assignment["id"], huge).status_code == 413


def test_submit_to_unknown_assignment(client, student_headers):
    assert submit(client, student_headers, 999, SUM_SOLUTION).status_code == 404


def test_rate_limit(client, assignment, student_headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "submissions_per_minute", 2)
    assert submit(client, student_headers, assignment["id"], BROKEN).status_code == 201
    assert submit(client, student_headers, assignment["id"], BROKEN).status_code == 201
    assert submit(client, student_headers, assignment["id"], BROKEN).status_code == 429


def test_hidden_expectations_never_reach_the_llm(
    client, assignment, student_headers, monkeypatch
):
    class Recorder:
        def __init__(self):
            self.prompts = []

        def complete(self, system, user):
            self.prompts.append(user)
            return "Your output does not match the expected result; check the logic."

    recorder = Recorder()
    monkeypatch.setattr(hints_module, "get_llm_client", lambda *a, **k: recorder)

    # Passes the two visible tests, fails only the hidden one.
    only_hidden_fails = (
        '#include <stdio.h>\nint main(void){int a,b;scanf("%d %d",&a,&b);'
        'printf("%d\\n", a>100 ? a+b+1 : a+b);return 0;}'
    )
    body = submit(client, student_headers, assignment["id"], only_hidden_fails).json()
    assert body["hint_source"] == "llm"
    prompt = recorder.prompts[0]
    assert "3000000" not in prompt
    assert "Expected output" not in prompt


# ---------- stats ----------
def test_stats_for_instructor(
    client, assignment, student_headers, other_student_headers, instructor_headers
):
    submit(client, student_headers, assignment["id"], WRONG)
    submit(client, student_headers, assignment["id"], SUM_SOLUTION)
    submit(client, other_student_headers, assignment["id"], BROKEN)

    stats = client.get(f"/api/assignments/{assignment['id']}/stats", headers=instructor_headers)
    body = stats.json()
    assert body["total_submissions"] == 3
    assert body["unique_students"] == 2
    assert body["students_accepted"] == 1
    assert body["acceptance_rate"] == 0.5
    assert body["verdict_counts"] == {"failed": 1, "accepted": 1, "compile_error": 1}
    assert {t["test_name"] for t in body["tests"]} == {"small", "negative", "big"}
    assert all(t["attempts"] == 2 for t in body["tests"])  # compile error ran no tests


def test_stats_empty_assignment(client, assignment, instructor_headers):
    body = client.get(
        f"/api/assignments/{assignment['id']}/stats", headers=instructor_headers
    ).json()
    assert body["total_submissions"] == 0
    assert body["acceptance_rate"] == 0.0


def test_stats_forbidden_for_students(client, assignment, student_headers):
    resp = client.get(f"/api/assignments/{assignment['id']}/stats", headers=student_headers)
    assert resp.status_code == 403


@pytest.mark.parametrize("path", ["/api/health"])
def test_health(client, path):
    assert client.get(path).json() == {"status": "ok"}
