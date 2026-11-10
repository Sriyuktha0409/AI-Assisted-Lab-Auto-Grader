import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { TestCaseInput } from "../api";
import { messageOf } from "../hooks";

const blankCase = (n: number): TestCaseInput => ({
  name: `test ${n}`,
  stdin: "",
  expected_stdout: "",
  is_hidden: false,
});

export function NewAssignment() {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [timeLimit, setTimeLimit] = useState(2000);
  const [memoryLimit, setMemoryLimit] = useState(128);
  const [reference, setReference] = useState("");
  const [cases, setCases] = useState<TestCaseInput[]>([blankCase(1)]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const updateCase = (index: number, patch: Partial<TestCaseInput>) =>
    setCases((prev) => prev.map((c, i) => (i === index ? { ...c, ...patch } : c)));

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await api.createAssignment({
        title,
        description,
        time_limit_ms: timeLimit,
        memory_limit_mb: memoryLimit,
        reference_solution: reference.trim() === "" ? null : reference,
        test_cases: cases,
      });
      navigate(`/assignments/${created.id}`);
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit}>
      <h1>New assignment</h1>
      <label>
        Title
        <input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} />
      </label>
      <label>
        Description
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          required
          rows={5}
        />
      </label>
      <div className="row">
        <label>
          Time limit (ms)
          <input
            type="number"
            min={100}
            max={10000}
            value={timeLimit}
            onChange={(e) => setTimeLimit(Number(e.target.value))}
          />
        </label>
        <label>
          Memory limit (MB)
          <input
            type="number"
            min={16}
            max={512}
            value={memoryLimit}
            onChange={(e) => setMemoryLimit(Number(e.target.value))}
          />
        </label>
      </div>
      <label>
        Reference solution (optional, verified against your tests before saving)
        <textarea
          className="editor"
          value={reference}
          onChange={(e) => setReference(e.target.value)}
          rows={10}
          spellCheck={false}
        />
      </label>

      <h2>Test cases</h2>
      {cases.map((c, i) => (
        <fieldset key={i} className="panel">
          <legend>Case {i + 1}</legend>
          <label>
            Name
            <input
              value={c.name}
              onChange={(e) => updateCase(i, { name: e.target.value })}
              required
            />
          </label>
          <div className="diff">
            <label>
              Input (stdin)
              <textarea
                className="editor"
                rows={3}
                value={c.stdin}
                onChange={(e) => updateCase(i, { stdin: e.target.value })}
              />
            </label>
            <label>
              Expected output
              <textarea
                className="editor"
                rows={3}
                value={c.expected_stdout}
                onChange={(e) => updateCase(i, { expected_stdout: e.target.value })}
              />
            </label>
          </div>
          <label className="check">
            <input
              type="checkbox"
              checked={c.is_hidden}
              onChange={(e) => updateCase(i, { is_hidden: e.target.checked })}
            />
            Hidden from students
          </label>
          {cases.length > 1 && (
            <button
              type="button"
              className="link"
              onClick={() => setCases((prev) => prev.filter((_, j) => j !== i))}
            >
              Remove case
            </button>
          )}
        </fieldset>
      ))}
      <button
        type="button"
        onClick={() => setCases((prev) => [...prev, blankCase(prev.length + 1)])}
        disabled={cases.length >= 50}
      >
        Add test case
      </button>

      {error && (
        <p role="alert" className="error-text">
          {error}
        </p>
      )}
      <div className="row">
        <button type="submit" disabled={busy}>
          {busy ? "Saving…" : "Create assignment"}
        </button>
      </div>
    </form>
  );
}
