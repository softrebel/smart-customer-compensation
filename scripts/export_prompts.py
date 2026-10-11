"""Export only explicitly selected development sessions; never discover other chats."""
import argparse
import ast
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SECRET_KEY = re.compile(r"^(?:api[_-]?key|password|access[_-]?token|refresh[_-]?token|authorization|secret)$", re.I)
SECRET_TEXT = re.compile(
    r"\bsk-[A-Za-z0-9_-]{16,}|\bBearer\s+[A-Za-z0-9._-]{16,}|"
    r"((?:OPENAI_API_KEY|ANTHROPIC_API_KEY|PASSWORD|ACCESS_TOKEN)\s*[=:]\s*[\"']?)[^\s\"',;}]+",
    re.I,
)
OMIT = object()


def scrub(value):
    if isinstance(value, dict):
        if value.get("type") in {"thinking", "redacted_thinking", "reasoning"} or value.get("channel") == "analysis":
            return OMIT
        result = {}
        for key, item in value.items():
            if key in {"thinking", "signature", "reasoning", "reasoning_content"}:
                continue
            clean = "[REDACTED]" if SECRET_KEY.fullmatch(key) else scrub(item)
            if clean is not OMIT:
                result[key] = clean
        return result
    if isinstance(value, list):
        return [clean for item in value if (clean := scrub(item)) is not OMIT]
    if isinstance(value, str):
        value = re.sub(r"<(thinking|analysis)>.*?</\1>", "[OMITTED HIDDEN REASONING]", value, flags=re.S)
        return SECRET_TEXT.sub(lambda match: (match.group(1) or "") + "[REDACTED]", value)
    return value


def _same_dir(a: str, b: Path) -> bool:
    try:
        return Path(a).resolve() == b.resolve() or Path(a).samefile(b)
    except OSError:
        return str(Path(a).resolve()).casefold() == str(b.resolve()).casefold()


def message_records(path: Path, project: Path):
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("type") not in {"user", "assistant"}:
            continue
        if row.get("sessionId") != path.stem or row.get("isSidechain"):
            continue
        if not row.get("cwd") or not _same_dir(row["cwd"], project):
            raise ValueError(f"Transcript project mismatch at {path.name}:{number}")
        message = scrub(row["message"])
        if message is OMIT or not message.get("content"):
            continue
        records.append({"source_line": number, "timestamp": row.get("timestamp"),
                        "uuid": row.get("uuid"), "message": message})
    if not records:
        raise ValueError(f"No matching user/assistant messages in {path.name}")
    return records


def runtime_prompts(path: Path) -> dict:
    values = {}

    def literal(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return values[node.id]
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return literal(node.left) + literal(node.right)
        raise ValueError("Runtime prompt must be a static string")

    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            name = getattr(node.targets[0], "id", "")
            if name in {"POLICY", "SUPPORT_PROMPT", "AUDIT_PROMPT"}:
                values[name] = literal(node.value)
    if set(values) != {"POLICY", "SUPPORT_PROMPT", "AUDIT_PROMPT"}:
        raise ValueError("Missing runtime prompt templates")
    return values


def export(paths: list[Path], output: Path, project: Path, invocation: list[str]) -> None:
    if output.resolve() in {path.resolve() for path in paths}:
        raise ValueError("Output must not overwrite an input transcript")
    sections = [
        "# Development prompt history\n\nStatus: GENERATED from explicitly selected local transcripts.",
        f"Exported UTC: {datetime.now(timezone.utc).isoformat()}",
        "## Coverage and omissions\n\nUser/assistant messages include tool-use and tool-result blocks. "
        "Message text is retained verbatim inside JSON except the documented redactions; JSON whitespace "
        "is reformatted. Hidden reasoning, signatures, system/attachment metadata, sidechains and unrelated "
        "sessions are excluded. Recognizable credentials are redacted. No claim is made about unavailable "
        "earlier conversations. This is a snapshot: messages after export are not included. Credential "
        "detection is best-effort: review this local file before sharing. CRM data may appear in tool results. "
        "No external upload is performed.",
        "## Export invocation\n\n" + json.dumps(invocation, ensure_ascii=False),
    ]
    for path in paths:
        records = message_records(path, project)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        sections.append(f"## Session {path.stem}\n\nSource snapshot SHA256: {digest}; messages: {len(records)}")
        for record in records:
            # Indented code cannot be terminated by Markdown fences inside a tool result.
            sections.append("\n".join("    " + line for line in json.dumps(
                record, ensure_ascii=False, indent=2).splitlines()))
    sections.append("## Runtime prompt templates")
    for name, value in runtime_prompts(project / "compensation" / "pipeline.py").items():
        sections.append(f"### {name}\n\n" + "\n".join("    " + line for line in value.splitlines()))
    sections.append("## Runtime invocation\n\n`uv run python -m compensation --all --offline`\n\n"
                    "Live local model: `uv run python -m compensation --ticket-id <database-ticket-id>`. "
                    "See README for model configuration. Live mode never silently falls back to fixtures.")
    output.write_text("\n\n".join(sections) + "\n", encoding="utf-8")


def default_transcripts() -> list[Path]:
    folder = Path.home() / ".claude" / "projects" / "S--smart-customer-compensation"
    return sorted(folder.glob("*.jsonl")) if folder.is_dir() else []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcripts", nargs="*", type=Path, default=[])
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("prompts.md"))
    args = parser.parse_args()
    transcripts = args.transcripts or default_transcripts()
    if not transcripts:
        parser.error("No transcripts specified and none found in project directory")
    export(transcripts, args.output, args.project, [sys.executable, *sys.argv])
    print(f"Exported {len(transcripts)} selected sessions to {args.output}")


if __name__ == "__main__":
    main()
