import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth";
import { Login } from "./Login";

function renderLogin() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <Login />
      </AuthProvider>
    </MemoryRouter>,
  );
}

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: async () => body,
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Login", () => {
  it("shows the server's error message on bad credentials", async () => {
    mockFetch(401, { detail: "Incorrect email or password" });
    renderLogin();
    await userEvent.type(screen.getByLabelText("Email"), "a@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "wrongpassword");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password");
    expect(localStorage.getItem("autograder.token")).toBeNull();
  });

  it("stores the token and sends credentials on success", async () => {
    const fetchMock = mockFetch(200, {
      access_token: "tok123",
      token_type: "bearer",
      user: { id: 1, email: "a@example.com", name: "A", role: "student" },
    });
    renderLogin();
    await userEvent.type(screen.getByLabelText("Email"), "a@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "password123");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(localStorage.getItem("autograder.token")).toBe("tok123"));
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/auth/login");
    expect(JSON.parse(init.body)).toEqual({ email: "a@example.com", password: "password123" });
  });

  it("asks for an invite code only when registering as an instructor", async () => {
    mockFetch(200, {});
    renderLogin();
    await userEvent.click(screen.getByRole("button", { name: /register/i }));
    expect(screen.queryByLabelText("Instructor invite code")).not.toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("I am a"), "instructor");
    expect(screen.getByLabelText("Instructor invite code")).toBeInTheDocument();
  });
});
