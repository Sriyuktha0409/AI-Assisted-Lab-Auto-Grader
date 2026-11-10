import { formatDate, percent, statusLabel, verdictLabel } from "./format";

describe("format helpers", () => {
  it("labels known verdicts and passes unknown ones through", () => {
    expect(verdictLabel("wrong_answer")).toBe("Wrong answer");
    expect(verdictLabel("timeout")).toBe("Time limit exceeded");
    expect(verdictLabel("something_new")).toBe("something_new");
  });

  it("labels statuses", () => {
    expect(statusLabel("compile_error")).toBe("Compile error");
    expect(statusLabel("accepted")).toBe("Accepted");
  });

  it("formats ratios as whole percentages", () => {
    expect(percent(0)).toBe("0%");
    expect(percent(0.5)).toBe("50%");
    expect(percent(0.6667)).toBe("67%");
  });

  it("returns the raw string for an invalid date", () => {
    expect(formatDate("not a date")).toBe("not a date");
  });
});
