import os
import tempfile

# Settings are read at import time, so configure the environment first.
_tmp = tempfile.mkdtemp(prefix="autograder-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-hs256"
os.environ["INSTRUCTOR_INVITE_CODE"] = "invite-123"
os.environ["SANDBOX_MODE"] = "local"
os.environ["ANTHROPIC_API_KEY"] = ""  # tests must never call a real LLM

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

SUM_SOLUTION = """
#include <stdio.h>
int main(void) {
    int a, b;
    if (scanf("%d %d", &a, &b) != 2) return 1;
    printf("%d\\n", a + b);
    return 0;
}
"""

SUM_TESTS = [
    {"name": "small", "stdin": "2 3\n", "expected_stdout": "5\n", "is_hidden": False},
    {"name": "negative", "stdin": "-4 1\n", "expected_stdout": "-3\n", "is_hidden": False},
    {
        "name": "big",
        "stdin": "1000000 2000000\n",
        "expected_stdout": "3000000\n",
        "is_hidden": True,
    },
]


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _register(client, email, role="student", invite=None):
    body = {"email": email, "name": email.split("@")[0], "password": "password123", "role": role}
    if invite:
        body["invite_code"] = invite
    resp = client.post("/api/auth/register", json=body)
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def student_headers(client):
    return _register(client, "alice@example.com")


@pytest.fixture
def other_student_headers(client):
    return _register(client, "bob@example.com")


@pytest.fixture
def instructor_headers(client):
    return _register(client, "prof@example.com", role="instructor", invite="invite-123")


@pytest.fixture
def assignment(client, instructor_headers):
    resp = client.post(
        "/api/assignments",
        headers=instructor_headers,
        json={
            "title": "Sum of two integers",
            "description": "Read two integers and print their sum.",
            "time_limit_ms": 1000,
            "memory_limit_mb": 64,
            "reference_solution": SUM_SOLUTION,
            "test_cases": SUM_TESTS,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()
