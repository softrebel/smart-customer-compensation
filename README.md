# Smart Customer Compensation

A Python CLI using LangChain tools and a cyclic LangGraph support/compliance workflow. It reads SQLite customer history, proposes compensation, independently audits it, and returns a local demonstration email. It does not send email or issue redeemable coupons.

## Verification status

Dependencies were installed and locked with `uv sync`. The verification script ran in this environment, passed all 22 tests, executed `--help`, tested one-ticket and all five supplied database tickets offline demonstrating self-correction loops, verified synthetic database creation and overwrite refusal, verified database SHA256 preservation (`a158a0c0db9b67c9d470dabebc6189afd6b16241470547aff06157765c5adf18`), and checked local Ollama availability. The captured output is saved in `execution.log`. Live-model validation was not performed because a local Ollama server was not running. Exporting prompt history and building the final local submission ZIP are the remaining steps.

## Setup

Python 3.14 and [uv](https://docs.astral.sh/uv/) are required by the existing project configuration.

```powershell
uv sync
uv run python -m unittest discover -s tests -v
uv run python -m compensation --help
```

`uv sync` creates/updates `.venv` and resolves exact transitive versions into `uv.lock`. After a successful first resolution, use `uv sync --locked` to reproduce that environment. No new test framework is required; tests use `unittest` and temporary SQLite databases, never the supplied database.

## Run offline first

```powershell
uv run python -m compensation --all --offline
uv run python -m compensation --ticket-id <actual-ticket-id> --offline
```

Use a ticket ID printed by `--all`; supplied IDs are not assumed. `--db path/to/crm.db` selects another database. The default is `crm.db` in the working directory. `python main.py` delegates to the same CLI.

**Offline mode is a scripted fixture, not an LLM.** On its first attempt it deliberately proposes ten percentage points above the cap. It reads rejection feedback and corrects the next proposal. It runs the real LangGraph, LangChain CRM tool, structured-output interface, and Python guardrails. A successful five-ticket offline demonstration proves routing/enforcement, not live-model judgment or prompt-injection resistance. Live mode never silently switches to offline mode.

Exit codes: `0` all selected requests verified (or initialization succeeded), `1` at least one request requires manual review, `2` invalid invocation/configuration, inaccessible database or refused initialization.

### Debug runner

```powershell
uv run python scripts/debug_ticket.py
uv run python scripts/debug_ticket.py --ticket-id cust_old_222 --offline
```

`scripts/debug_ticket.py` streams LangGraph node updates, inspects the customer profile and financial cap, and auto-resolves customer IDs (such as `cust_old_222`) to their matching database ticket (`tick_105`). Pass `--no-auto-resolve` to observe strict fail-closed behavior on raw IDs.

### Explicit synthetic initialization

```powershell
uv run python -m compensation --db synthetic.db --init-db
uv run python -m compensation --db synthetic.db --all --offline
```

Creates the supplied schema with five **synthetic** scenarios: new customer, VIP, zero purchases, established non-VIP, and an identity/policy override attempt. Creation refuses any existing destination, even an empty file. Never run an initializer to replace the supplied `crm.db`. Processing opens SQLite using `mode=ro` and `query_only`; it does not update ticket status.

## Live local model

Install/start Ollama yourself, then install a model with structured-output support, for example:

```powershell
ollama pull qwen2.5:7b
$env:COMPENSATION_PROVIDER = "ollama"
$env:COMPENSATION_MODEL = "qwen2.5:7b"
$env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"
uv run python -m compensation --ticket-id <actual-ticket-id>
```

These are the defaults. An unavailable server/model or invalid structured response fails closed. Each model request has a 60-second timeout and bounded output. `.env.example` lists settings but is **not automatically loaded**. The verification script probes only the loopback server; it never pulls a model or sends tickets to an external provider.

### Explicit OpenAI alternative

```powershell
$env:COMPENSATION_PROVIDER = "openai"
$env:COMPENSATION_MODEL = "gpt-4.1-mini"
# Set OPENAI_API_KEY securely in your environment.
uv run python -m compensation --ticket-id <actual-ticket-id> --allow-remote-model
```

`OPENAI_BASE_URL` can configure an OpenAI-compatible endpoint. OpenAI or non-loopback Ollama requires `--allow-remote-model` on every invocation. This authorizes sending the raw complaint and historical eligibility fields externally; complaints may contain personal data. Customer names and IDs are excluded from model context, but raw complaint text is not anonymized. LangSmith tracing is disabled around processing, even if enabled in the surrounding environment. The application itself never uploads execution logs, prompt history or the database.

## Policy and routing

Eligibility is enforced again in ordinary Python, regardless of either model's assertions:

| Customer | Maximum discount |
| --- | ---: |
| `total_orders == 0`, regardless of tenure/LTV | 0% |
| Purchases, tenure >= 12 months, LTV >= $1,000 | 40% |
| All other customers with purchases | 15% |

The established non-VIP 15% tier is the approved clarification. Caps are not entitlements: the live support model considers actual complaint severity and the auditor can reject inappropriate offers below the cap.

Flow: `START -> support -> auditor -> END`, or rejection returns to `support`. State includes the ticket, trusted CRM profile, proposal, rendered draft, attempt count, audit feedback, verification and terminal status.

- Support invokes a database-scoped LangChain tool using the **ticket row's customer ID**, never an identity chosen by the model or complaint text.
- Support chooses a structured issue category, rationale and integer percentage. The email draft is rendered from these constrained fields rather than accepting free-form financial promises.
- The independent auditor uses `with_structured_output(AuditResult)` and checks the full rendered draft. It must report the exact percentage it reviewed. Detailed rejection feedback and the previous proposal/draft reach the next attempt.
- All model output is strictly validated. A dishonest auditor cannot approve an over-cap percentage. The final response contains only template-controlled language and the verified percentage; model rationales/feedback are not sent as customer-facing financial text.
- At most **three complete support/audit rounds** are permitted. `recursion_limit=8` bounds six node executions plus termination headroom. LangGraph counts supersteps, not business rounds, so `recursion_limit=3` cannot implement three two-node rounds.
- Exhaustion, missing/invalid data, provider errors or graph-limit errors produce an unverified apology/manual-review response with **no coupon**. Error logs include exception types, not potentially sensitive provider messages.
- `DEMO-...` codes are deterministic local samples, explicitly **non-redeemable**. There is no coupon-issuance integration. Final code generation is unreachable for zero compensation or rejected offers.

Both prompts treat ticket text as untrusted, reject threats and ignore policy/identity overrides. Deterministic financial enforcement limits exposure even when model judgment fails; it does not make an LLM immune to all prompt injection. The CLI assumes its operator may access the selected database; it is not a multi-tenant authenticated API.

## Evidence and local submission

Once dependencies are installed:

```powershell
uv run python scripts/verify_submission.py
```

This inspects the actual schema and five supplied cases, records a preservation hash, runs tests/help/one-ticket/all-ticket commands, confirms rejection and rewrite output, tests synthetic initialization and overwrite refusal, checks local Ollama availability, and writes genuine captured output to `execution.log`. Failed commands stop verification and are recorded as failures. The log contains complaint text and is sensitive; it stays local.

Export explicitly selected project transcripts (defaults to the project's session transcripts):

```powershell
uv run python scripts/export_prompts.py
uv run python scripts/verify_submission.py --package
```

The first two sessions begin with implementation of this same specification; the third is this plan-implementation session. Adjust paths if the local histories have moved. The exporter retains message text and tool exchanges in JSON, strips hidden reasoning/metadata and recognizable credentials, adds the actual static runtime prompts, and states coverage/omissions. It is a snapshot, not a promise of unavailable history. Review its best-effort redactions before sharing.

Packaging refuses a placeholder prompt history, stale dependency lock or unsuccessful verification. It produces a timestamped ZIP under `dist/` and checks ZIP integrity, member names and the database bytes. Its explicit allowlist includes code, tests, scripts, exact lock, README, supplied database, spec, task records, prompts and execution evidence. It excludes secrets, `.git`, `.codegraph`, `.venv`, caches and the ZIP itself. No email, publication or remote upload is performed. Live-model evidence must be recorded separately and must not be described as passed unless a real live call succeeds.

Implementation progress and unresolved checks are tracked in `tasks/todo.md`.
