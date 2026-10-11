
Mandatory Frameworks: LangChain and LangGraph.

LLM Choice: You are free to use either a local model (via ChatOllama) or any standard commercial API. The codebase must be modular enough to switch between models easily by changing the configuration.

The Challenge: Smart Customer Compensation & Audit System (with LangGraph)

We aim to automate the process of analyzing customer complaint tickets and issuing appropriate compensation coupon codes. Your system must accept a ticket_id, query a database to fetch the customer's historical profile, analyze the ticket context, and draft a response email containing a calibrated discount percentage.

Crucially, before final output generation, a secondary Compliance Auditor Agent node must review the draft to ensure the system has not fallen prey to aggressive customer behavior or violated internal financial limits.

1. Database Setup

To ensure you do not waste time setting up infrastructure or data pipelines, you are expected to initialize a local SQLite crm.db database file containing two tables: customers and tickets.

2. Graph Architecture (Nodes & State)

You must build a cyclic StateGraph that manages the following components:

Database Access Tool (LangChain Tool): A function wrapped as a tool that queries crm.db and pulls customer demographics based on a customer_id.

Support Agent Node: Reads the raw ticket message, executes the CRM tool to check user details, assesses the severity of the issue, and drafts an email alongside a proposed discount.

Compliance Auditor Node: Evaluates the Support Agent's draft. This node must use LangChain's Structured Outputs (via Pydantic) to output its evaluation.

Conditional Edge: If the Auditor rejects the draft due to rule violations, it must set is_verified = False, attach detailed feedback, and loop back to the Support Agent Node for a rewrite. If approved, the pipeline finalizes.

Corporate Financial Guardrails (Strict Limits)

New Users (registration_months < 12) -> Maximum 15% discount permitted.

VIP Users (registration_months >= 12 AND ltv_usd >= 1000) -> Up to 40% discount permitted.

Users with Zero Purchases (total_orders = 0) -> Strictly 0% discount (Apology email only).

The graph must implement a strict recursion_limit (maximum 3 iterations) to cleanly prevent infinite agentic routing loops.

Approved implementation clarifications:
- Established non-VIP customers (registration_months >= 12, ltv_usd < 1000, total_orders > 0) have a maximum 15% discount.
- An iteration means one complete support/audit round. At most three rounds are allowed; LangGraph recursion_limit is 8 to accommodate six node executions and termination headroom. recursion_limit=3 would not permit three complete two-node rounds.
- Coupon codes in this local demonstration are non-redeemable samples, not externally issued coupons.
- Offline deterministic fixtures must be explicitly selected and labeled separately from live LLM evidence.

Mandatory Policy on AI Tool Usage (Prompt Logs Required)

We highly encourage the use of modern developer acceleration tools (such as ChatGPT, GitHub Copilot, Cursor, etc.) to optimize your workflow within the 3-hour limit. However, as an AI Engineer, your ability to architect, refine, and engineer prompts is a core competency we are evaluating.

Mandatory Requirement: If you leverage any generative AI assistants to write code snippets, construct prompt templates, or organize graph logic, you must document and attach your complete prompt logs/chat histories in a file named prompts.md (or provide active shared chat URLs) alongside your codebase. Failure to supply these logs when AI assistance is used will result in an incomplete submission.



The complete codebase implementing the LangGraph pipeline.

A README.md file detailing environment setup, dependency management, and execution instructions.

A comprehensive terminal execution log demonstrating how the graph behaves when sequentially tested against all 5 distinct database tickets (highlighting the self-correction loops).
