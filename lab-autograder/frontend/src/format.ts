import type { SubmissionStatus, Verdict } from "./api";

export const VERDICT_LABELS: Record<Verdict, string> = {
  pass: "Passed",
  wrong_answer: "Wrong answer",
  timeout: "Time limit exceeded",
  runtime_error: "Runtime error",
  output_limit: "Output limit exceeded",
};

export const STATUS_LABELS: Record<SubmissionStatus, string> = {
  accepted: "Accepted",
  failed: "Failed",
  compile_error: "Compile error",
};

export function verdictLabel(verdict: string): string {
  return VERDICT_LABELS[verdict as Verdict] ?? verdict;
}

export function statusLabel(status: string): string {
  return STATUS_LABELS[status as SubmissionStatus] ?? status;
}

export function percent(ratio: number): string {
  return `${Math.round(ratio * 100)}%`;
}

export function formatDate(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString();
}

export const STARTER_CODE = `#include <stdio.h>

int main(void) {
    return 0;
}
`;
