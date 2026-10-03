# Nexus Research OS — Claude Code Guidelines

## Project Overview
Nexus OS is a research AI discovery MVP with OpenAlex normalization, evals, Chrome extension, and Supabase backend. Every module ships with unit tests, benchmark data, and an evaluation script.

**Architecture Flow:**
Research Query → OpenAlex/Semantic Scholar → Raw JSON → Normalization → Source → DiscoveryResult → Eval

## Before Implementation

**Always plan first.** When given a problem:
1. **Read affected files entirely** — don't assume structure from grep results
2. **Identify the root cause** — not symptoms
3. **Consider architectural constraints** — this project requires tests/benchmarks/evals before production
4. **Design a single, complete fix** — no trial-and-error patches
5. **Verify with tests** — write them if they don't exist

**Use EnterPlanMode for:**
- Multi-file changes
- New features or refactors
- Cases where the fix isn't immediately obvious
- Anything touching core flows (normalization, discovery, eval)

## Key Modules & Patterns

### Testing & Validation
- **Unit tests required** before any module goes to production
- **Benchmark data** in `benchmarks/` for performance validation
- **Eval scripts** in `evals/` for result quality assessment
- Use pytest; config in `pyproject.toml`

### API Structure (Railway + Supabase)
- Authenticated endpoints require Supabase access token (never expose service-role key in browser)
- `POST /v1/scan` — run and save a research scan
- `GET /v1/research/{run_id}/dossier` — download Excel dossier
- `POST /v1/reports` — generate and download Word report
- Row-level security enforces per-user data isolation in Supabase

### Chrome Extension
- Communicates with Railway API (no local Native Messaging host needed)
- Built with `python extension/build_release.py`
- Persists to Supabase, not local filesystem

### Data Flow
- OpenAlex/Semantic Scholar are fallback providers; configure `SEMANTIC_SCHOLAR_API_KEY` for authenticated tier
- Report generation uses Claude API (primary) with Gemini failover
- All ETL normalizes to `Source` → `DiscoveryResult` model

## Code Standards

### Python
- Follow existing patterns in `app/` and `models/`
- Use type hints where the codebase uses them
- Keep functions focused; prefer composition over abstraction premature to use cases
- No error handling for scenarios that can't happen; trust internal contracts

### Git & PRs
- Atomic commits with clear rationale in the message (not task/issue numbers)
- Single fix per PR, no bundled cleanup
- Reference the actual problem in the commit message (helps future debugging)

### Avoid
- Trial-and-error patches — plan once, implement once
- Mocking database calls in integration tests (configs in `config/` are authoritative)
- Backwards-compatibility hacks for code you control; just change it
- Feature flags for transient work
- Renaming unused variables; delete unused code cleanly
- Temporary scaffolding or half-finished implementations

## Common Tasks

### Running Tests
```bash
pytest tests/
```

### Running Locally
```bash
python main.py              # Start API
python cloud_app.py         # Cloud mode
python extension/build_release.py  # Build extension
```

### Checking for Secrets
Before committing: scan for `.env`, credentials, API keys. Never commit them.

---

**When in doubt, ask for clarification.** This project's constraints (tests/benchmarks/evals) matter; a quick fix that skips them will stall production.
