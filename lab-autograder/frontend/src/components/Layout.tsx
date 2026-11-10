import { Link, Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth";
import type { Role } from "../api";

export function Layout() {
  const { user, logout } = useAuth();
  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">
          Lab Auto-Grader
        </Link>
        {user && (
          <nav className="row">
            <Link to="/">Assignments</Link>
            {user.role === "student" && <Link to="/submissions">My submissions</Link>}
            {user.role === "instructor" && <Link to="/assignments/new">New assignment</Link>}
            <span className="muted">
              {user.name} ({user.role})
            </span>
            <button type="button" className="link" onClick={logout}>
              Sign out
            </button>
          </nav>
        )}
      </header>
      <main className="container">
        <Outlet />
      </main>
    </>
  );
}

export function RequireAuth({ role, children }: { role?: Role; children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="muted">Loading…</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (role && user.role !== role) {
    return <p className="error-text">You do not have access to this page.</p>;
  }
  return <>{children}</>;
}
