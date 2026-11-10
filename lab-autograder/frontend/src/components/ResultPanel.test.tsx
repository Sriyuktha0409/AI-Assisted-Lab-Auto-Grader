import { render, screen } from "@testing-library/react";
import type { Submission } from "../api";
import { ResultPanel } from "./ResultPanel";

function make(overrides: Partial<Submission> = {}): Submission {
  return {
    id: 1,
    assignment_id: 1,
    status: "failed",
    passed: 1,
    total: 2,
    created_at: "2026-11-07T10:00:00Z",
    code: "int main(void){return 0;}",
    compile_error: null,
    hint: null,
    hint_source: null,
    results: [],
    ...overrides,
  };
}

describe("ResultPanel", () => {
  it("shows the score and per-test verdicts", () => {
    render(
      <ResultPanel
        submission={make({
          results: [
            {
              test_name: "small",
              verdict: "pass",
              is_hidden: false,
              duration_ms: 3,
              actual_stdout: "5\n",
              expected_stdout: "5\n",
              stderr: null,
            },
            {
              test_name: "edge",
              verdict: "timeout",
              is_hidden: false,
              duration_ms: 1000,
              actual_stdout: "",
              expected_stdout: "1\n",
              stderr: null,
            },
          ],
        })}
      />,
    );
    expect(screen.getByText("1/2 tests passed")).toBeInTheDocument();
    expect(screen.getByText("Passed")).toBeInTheDocument();
    expect(screen.getByText("Time limit exceeded")).toBeInTheDocument();
  });

  it("shows expected vs actual output for a visible wrong answer", () => {
    render(
      <ResultPanel
        submission={make({
          results: [
            {
              test_name: "small",
              verdict: "wrong_answer",
              is_hidden: false,
              duration_ms: 2,
              actual_stdout: "-1\n",
              expected_stdout: "5\n",
              stderr: null,
            },
          ],
        })}
      />,
    );
    expect(screen.getByText("Expected")).toBeInTheDocument();
    expect(screen.getByText("Your output")).toBeInTheDocument();
  });

  it("never shows output for a hidden test", () => {
    render(
      <ResultPanel
        submission={make({
          results: [
            {
              test_name: "secret",
              verdict: "wrong_answer",
              is_hidden: true,
              duration_ms: 2,
              actual_stdout: null,
              expected_stdout: null,
              stderr: null,
            },
          ],
        })}
      />,
    );
    expect(screen.getByText("hidden")).toBeInTheDocument();
    expect(screen.getByText("Wrong answer")).toBeInTheDocument();
    expect(screen.queryByText("Expected")).not.toBeInTheDocument();
    expect(screen.queryByText("Your output")).not.toBeInTheDocument();
  });

  it("labels AI hints and automated hints differently", () => {
    const { rerender } = render(
      <ResultPanel submission={make({ hint: "Check the loop bounds.", hint_source: "llm" })} />,
    );
    expect(screen.getByText("AI-assisted hint")).toBeInTheDocument();
    expect(screen.getByText(/can still be wrong/i)).toBeInTheDocument();

    rerender(
      <ResultPanel submission={make({ hint: "Check the loop bounds.", hint_source: "rule" })} />,
    );
    expect(screen.getByText("Automated hint")).toBeInTheDocument();
    expect(screen.queryByText(/can still be wrong/i)).not.toBeInTheDocument();
  });

  it("shows compiler output and omits the score for compile errors", () => {
    render(
      <ResultPanel
        submission={make({
          status: "compile_error",
          passed: 0,
          total: 0,
          compile_error: "main.c:1:5: error: expected ';'",
        })}
      />,
    );
    expect(screen.getByText(/expected ';'/)).toBeInTheDocument();
    expect(screen.queryByText(/tests passed/)).not.toBeInTheDocument();
  });
});
