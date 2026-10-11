import argparse
import json
import logging
import os
from pathlib import Path

from compensation.crm import initialize, ticket_ids
from compensation.pipeline import MANUAL_RESPONSE, OfflineModel, create_model, process_ticket


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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Customer compensation with a bounded compliance audit")
    parser.add_argument("--db", type=Path, default=Path("crm.db"), help="SQLite database (read-only except --init-db)")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--ticket-id", help="Process one trusted database ticket ID")
    action.add_argument("--all", action="store_true", help="Process all tickets sequentially by ID")
    action.add_argument("--init-db", action="store_true", help="Create five synthetic cases; never overwrite")
    parser.add_argument("--offline", action="store_true", help="Use a deterministic fixture, NOT a live LLM")
    parser.add_argument("--allow-remote-model", action="store_true",
                        help="Explicitly permit sending CRM context to a remote model provider")
    parser.add_argument("--env-file", type=Path, default=Path(".env"),
                        help="Environment file to load (default: .env)")
    args = parser.parse_args(argv)
    if args.env_file:
        load_dotenv(args.env_file)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.init_db:
        try:
            initialize(args.db)
        except Exception as error:
            print(f"Initialization refused/failed ({type(error).__name__}). Existing files are not overwritten.")
            return 2
        print("Initialized five synthetic scenarios.")
        return 0
    if args.offline:
        print("MODE: OFFLINE deterministic fixture — not a live LLM run", flush=True)
        model = OfflineModel()
    else:
        print(f"MODE: LIVE provider={json.dumps(os.environ.get('COMPENSATION_PROVIDER', 'ollama'))}", flush=True)
        try:
            model = create_model(allow_remote=args.allow_remote_model)
        except Exception as error:
            print(f"Model configuration failed ({type(error).__name__}). Check provider settings and remote opt-in.")
            print(MANUAL_RESPONSE)
            return 2
    try:
        identifiers = ticket_ids(args.db) if args.all else [args.ticket_id]
        if not identifiers:
            print("No tickets found.")
            return 2
    except Exception as error:
        print(f"Database access failed ({type(error).__name__}).")
        print(MANUAL_RESPONSE)
        return 2
    failed = False
    for identifier in identifiers:
        print(f"\n=== Ticket {json.dumps(identifier)} ===", flush=True)
        result = process_ticket(args.db, identifier, model)
        print(f"status={result['status']} verified={result['is_verified']} rounds={result['attempt']}")
        print(result["final_response"], flush=True)
        failed |= not result["is_verified"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
