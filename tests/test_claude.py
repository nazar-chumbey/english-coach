import json
import subprocess
import unittest
from unittest import mock

from coach import claude


def done(payload, code=0, is_error=False):
    out = json.dumps({"is_error": is_error, "structured_output": payload, "result": "boom"})
    return subprocess.CompletedProcess([], code, stdout=out, stderr="err")


class AskTest(unittest.TestCase):
    @mock.patch("coach.claude.subprocess.run")
    def test_builds_isolated_command_and_returns_structured_output(self, run):
        run.return_value = done({"ok": True})
        self.assertEqual(claude.ask("check_answer", {"a": 1}, "check", "sonnet"), {"ok": True})
        args = run.call_args.args[0]
        for flag in ("-p", "--no-session-persistence", "--json-schema", "--system-prompt"):
            self.assertIn(flag, args)
        self.assertEqual(args[args.index("--tools") + 1], "")
        self.assertEqual(args[args.index("--setting-sources") + 1], "")
        self.assertEqual(args[args.index("--model") + 1], "sonnet")
        self.assertEqual(json.loads(run.call_args.kwargs["input"]), {"a": 1})

    @mock.patch("coach.claude.subprocess.run")
    def test_retries_once_then_raises(self, run):
        run.return_value = done(None, code=1)
        with self.assertRaises(claude.ClaudeError):
            claude.ask("check_answer", {}, "check", "sonnet")
        self.assertEqual(run.call_count, 2)

    @mock.patch("coach.claude.subprocess.run")
    def test_recovers_on_retry(self, run):
        run.side_effect = [done(None, is_error=True), done({"ok": 1})]
        self.assertEqual(claude.ask("check_answer", {}, "check", "sonnet"), {"ok": 1})

    @mock.patch("coach.claude.subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 1))
    def test_timeout_raises_without_retry(self, run):
        with self.assertRaises(claude.ClaudeError):
            claude.ask("check_answer", {}, "check", "sonnet")
        self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
