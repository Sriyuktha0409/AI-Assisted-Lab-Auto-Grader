from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_instructor
from ..models import Assignment, Submission, TestCase, TestResult, User
from ..schemas import (
    AssignmentIn,
    AssignmentInstructorOut,
    AssignmentStats,
    AssignmentStudentOut,
    AssignmentSummary,
    TestCaseStudentOut,
    TestStat,
)
from ..services.grader import CaseSpec, grade

router = APIRouter(prefix="/api/assignments", tags=["assignments"])


def _student_view(a: Assignment) -> AssignmentStudentOut:
    cases = [
        TestCaseStudentOut(name=t.name, is_hidden=True)
        if t.is_hidden
        else TestCaseStudentOut(
            name=t.name, is_hidden=False, stdin=t.stdin, expected_stdout=t.expected_stdout
        )
        for t in a.test_cases
    ]
    return AssignmentStudentOut(
        id=a.id,
        title=a.title,
        description=a.description,
        time_limit_ms=a.time_limit_ms,
        memory_limit_mb=a.memory_limit_mb,
        created_at=a.created_at,
        test_cases=cases,
    )


def _get_or_404(db: Session, assignment_id: int) -> Assignment:
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")
    return assignment


@router.get("", response_model=list[AssignmentSummary])
def list_assignments(
    db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> list[Assignment]:
    return list(db.scalars(select(Assignment).order_by(Assignment.created_at.desc())))


@router.post("", response_model=AssignmentInstructorOut, status_code=status.HTTP_201_CREATED)
def create_assignment(
    body: AssignmentIn,
    db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor),
) -> Assignment:
    # A reference solution that fails its own tests would silently grade every student
    # wrong, so verify it before saving.
    if body.reference_solution:
        specs = [
            CaseSpec(i, t.name, t.stdin, t.expected_stdout, t.is_hidden)
            for i, t in enumerate(body.test_cases)
        ]
        outcome = grade(body.reference_solution, specs, body.time_limit_ms, body.memory_limit_mb)
        if not outcome.compile.ok:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Reference solution does not compile: {outcome.compile.error[:300]}",
            )
        failed = outcome.first_failure
        if failed is not None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Reference solution fails test '{failed.spec.name}' ({failed.verdict})",
            )

    assignment = Assignment(
        title=body.title.strip(),
        description=body.description,
        created_by=instructor.id,
        reference_solution=body.reference_solution,
        time_limit_ms=body.time_limit_ms,
        memory_limit_mb=body.memory_limit_mb,
        test_cases=[TestCase(**t.model_dump()) for t in body.test_cases],
    )
    db.add(assignment)
    db.commit()
    return assignment


@router.get("/{assignment_id}")
def get_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AssignmentStudentOut | AssignmentInstructorOut:
    assignment = _get_or_404(db, assignment_id)
    if user.role == "instructor":
        return AssignmentInstructorOut.model_validate(assignment)
    return _student_view(assignment)


@router.get("/{assignment_id}/stats", response_model=AssignmentStats)
def assignment_stats(
    assignment_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_instructor),
) -> AssignmentStats:
    assignment = _get_or_404(db, assignment_id)

    subs = list(db.scalars(select(Submission).where(Submission.assignment_id == assignment_id)))
    unique = {s.student_id for s in subs}
    accepted = {s.student_id for s in subs if s.status == "accepted"}
    scored = [s.passed / s.total for s in subs if s.total > 0]
    verdicts: dict[str, int] = {}
    for s in subs:
        verdicts[s.status] = verdicts.get(s.status, 0) + 1

    rows = db.execute(
        select(
            TestResult.test_case_id,
            func.count(TestResult.id),
            func.sum(case((TestResult.verdict == "pass", 1), else_=0)),
        )
        .join(Submission, Submission.id == TestResult.submission_id)
        .where(Submission.assignment_id == assignment_id)
        .group_by(TestResult.test_case_id)
    ).all()
    by_case = {case_id: (attempts, passes or 0) for case_id, attempts, passes in rows}

    tests = []
    for t in assignment.test_cases:
        attempts, passes = by_case.get(t.id, (0, 0))
        tests.append(
            TestStat(
                test_name=t.name,
                is_hidden=t.is_hidden,
                attempts=attempts,
                pass_rate=round(passes / attempts, 3) if attempts else 0.0,
            )
        )

    return AssignmentStats(
        assignment_id=assignment_id,
        total_submissions=len(subs),
        unique_students=len(unique),
        students_accepted=len(accepted),
        acceptance_rate=round(len(accepted) / len(unique), 3) if unique else 0.0,
        average_score=round(sum(scored) / len(scored), 3) if scored else 0.0,
        verdict_counts=verdicts,
        tests=tests,
    )
