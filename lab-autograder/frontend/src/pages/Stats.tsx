import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { percent, statusLabel } from "../format";
import { useLoad } from "../hooks";

export function Stats() {
  const { id } = useParams();
  const assignmentId = Number(id);
  const { data, error, loading } = useLoad(() => api.assignmentStats(assignmentId), [assignmentId]);

  if (loading) return <p className="muted">Loading…</p>;
  if (error || !data) {
    return (
      <p role="alert" className="error-text">
        {error ?? "No data"}
      </p>
    );
  }

  return (
    <>
      <p>
        <Link to={`/assignments/${assignmentId}`}>← Back to assignment</Link>
      </p>
      <h1>Statistics</h1>
      <div className="cards">
        <div className="card">
          <span className="muted">Submissions</span>
          <strong>{data.total_submissions}</strong>
        </div>
        <div className="card">
          <span className="muted">Students</span>
          <strong>{data.unique_students}</strong>
        </div>
        <div className="card">
          <span className="muted">Accepted</span>
          <strong>
            {data.students_accepted} ({percent(data.acceptance_rate)})
          </strong>
        </div>
        <div className="card">
          <span className="muted">Average score</span>
          <strong>{percent(data.average_score)}</strong>
        </div>
      </div>

      <h2>Outcomes</h2>
      {Object.keys(data.verdict_counts).length === 0 ? (
        <p className="muted">No submissions yet.</p>
      ) : (
        <ul>
          {Object.entries(data.verdict_counts).map(([status, count]) => (
            <li key={status}>
              {statusLabel(status)}: {count}
            </li>
          ))}
        </ul>
      )}

      <h2>Pass rate by test</h2>
      <table>
        <thead>
          <tr>
            <th>Test</th>
            <th>Attempts</th>
            <th>Pass rate</th>
          </tr>
        </thead>
        <tbody>
          {data.tests.map((t) => (
            <tr key={t.test_name}>
              <td>
                {t.test_name}
                {t.is_hidden && <span className="tag">hidden</span>}
              </td>
              <td>{t.attempts}</td>
              <td>
                <div className="bar" aria-hidden="true">
                  <div style={{ width: percent(t.pass_rate) }} />
                </div>
                {percent(t.pass_rate)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
