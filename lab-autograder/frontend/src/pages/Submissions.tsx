import { Link } from "react-router-dom";
import { api } from "../api";
import { formatDate, statusLabel } from "../format";
import { useLoad } from "../hooks";

export function Submissions() {
  const { data, error, loading } = useLoad(() => api.listSubmissions(), []);
  return (
    <>
      <h1>My submissions</h1>
      {loading && <p className="muted">Loading…</p>}
      {error && (
        <p role="alert" className="error-text">
          {error}
        </p>
      )}
      {data && data.length === 0 && <p className="muted">You have not submitted anything yet.</p>}
      {data && data.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>When</th>
              <th>Assignment</th>
              <th>Status</th>
              <th>Score</th>
            </tr>
          </thead>
          <tbody>
            {data.map((s) => (
              <tr key={s.id}>
                <td>{formatDate(s.created_at)}</td>
                <td>
                  <Link to={`/assignments/${s.assignment_id}`}>#{s.assignment_id}</Link>
                </td>
                <td>{statusLabel(s.status)}</td>
                <td>
                  {s.passed}/{s.total}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
