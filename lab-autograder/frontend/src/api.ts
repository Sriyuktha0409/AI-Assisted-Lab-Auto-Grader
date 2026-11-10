export type Role = "student" | "instructor";

export interface User {
  id: number;
  email: string;
  name: string;
  role: Role;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface AssignmentSummary {
  id: number;
  title: string;
  time_limit_ms: number;
  memory_limit_mb: number;
  created_at: string;
}

export interface TestCaseView {
  id?: number;
  name: string;
  is_hidden: boolean;
  stdin: string | null;
  expected_stdout: string | null;
}

export interface AssignmentDetail extends AssignmentSummary {
  description: string;
  reference_solution?: string | null;
  test_cases: TestCaseView[];
}

export interface TestCaseInput {
  name: string;
  stdin: string;
  expected_stdout: string;
  is_hidden: boolean;
}

export interface AssignmentInput {
  title: string;
  description: string;
  time_limit_ms: number;
  memory_limit_mb: number;
  reference_solution: string | null;
  test_cases: TestCaseInput[];
}

export type Verdict = "pass" | "wrong_answer" | "timeout" | "runtime_error" | "output_limit";
export type SubmissionStatus = "accepted" | "failed" | "compile_error";

export interface TestResult {
  test_name: string;
  verdict: Verdict;
  is_hidden: boolean;
  duration_ms: number;
  actual_stdout: string | null;
  expected_stdout: string | null;
  stderr: string | null;
}

export interface SubmissionSummary {
  id: number;
  assignment_id: number;
  status: SubmissionStatus;
  passed: number;
  total: number;
  created_at: string;
}

export interface Submission extends SubmissionSummary {
  code: string;
  compile_error: string | null;
  hint: string | null;
  hint_source: "llm" | "rule" | null;
  results: TestResult[];
}

export interface TestStat {
  test_name: string;
  is_hidden: boolean;
  attempts: number;
  pass_rate: number;
}

export interface AssignmentStats {
  assignment_id: number;
  total_submissions: number;
  unique_students: number;
  students_accepted: number;
  acceptance_rate: number;
  average_score: number;
  verdict_counts: Record<string, number>;
  tests: TestStat[];
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const BASE = import.meta.env.VITE_API_BASE ?? "/api";
const TOKEN_KEY = "autograder.token";

// localStorage can throw (private mode, blocked storage), so every access is guarded.
export const tokenStore = {
  get(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string): void {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {
      /* the session just will not survive a reload */
    }
  },
  clear(): void {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* nothing to clear */
    }
  },
};

function errorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : ""))
        .filter(Boolean)
        .join("; ");
    }
  }
  return fallback;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const token = tokenStore.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, errorMessage(body, res.statusText || "Request failed"));
  }
  return (await res.json()) as T;
}

const post = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  login: (email: string, password: string) =>
    post<TokenResponse>("/auth/login", { email, password }),
  register: (body: {
    email: string;
    name: string;
    password: string;
    role: Role;
    invite_code?: string;
  }) => post<TokenResponse>("/auth/register", body),
  me: () => request<User>("/auth/me"),

  listAssignments: () => request<AssignmentSummary[]>("/assignments"),
  getAssignment: (id: number) => request<AssignmentDetail>(`/assignments/${id}`),
  createAssignment: (body: AssignmentInput) => post<AssignmentDetail>("/assignments", body),
  assignmentStats: (id: number) => request<AssignmentStats>(`/assignments/${id}/stats`),

  submit: (assignmentId: number, code: string) =>
    post<Submission>(`/assignments/${assignmentId}/submissions`, { code }),
  listSubmissions: (assignmentId?: number) =>
    request<SubmissionSummary[]>(
      assignmentId === undefined ? "/submissions" : `/submissions?assignment_id=${assignmentId}`,
    ),
  getSubmission: (id: number) => request<Submission>(`/submissions/${id}`),
};
