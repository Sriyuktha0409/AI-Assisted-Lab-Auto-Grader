from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- auth ----------
class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    role: Literal["student", "instructor"] = "student"
    invite_code: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(ORM):
    id: int
    email: str
    name: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- assignments ----------
class TestCaseIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    stdin: str = Field(default="", max_length=10_000)
    expected_stdout: str = Field(max_length=10_000)
    is_hidden: bool = False


class AssignmentIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)
    time_limit_ms: int = Field(default=2000, ge=100, le=10_000)
    memory_limit_mb: int = Field(default=128, ge=16, le=512)
    reference_solution: str | None = Field(default=None, max_length=20_000)
    test_cases: list[TestCaseIn] = Field(min_length=1, max_length=50)


class TestCaseStudentOut(BaseModel):
    """Hidden cases expose only their name."""

    name: str
    is_hidden: bool
    stdin: str | None = None
    expected_stdout: str | None = None


class TestCaseInstructorOut(ORM):
    id: int
    name: str
    stdin: str
    expected_stdout: str
    is_hidden: bool


class AssignmentSummary(ORM):
    id: int
    title: str
    time_limit_ms: int
    memory_limit_mb: int
    created_at: datetime


class AssignmentStudentOut(AssignmentSummary):
    description: str
    test_cases: list[TestCaseStudentOut]


class AssignmentInstructorOut(AssignmentSummary):
    description: str
    reference_solution: str | None
    test_cases: list[TestCaseInstructorOut]


class TestStat(BaseModel):
    test_name: str
    is_hidden: bool
    attempts: int
    pass_rate: float


class AssignmentStats(BaseModel):
    assignment_id: int
    total_submissions: int
    unique_students: int
    students_accepted: int
    acceptance_rate: float
    average_score: float
    verdict_counts: dict[str, int]
    tests: list[TestStat]


# ---------- submissions ----------
class SubmissionIn(BaseModel):
    code: str = Field(min_length=1)


class TestResultOut(BaseModel):
    test_name: str
    verdict: str
    is_hidden: bool
    duration_ms: int
    actual_stdout: str | None = None
    expected_stdout: str | None = None
    stderr: str | None = None


class SubmissionSummary(ORM):
    id: int
    assignment_id: int
    status: str
    passed: int
    total: int
    created_at: datetime


class SubmissionOut(SubmissionSummary):
    code: str
    compile_error: str | None
    hint: str | None
    hint_source: str | None
    results: list[TestResultOut]
