import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { formatDate } from "../format";
import { useLoad } from "../hooks";

export function Assignments() {
  const { user } = useAuth();
  const { data, error, loading } = useLoad(() => api.listAssignments(), []);

  return (
    <>
      <div className="row between">
        <h1>Assignments</h1>
        {user?.role === "instructor" && <Link to="/assignments/new">New assignment</Link>}
      </div>
      {loading && <p className="muted">Loading…</p>}
      {error && (
        <p role="alert" className="error-text">
          {error}
        </p>
      )}
      {data && data.length === 0 && <p className="muted">No assignments yet.</p>}
      {data && data.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Title</th>
              <th>Limits</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {data.map((a) => (
              <tr key={a.id}>
                <td>
                  <Link to={`/assignments/${a.id}`}>{a.title}</Link>
                </td>
                <td>
                  {a.time_limit_ms} ms · {a.memory_limit_mb} MB
                </td>
                <td>{formatDate(a.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
