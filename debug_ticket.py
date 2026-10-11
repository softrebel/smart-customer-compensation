"""Debug runner for customer compensation workflow.

Default scenario:
    uv run python scripts/debug_ticket.py
Equivalent to:
    uv run python -m compensation --ticket-id cust_old_222 --allow-remote-model
"""
import argparse
import json
import logging
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from compensation.crm import connect_readonly, discount_cap, get_ticket
from compensation.models import Customer
from compensation.pipeline import (
    MANUAL_RESPONSE,
    OfflineModel,
    build_graph,
    create_model,
)

logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
LOGGER = logging.getLogger("debug_ticket")


def load_dotenv(path: Path | str = ".env") -> None:
    env_path = Path(path)
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        elif " #" in val:
            val = val.split(" #", 1)[0].strip()
        os.environ.setdefault(key, val)


def inspect_db(db_path: Path, identifier: str) -> str:
    """Resolve identifier, checking if it is a ticket_id or customer_id."""
    with closing(connect_readonly(db_path)) as conn:
        row = conn.execute(
            "SELECT ticket_id, customer_id FROM tickets WHERE ticket_id = ?",
            (identifier,),
        ).fetchone()
        if row:
            print(f"[DB] Found ticket_id={row[0]!r} (customer_id={row[1]!r})")
            return identifier

        # ponytail: auto-resolves customer_id to ticket_id for convenience in debug mode
        row = conn.execute(
            "SELECT ticket_id, customer_id FROM tickets WHERE customer_id = ?",
            (identifier,),
        ).fetchone()
        if row:
            print(
                f"[DB] Note: {identifier!r} is a customer_id, mapped to ticket_id={row[0]!r}"
            )
            return row[0]

        print(f"[DB] Warning: {identifier!r} not found in tickets table")
        return identifier


def print_customer_profile(db_path: Path, ticket_id: str) -> None:
    try:
        ticket = get_ticket(db_path, ticket_id)
        with closing(connect_readonly(db_path)) as conn:
            row = conn.execute(
                "SELECT customer_id, name, registration_months, ltv_usd, total_orders "
                "FROM customers WHERE customer_id = ?",
                (ticket.customer_id,),
            ).fetchone()
        if row:
            cust = Customer.model_validate(dict(row))
            cap = discount_cap(cust)
            print(f"[DB] Customer Profile: {cust.model_dump()}")
            print(f"[DB] Computed Financial Cap: {cap}%")
    except Exception as exc:
        print(f"[DB] Could not fetch profile for ticket {ticket_id}: {exc}")


def run_debug(
    db_path: Path,
    ticket_id: str,
    allow_remote: bool = True,
    offline: bool = False,
    auto_resolve: bool = True,
) -> int:
    resolved_id = inspect_db(db_path, ticket_id) if auto_resolve else ticket_id
    print_customer_profile(db_path, resolved_id)

    if offline:
        print("[DEBUG] Using OfflineModel fixture")
        model = OfflineModel()
    else:
        provider = os.environ.get("COMPENSATION_PROVIDER", "ollama")
        print(f"[DEBUG] Using live model provider={provider!r} (allow_remote={allow_remote})")
        try:
            model = create_model(allow_remote=allow_remote)
        except Exception as exc:
            print(f"[DEBUG] Model creation failed: {exc}")
            print("[DEBUG] Tip: set COMPENSATION_PROVIDER or pass --offline to simulate.")
            return 2

    state = {
        "attempt": 0,
        "proposal": None,
        "draft": "",
        "audit_feedback": "",
        "is_verified": False,
        "status": "pending",
        "final_response": MANUAL_RESPONSE,
    }

    try:
        state["ticket"] = get_ticket(db_path, resolved_id)
        print(f"[DEBUG] Loaded ticket: {state['ticket'].model_dump()}")
    except Exception as exc:
        print(f"[DEBUG] get_ticket({resolved_id!r}) failed: {type(exc).__name__}: {exc}")
        print("[DEBUG] System will fail-closed to manual review.")
        print(MANUAL_RESPONSE)
        return 1

    graph = build_graph(db_path, model)
    print("\n--- Starting LangGraph Stream ---")
    step = 0
    try:
        for update in graph.stream(state, {"recursion_limit": 8}, stream_mode="updates"):
            step += 1
            print(f"\n[Step {step}] Node Update: {list(update.keys())}")
            for node, values in update.items():
                print(f"  Node: {node}")
                for key, val in values.items():
                    if key in {"draft", "final_response"}:
                        print(f"    {key}:\n      " + str(val).replace("\n", "\n      "))
                    elif key == "proposal" and val is not None:
                        print(f"    proposal: {val.model_dump()}")
                    else:
                        print(f"    {key}: {val}")
                state.update(values)
    except Exception as exc:
        print(f"\n[DEBUG] Graph execution error: {type(exc).__name__}: {exc}")
        return 1

    print("\n--- Final Result ---")
    print(f"Status: {state.get('status')}")
    print(f"Verified: {state.get('is_verified')}")
    print(f"Rounds: {state.get('attempt')}")
    print("\nFinal Response Email:")
    print(state.get("final_response"))
    return 0 if state.get("is_verified") else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("crm.db"), help="SQLite database path")
    parser.add_argument(
        "--ticket-id",
        default="cust_old_222",
        help="Ticket or Customer ID to debug (default: cust_old_222)",
    )
    parser.add_argument(
        "--allow-remote-model",
        action="store_true",
        default=True,
        help="Explicitly permit remote model provider (default: True for debug)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run deterministic offline fixture instead of live LLM",
    )
    parser.add_argument(
        "--no-auto-resolve",
        dest="auto_resolve",
        action="store_false",
        help="Do not auto-map customer_id to ticket_id; test raw lookup failure",
    )
    args = parser.parse_args(argv)
    load_dotenv()
    return run_debug(
        args.db,
        args.ticket_id,
        allow_remote=args.allow_remote_model,
        offline=args.offline,
        auto_resolve=args.auto_resolve,
    )


if __name__ == "__main__":
    raise SystemExit(main())
