# Smart Customer Compensation

## Context
Implement the existing approved `.specs/spec01.md` in a currently source-free repository. The supplied `crm.db` must be preserved. Deliver a runnable LangChain/LangGraph CLI, bounded support/audit correction loop, tests, actual five-ticket execution evidence, README, complete available development prompt history, and a local submission ZIP. Do not send email or publish CRM data.

The user resolved the unspecified established non-VIP tier: customers with purchases, tenure >=12 months, and LTV <$1,000 receive a **15% maximum**.

## Inspection status
- CodeGraph reports no existing implementation; repository root contains `.specs/spec01.md`, `.gitignore`, and `crm.db`.
- `.gitignore` already excludes `.env`, `.venv`, generated Python files, `dist/`, `logs/`, and `crm.db`.
- Database-schema/runtime inspection and planning-agent calls were blocked by the permission service's temporary classifier outage. Inspect these before writing schema-dependent code; do not invent the supplied schema or claim live-model verification.

## Recommended implementation
- Python package with `pyproject.toml`, using required LangChain, LangGraph, Pydantic, and Ollama/OpenAI integrations. Use stdlib SQLite, argparse, unittest, logging, and zipfile; no web server or unrelated abstractions.
- Default to local Ollama. Configure provider/model/connection settings using environment variables, with a documented OpenAI alternative. Never contact a commercial provider with CRM contents automatically.
- Read the supplied database in read-only mode for processing, parameterize SQL, validate IDs and customer fields. Provide an explicit initializer that creates the same schema and five synthetic scenarios only when the destination does not exist; never reset an existing DB.
- Use a LangChain CRM tool scoped to the database. The Support node invokes it with the ticket's trusted customer ID; customer text cannot select a different identity or alter policy.
- Build `START -> support -> auditor`, with rejection looping to support and approval ending. Typed state includes ticket/profile, proposal, draft, attempt count, audit feedback, and verification/final status. Both prompts treat ticket text as untrusted data and tell agents to ignore threats and policy overrides.
- Support drafts a structured response and proposed discount; auditor independently evaluates it via `with_structured_output(AuditResult)` using Pydantic. Detailed rejection feedback reaches the next support attempt.
- Enforce financial limits again in ordinary Python regardless of auditor/model claims: zero orders -> 0%; VIP >=12 months and LTV >=1000 -> 40%; all other customers -> 15%. Reject invalid/inconsistent outputs and never approve an over-cap offer. Final financial language and local demonstration coupon code are rendered from the verified numeric discount, not uncontrolled model text. Coupons are local sample codes, not redeemable codes issued by an external system.
- Permit at most **three complete support/audit rounds**, with explicit attempt-count routing and a finite LangGraph `recursion_limit` large enough for those node steps (six node executions plus termination headroom). Document why `recursion_limit=3` alone cannot represent three two-node rounds. Exhaustion/errors return an unverified apology/manual-review result with no coupon, never the rejected offer. Handle graph-limit and provider/structured-output failures cleanly.
- Provide an explicitly selected, clearly labeled deterministic offline mode for repeatable integration tests and five-ticket demonstration. It must exercise the real graph, CRM tool, structured-audit interface, rejection feedback, and rewrites, but must not be represented as a real LLM run. Live mode never silently falls back to it.

## Ordered tasks and files
After approval, copy this plan into `tasks/plan.md` and track these tasks in `tasks/todo.md` (check for existing incomplete work first).

1. **Data and policy boundary** — `pyproject.toml`, `compensation/__init__.py`, `compensation/crm.py`, `tests/test_compensation.py`.
   - Inspect exact schema and supplied five cases; reuse them. Implement safe read/tool/initializer and deterministic caps.
   - Verify unknown IDs, parameterized lookups, policy boundaries, zero-order precedence, and initialization without overwrites using temporary databases.
2. **One bounded graph** — `compensation/pipeline.py`, `compensation/models.py`, expand the same test file.
   - Implement configurable providers, typed draft/audit output, support/audit loop, deterministic enforcement, safe final rendering, and scripted offline test model.
   - Verify approve-first-pass, reject/rewrite/approve, dishonest auditor, three-round exhaustion, malformed outputs, and provider failures with no credentials required.
3. **Runnable CLI and evidence** — `compensation/__main__.py`, `README.md`, `.env.example`, `.specs/spec01.md`, `execution.log`.
   - Accept one ticket ID or sequential all-ticket mode; provide explicit database initialization and offline mode; show proposed discount, cap, iteration, audit feedback, and final response.
   - Document the approved 15% non-VIP clarification, recursion semantics, configuration, setup, tests, failure behavior, and non-redeemable demonstration coupons.
   - Run all five actual supplied tickets sequentially offline and capture terminal output including correction loops. Attempt live Ollama validation only if an appropriate local model is available; report any limitation honestly.
4. **Submission completeness** — `prompts.md`, `scripts/export_prompts.py`, local ZIP under `dist/`, finish task checklist.
   - Export this session's available user/assistant messages and tool exchanges verbatim into `prompts.md`, including runtime prompt templates and invocation instructions. Exclude hidden reasoning, credentials, and unrelated sessions; explicitly state omissions rather than calling a summary a complete transcript.
   - Build and inspect a local ZIP containing code, exact dependencies, README, tests, supplied database, spec, prompt history, and execution log; exclude `.git`, `.codegraph`, `.venv`, secrets, caches, and the ZIP itself. No email delivery or external upload.

## Verification
- Create a local virtual environment and install the declared dependencies; record resolved versions reproducibly.
- `python -m unittest discover -s tests -v` — deterministic policy/database/graph/failure-path checks.
- `python -m compensation --help` — documented command interface.
- `python -m compensation --ticket-id <actual-id> --offline` — one supported ticket.
- `python -m compensation --all --offline` — all five supplied tickets in order; capture genuine output to `execution.log` and check that rejection/rewrite events appear.
- Initialize a fresh temporary database, run its five scenarios, and verify a second initialization refuses to overwrite it.
- If local Ollama is available, run a live ticket and distinguish that evidence from offline fixtures. Otherwise explicitly mark live model validation as not performed.
- Inspect ZIP members and verify required artifacts are included and secrets/internal session files are excluded.
