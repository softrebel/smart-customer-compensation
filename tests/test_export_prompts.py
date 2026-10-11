import json
import tempfile
import unittest
from pathlib import Path

from scripts.export_prompts import export, message_records, scrub


class PromptExportTests(unittest.TestCase):
    def test_selected_messages_tools_redactions_and_runtime_prompts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "session.jsonl"
            output = root / "prompts.md"
            rows = [
                {"type": "user", "message": {"role": "user", "content": "Build this exactly.\nNext line."}},
                {"type": "assistant", "message": {"role": "assistant", "content": [
                    {"type": "thinking", "thinking": "DO NOT EXPORT"},
                    {"type": "text", "text": "Visible reply"},
                    {"type": "tool_use", "name": "tool", "input": {"api_key": "private-value"}},
                ]}},
                {"type": "user", "message": {"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": "test", "content": "actual tool output"},
                ]}},
            ]
            for row in rows:
                row.update(sessionId="session", cwd=str(root))
            source.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            (root / "compensation").mkdir()
            (root / "compensation" / "pipeline.py").write_text(
                'POLICY = "Policy"\nSUPPORT_PROMPT = "Support " + POLICY\nAUDIT_PROMPT = "Audit " + POLICY\n',
                encoding="utf-8",
            )
            export([source], output, root, ["export_prompts.py", "session.jsonl"])
            text = output.read_text(encoding="utf-8")
            self.assertIn("Build this exactly.\\nNext line.", text)
            self.assertIn("actual tool output", text)
            self.assertIn("Support Policy", text)
            self.assertIn("Audit Policy", text)
            self.assertIn("[REDACTED]", text)
            self.assertNotIn("private-value", text)
            self.assertNotIn("DO NOT EXPORT", text)
            with self.assertRaises(ValueError):
                export([source], source, root, [])
            with self.assertRaises(ValueError):
                message_records(source, root / "other-project")

    def test_known_secret_patterns(self):
        self.assertNotIn("sk-", scrub("key sk-abcdefghijklmnopqrstuvwxyz"))
        self.assertNotIn("private", scrub("OPENAI_API_KEY=private"))
        self.assertEqual(scrub("Ordinary prompt text"), "Ordinary prompt text")

    def test_default_transcripts_returns_list(self):
        from scripts.export_prompts import default_transcripts

        self.assertIsInstance(default_transcripts(), list)


if __name__ == "__main__":
    unittest.main()
