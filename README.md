# AI-Assisted-Lab-Auto-Grader

A full-stack web app that grades C programs for programming labs. Instructors create assignments with visible and hidden test cases. Students submit code, which is compiled and run in a resource-limited sandbox, and failed submissions get a short hint. Hints are written by an LLM (optional) and checked by a validator before a student sees them.

**Stack:** React + TypeScript (Vite) · FastAPI · SQLAlchemy · PostgreSQL · Docker · GitHub Actions

<!-- Add a screenshot or GIF here: ![Demo](docs/demo.png) -->

## Features

- **Roles:** JWT login for students and instructors (instructor sign-up needs an invite code)
- **Grading:** compiles C with gcc, runs each test with time, memory and output limits, and reports pass, wrong answer, timeout, runtime error or output limit
- **Hidden tests:** students see only a verdict for them, never the input or expected output
- **Reference check:** an instructor's reference solution must pass its own tests before the assignment is saved
- **Validated AI hints:** LLM hints are rejected if they contain code blocks, overlap the reference solution, or are off-topic. Rejected hints fall back to a rule-based hint
- **Instructor stats:** acceptance rate, average score, pass rate per test
- **Safety:** per-student rate limit, code size cap, hidden test data never sent to the LLM

## Architecture

```
React SPA ──/api──► FastAPI ──► PostgreSQL
                       ├─► Grader ─► Sandbox (gcc + program, Docker or local)
                       └─► Hints ─► LLM (optional) ─► Validator ─► rule-based fallback
```

## Run locally (Linux, macOS with gcc, or WSL on Windows)

Requires Python 3.12+, Node 22+, `gcc` and `prlimit`.

```bash
# Terminal 1: API on :8000
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
INSTRUCTOR_INVITE_CODE=letmein uvicorn app.main:app --reload

# Terminal 2: UI on :5173
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, register an instructor with the code `letmein`, create an assignment, then submit solutions as a student.

Optional: set `ANTHROPIC_API_KEY` before starting the API to enable LLM hints.

## Run with Docker Compose

```bash
cp .env.example .env     # set POSTGRES_PASSWORD and SECRET_KEY
sudo mkdir -p /var/grader-work
docker compose up --build   # UI on http://localhost:8080
```

## Tests

```bash
cd backend  && ruff check . && pytest --cov=app           # 65 tests
cd frontend && npm run typecheck && npm test && npm run build   # 12 tests
```

CI runs lint, type-check, tests and builds on every push (`.github/workflows/ci.yml`).

## Security notes

- Docker mode runs each compile and run in a throwaway container with no network, a read-only filesystem, dropped capabilities and memory and process limits.
- The local sandbox applies resource limits only. **It is not isolation. Use it for development, never for untrusted users.**
- The Docker sandbox is covered by unit tests of its flags but has no automated end-to-end test.

## Limitations and next steps

- Grading is synchronous. A job queue would scale better.
- C only, one file per submission.
- Tables are created at startup. Add Alembic migrations before changing the schema in production.
