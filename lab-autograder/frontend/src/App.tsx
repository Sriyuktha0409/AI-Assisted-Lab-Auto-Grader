import { Route, Routes } from "react-router-dom";
import { Layout, RequireAuth } from "./components/Layout";
import { AssignmentDetail } from "./pages/AssignmentDetail";
import { Assignments } from "./pages/Assignments";
import { Login } from "./pages/Login";
import { NewAssignment } from "./pages/NewAssignment";
import { Stats } from "./pages/Stats";
import { Submissions } from "./pages/Submissions";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Assignments />
            </RequireAuth>
          }
        />
        <Route
          path="/assignments/new"
          element={
            <RequireAuth role="instructor">
              <NewAssignment />
            </RequireAuth>
          }
        />
        <Route
          path="/assignments/:id"
          element={
            <RequireAuth>
              <AssignmentDetail />
            </RequireAuth>
          }
        />
        <Route
          path="/assignments/:id/stats"
          element={
            <RequireAuth role="instructor">
              <Stats />
            </RequireAuth>
          }
        />
        <Route
          path="/submissions"
          element={
            <RequireAuth role="student">
              <Submissions />
            </RequireAuth>
          }
        />
        <Route path="*" element={<p className="muted">Page not found.</p>} />
      </Route>
    </Routes>
  );
}
