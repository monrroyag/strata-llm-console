import json
import unittest
from unittest.mock import patch

import cli


class ConsoleCliTests(unittest.TestCase):
    def test_parser_exposes_operational_commands(self):
        parser = cli.build_parser()
        commands = {"status": ["status"], "models": ["models"], "traces": ["traces"], "optimize": ["optimize"], "updates": ["updates"], "update": ["update"], "config": ["config", "get", "--model", "m"], "evaluation": ["evaluation", "status", "job"], "connection": ["connection"], "tunnel": ["tunnel"], "chat": ["chat"]}
        for command, argv in commands.items():
            with self.subTest(command=command):
                args = parser.parse_args(argv)
                self.assertEqual(args.command, command)

    def test_client_sends_console_token_and_decodes_json(self):
        client = cli.ConsoleClient("http://127.0.0.1:8090", "test-token")
        response = type("Response", (), {
            "read": lambda self, *args: json.dumps({"status": "ok"}).encode(),
            "__enter__": lambda self: self,
            "__exit__": lambda self, *args: None,
        })()
        with patch("cli.urllib.request.urlopen", return_value=response) as open_url:
            data = client.request("/api/status")
        self.assertEqual(data["status"], "ok")
        request = open_url.call_args.args[0]
        self.assertEqual(request.get_header("X-strata-token"), "test-token")

    def test_brand_is_scannable(self):
        self.assertIn("STRATA", cli.BRAND)
        self.assertIn("CONSOLE", cli.BRAND)


if __name__ == "__main__":
    unittest.main()
