"""Run real local checks, capture evidence, and optionally build an allowlisted ZIP."""
import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import tomllib
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "customers": [("customer_id", "TEXT"), ("name", "TEXT"), ("registration_months", "INTEGER"),
                  ("ltv_usd", "REAL"), ("total_orders", "INTEGER")],
    "tickets": [("ticket_id", "TEXT"), ("customer_id", "TEXT"), ("message", "TEXT"), ("status", "TEXT")],
}


def run_checks(log, db: Path):
    def record(text):
        log.write(text + "\n")
        log.flush()
        print(text, flush=True)

    def run(arguments, expected=0):
        record("\n$ " + " ".join(arguments))
        completed = subprocess.run(arguments, cwd=ROOT, encoding="utf-8", errors="replace",
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=600)
        record(completed.stdout)
        record(f"exit_code={completed.returncode}")
        if completed.returncode != expected:
            raise RuntimeError("Verification command returned an unexpected exit code")
        return completed.stdout

    record(f"UTC: {datetime.now(timezone.utc).isoformat()}")
    record("OFFLINE fixtures are deterministic simulations, not live LLM verification.")
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    names = {package["name"] for package in lock["package"]}
    if not {"langchain", "langgraph", "langchain-ollama", "langchain-openai", "pydantic"} <= names:
        raise RuntimeError("uv.lock is stale; run uv sync first")
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    record("Supplied database SHA256 before: " + before)
    connection = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        for table, expected in EXPECTED.items():
            # Table names are constants above, never user input.
            columns = connection.execute(f"PRAGMA table_info({table})").fetchall()
            actual = [(row[1], row[2].upper()) for row in columns]
            if actual != expected:
                raise RuntimeError(f"Unexpected schema for {table}: {actual}")
            record(f"Schema {table}: {json.dumps(actual)}")
        tickets = connection.execute("SELECT ticket_id, customer_id, message FROM tickets ORDER BY ticket_id").fetchall()
        if len(tickets) != 5:
            raise RuntimeError("Expected exactly five supplied tickets")
        for ticket in tickets:
            record("Supplied case: " + json.dumps(ticket, ensure_ascii=True))
    finally:
        connection.close()
    python = sys.executable
    run([python, "-m", "unittest", "discover", "-s", "tests", "-v"])
    run([python, "-m", "compensation", "--help"])
    run([python, "-m", "compensation", "--db", str(db), "--ticket-id", tickets[0][0], "--offline"])
    output = run([python, "-m", "compensation", "--db", str(db), "--all", "--offline"])
    if output.count("=== Ticket") != 5 or "REJECTED" not in output or "rewrite=True" not in output:
        raise RuntimeError("Five-ticket correction evidence is incomplete")
    with tempfile.TemporaryDirectory() as directory:
        synthetic = str(Path(directory) / "synthetic.db")
        run([python, "-m", "compensation", "--db", synthetic, "--init-db"])
        run([python, "-m", "compensation", "--db", synthetic, "--all", "--offline"])
        run([python, "-m", "compensation", "--db", synthetic, "--init-db"], expected=2)
    after = hashlib.sha256(db.read_bytes()).hexdigest()
    record("Supplied database SHA256 after: " + after)
    if before != after:
        raise RuntimeError("Supplied database changed")
    # Probe only the loopback Ollama server, with proxies disabled; never pull a model.
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open("http://127.0.0.1:11434/api/tags", timeout=3) as response:
            models = json.load(response).get("models", [])
        record("Local Ollama models: " + json.dumps([model.get("name") for model in models]))
        record("Live validation NOT performed automatically. Select an appropriate installed model "
               "and run a live ticket explicitly; this evidence is offline only.")
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        record("Live validation NOT performed: local Ollama could not be confirmed available.")
    record("VERIFICATION PASSED: offline checks only")


def package():
    prompts = (ROOT / "prompts.md").read_text(encoding="utf-8")
    evidence = (ROOT / "execution.log").read_text(encoding="utf-8")
    if "Status: GENERATED from explicitly selected local transcripts." not in prompts:
        raise RuntimeError("Export actual prompt history before packaging")
    if "VERIFICATION PASSED: offline checks only" not in evidence:
        raise RuntimeError("Successful execution evidence is required")
    names = ["pyproject.toml", "uv.lock", ".python-version", ".env.example", "README.md", "main.py",
             "crm.db", "schema.json", ".specs/spec01.md", "prompts.md", "execution.log",
             "tasks/plan.md", "tasks/todo.md"]
    names += [path.relative_to(ROOT).as_posix() for folder in ("compensation", "tests", "scripts")
              for path in sorted((ROOT / folder).glob("*.py"))]
    for name in names:
        if not (ROOT / name).is_file() or (ROOT / name).is_symlink():
            raise RuntimeError(f"Missing or linked submission input: {name}")
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = dist / f"smart-customer-compensation-{stamp}.zip"
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            archive.write(ROOT / name, name)
    with zipfile.ZipFile(target) as archive:
        if set(archive.namelist()) != set(names) or archive.testzip() is not None:
            raise RuntimeError("ZIP verification failed")
        if hashlib.sha256(archive.read("crm.db")).digest() != hashlib.sha256((ROOT / "crm.db").read_bytes()).digest():
            raise RuntimeError("Packaged database mismatch")
        print("ZIP members:\n" + "\n".join(archive.namelist()))
    print(f"Local ZIP only: {target}; contains CRM data. Review before sharing.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", action="store_true", help="Also build a local ZIP after successful checks")
    args = parser.parse_args()
    with (ROOT / "execution.log").open("w", encoding="utf-8") as log:
        try:
            run_checks(log, ROOT / "crm.db")
        except Exception as error:
            log.write(f"\nVERIFICATION FAILED: {type(error).__name__}: {error}\n")
            raise
    if args.package:
        package()


if __name__ == "__main__":
    main()
