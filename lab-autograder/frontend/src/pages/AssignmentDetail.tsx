import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import type { Submission } from "../api";
import { ResultPanel } from "../components/ResultPanel";
import { useAuth } from "../auth";
import { formatDate, statusLabel, STARTER_CODE } from "../format";
import { messageOf, useLoad } from "../hooks";

function draftKey(assignmentId: number): string {
  return `autograder.draft.${assignmentId}`;
}

function loadDraft(assignmentId: number): string {
  try {
    return localStorage.getItem(draftKey(assignmentId)) ?? STARTER_CODE;
  } catch {
    return STARTER_CODE;
  }
}

function saveDraft(assignmentId: number, code: string): void {
  try {
    localStorage.setItem(draftKey(assignmentId), code);
  } catch {
    /* drafts are a convenience only */
  }
}

export function AssignmentDetail() {
  const { id } = useParams();
  const assignmentId = Number(id);
  const { user } = useAuth();
  const assignment = useLoad(() => api.getAssignment(assignmentId), [assignmentId]);
  const history = useLoad(
    () => (user?.role === "student" ? api.listSubmissions(assignmentId) : Promise.resolve([])),
    [assignmentId, user?.role],
  );

  const [code, setCode] = useState(() => loadDraft(assignmentId));
  const [result, setResult] = useState<Submission | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    saveDraft(assignmentId, code);
  }, [assignmentId, code]);

  async function onSubmit() {
    setBusy(true);
    setSubmitError(null);
    try {
      setResult(await api.submit(assignmentId, code));
      history.reload();
    } catch (err) {
      setSubmitError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  async function openPast(submissionId: number) {
    try {
      const past = await api.getSubmission(submissionId);
      setResult(past);
      setCode(past.code);
    } catch (err) {
      setSubmitError(messageOf(err));
    }
  }

  if (assignment.loading) return <p className="muted">Loading…</p>;
  if (assignment.error || !assignment.data) {
    return (
      <p role="alert" className="error-text">
        {assignment.error ?? "Assignment not found"}
      </p>
    );
  }
  const a = assignment.data;
  const isInstructor = user?.role === "instructor";

  return (
    <>
      <div className="row between">
        <h1>{a.title}</h1>
        {isInstructor && <Link to={`/assignments/${a.id}/stats`}>View statistics</Link>}
      </div>
      <p className="muted">
        Limits: {a.time_limit_ms} ms, {a.memory_limit_mb} MB
      </p>
      <p className="prewrap">{a.description}</p>

      <h2>Sample tests</h2>
      <ul className="tests">
        {a.test_cases.map((t) => (
          <li key={t.name}>
            <strong>{t.name}</strong>
            {t.is_hidden && !isInstructor ? (
              <span className="tag">hidden</span>
            ) : (
              <div className="diff">
                <div>
                  <small>Input</small>
                  <pre className="code">{t.stdin ?? ""}</pre>
                </div>
                <div>
                  <small>Expected output</small>
                  <pre className="code">{t.expected_stdout ?? ""}</pre>
                </div>
              </div>
            )}
            {t.is_hidden && isInstructor && <span className="tag">hidden from students</span>}
          </li>
        ))}
      </ul>

      {isInstructor && a.reference_solution && (
        <>
          <h2>Reference solution</h2>
          <pre className="code">{a.reference_solution}</pre>
        </>
      )}

      {user?.role === "student" && (
        <>
          <h2>Your solution (C)</h2>
          <label className="sr-only" htmlFor="code">
            Source code
          </label>
          <textarea
            id="code"
            className="editor"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            spellCheck={false}
            rows={18}
          />
          <div className="row">
            <button type="button" onClick={onSubmit} disabled={busy || code.trim() === ""}>
              {busy ? "Grading…" : "Submit"}
            </button>
            {submitError && (
              <span role="alert" className="error-text">
                {submitError}
              </span>
            )}
          </div>

          {result && <ResultPanel submission={result} />}

          {history.data && history.data.length > 0 && (
            <>
              <h2>Previous attempts</h2>
              <table>
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Status</th>
                    <th>Score</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {history.data.map((s) => (
                    <tr key={s.id}>
                      <td>{formatDate(s.created_at)}</td>
                      <td>{statusLabel(s.status)}</td>
                      <td>
                        {s.passed}/{s.total}
                      </td>
                      <td>
                        <button type="button" className="link" onClick={() => openPast(s.id)}>
                          Open
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </>
      )}
    </>
  );
}
