from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import get_current_user, require_student
from ..models import Assignment, Submission, TestResult, User, utcnow
from ..schemas import SubmissionIn, SubmissionOut, SubmissionSummary, TestResultOut
from ..services.grader import CaseSpec, GradeOutcome, grade
from ..services.hints import HintContext, generate_hint

router = APIRouter(prefix="/api", tags=["submissions"])


def _to_out(sub: Submission, viewer: User, expected_by_case: dict[int, str]) -> SubmissionOut:
    """Hidden test details (expected output, actual output, stderr) go to instructors only."""
    is_instructor = viewer.role == "instructor"
    results = []
    for r in sub.results:
        reveal = is_instructor or not r.is_hidden
        results.append(
            TestResultOut(
                test_name=r.test_name,
                verdict=r.verdict,
                is_hidden=r.is_hidden,
                duration_ms=r.duration_ms,
                actual_stdout=r.actual_stdout if reveal else None,
                expected_stdout=expected_by_case.get(r.test_case_id) if reveal else None,
                stderr=r.stderr if reveal else None,
            )
        )
    return SubmissionOut(
        id=sub.id,
        assignment_id=sub.assignment_id,
        status=sub.status,
        passed=sub.passed,
        total=sub.total,
        created_at=sub.created_at,
        code=sub.code,
        compile_error=sub.compile_error,
        hint=sub.hint,
        hint_source=sub.hint_source,
        results=results,
    )


def _expected_map(db: Session, assignment_id: int) -> dict[int, str]:
    assignment = db.get(Assignment, assignment_id)
    return {t.id: t.expected_stdout for t in assignment.test_cases} if assignment else {}


def _hint_context(assignment: Assignment, code: str, outcome: GradeOutcome) -> HintContext:
    if not outcome.compile.ok:
        return HintContext(
            assignment_title=assignment.title,
            assignment_description=assignment.description,
            failure_kind="compile_error",
            student_code=code,
            compile_error=outcome.compile.error,
        )
    failure = outcome.first_failure
    assert failure is not None
    ctx = HintContext(
        assignment_title=assignment.title,
        assignment_description=assignment.description,
        failure_kind=failure.verdict,
        student_code=code,
        failing_test=failure.spec.name,
    )
    if not failure.spec.is_hidden:  # never send hidden expectations to a third party
        ctx.expected_output = failure.spec.expected_stdout
        ctx.actual_output = failure.stdout
    return ctx


@router.post(
    "/assignments/{assignment_id}/submissions",
    response_model=SubmissionOut,
    status_code=status.HTTP_201_CREATED,
)
def submit(
    assignment_id: int,
    body: SubmissionIn,
    db: Session = Depends(get_db),
    student: User = Depends(require_student),
) -> SubmissionOut:
    settings = get_settings()
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")

    if len(body.code.encode()) > settings.max_code_bytes:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"Code exceeds {settings.max_code_bytes} bytes",
        )

    recent = db.scalar(
        select(func.count(Submission.id)).where(
            Submission.student_id == student.id,
            Submission.created_at >= utcnow() - timedelta(minutes=1),
        )
    )
    if recent >= settings.submissions_per_minute:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many submissions. Wait a minute and retry."
        )

    specs = [
        CaseSpec(t.id, t.name, t.stdin, t.expected_stdout, t.is_hidden)
        for t in assignment.test_cases
    ]
    outcome = grade(body.code, specs, assignment.time_limit_ms, assignment.memory_limit_mb)

    if not outcome.compile.ok:
        sub_status = "compile_error"
    elif outcome.all_passed:
        sub_status = "accepted"
    else:
        sub_status = "failed"

    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        code=body.code,
        status=sub_status,
        passed=outcome.passed,
        total=len(specs),
        compile_error=None if outcome.compile.ok else outcome.compile.error,
        results=[
            TestResult(
                test_case_id=c.spec.id,
                test_name=c.spec.name,
                verdict=c.verdict,
                actual_stdout=c.stdout,
                stderr=c.stderr,
                duration_ms=c.duration_ms,
                is_hidden=c.spec.is_hidden,
            )
            for c in outcome.cases
        ],
    )

    if sub_status != "accepted":
        hint = generate_hint(
            _hint_context(assignment, body.code, outcome), assignment.reference_solution
        )
        submission.hint, submission.hint_source = hint.text, hint.source

    db.add(submission)
    db.commit()
    return _to_out(submission, student, _expected_map(db, assignment.id))


@router.get("/submissions", response_model=list[SubmissionSummary])
def list_submissions(
    assignment_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Submission]:
    query = select(Submission).order_by(Submission.created_at.desc()).limit(200)
    if user.role != "instructor":
        query = query.where(Submission.student_id == user.id)
    if assignment_id is not None:
        query = query.where(Submission.assignment_id == assignment_id)
    return list(db.scalars(query))


@router.get("/submissions/{submission_id}", response_model=SubmissionOut)
def get_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubmissionOut:
    sub = db.get(Submission, submission_id)
    # 404 (not 403) for other students' submissions so ids cannot be probed.
    if sub is None or (user.role != "instructor" and sub.student_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")
    return _to_out(sub, user, _expected_map(db, sub.assignment_id))
