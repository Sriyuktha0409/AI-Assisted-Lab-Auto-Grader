import type { Submission } from "../api";
import { formatDate, statusLabel, verdictLabel } from "../format";

export function ResultPanel({ submission }: { submission: Submission }) {
  const { status, passed, total, compile_error, hint, hint_source, results } = submission;

  return (
    <section className="panel" aria-label="Submission result">
      <header className="row">
        <span className={`badge badge-${status}`}>{statusLabel(status)}</span>
        {status !== "compile_error" && (
          <strong>
            {passed}/{total} tests passed
          </strong>
        )}
        <span className="muted">{formatDate(submission.created_at)}</span>
      </header>

      {compile_error && (
        <>
          <h4>Compiler output</h4>
          <pre className="code error">{compile_error}</pre>
        </>
      )}

      {hint && (
        <aside className="hint" role="note">
          <strong>{hint_source === "llm" ? "AI-assisted hint" : "Automated hint"}</strong>
          <p>{hint}</p>
          {hint_source === "llm" && (
            <small className="muted">
              Checked automatically so it does not reveal a full solution. It can still be wrong.
            </small>
          )}
        </aside>
      )}

      {results.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Test</th>
              <th>Result</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r) => (
              <tr key={r.test_name}>
                <td>
                  {r.test_name}
                  {r.is_hidden && <span className="tag">hidden</span>}
                </td>
                <td>
                  <span className={r.verdict === "pass" ? "ok" : "bad"}>
                    {verdictLabel(r.verdict)}
                  </span>
                  {r.verdict === "wrong_answer" && r.expected_stdout !== null && (
                    <div className="diff">
                      <div>
                        <small>Expected</small>
                        <pre className="code">{r.expected_stdout}</pre>
                      </div>
                      <div>
                        <small>Your output</small>
                        <pre className="code">{r.actual_stdout ?? ""}</pre>
                      </div>
                    </div>
                  )}
                  {r.stderr && <pre className="code error">{r.stderr}</pre>}
                </td>
                <td>{r.duration_ms} ms</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
