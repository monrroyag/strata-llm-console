import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import console_core
import evaluation_core
import history_core
import tunnel_core
import update_core


class ConsoleSecurityTests(unittest.TestCase):
    def test_model_ids_reject_paths_and_shell_delimiters(self):
        for value in ("../traces", "model/name", "bad id", "x'y", "a" * 65):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    console_core.validate_model_id(value)
        self.assertEqual(console_core.validate_model_id("Qwen-3.8_IQ3"), "qwen-3.8_iq3")

    def test_systemd_command_rejects_shell_control(self):
        with self.assertRaises(ValueError):
            console_core._systemd_quote("/tmp/x'\n/bin/sh")
        self.assertEqual(console_core._systemd_quote("/tmp/model files"), '"/tmp/model files"')

    def test_history_path_is_bounded(self):
        with self.assertRaises(ValueError):
            history_core.history("../traces")
        with self.assertRaises(ValueError):
            history_core.compare_setups("../../token")

    def test_update_check_does_not_clone_missing_engine(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = update_core.check_update({"engine_root": str(Path(tmp) / "missing")})
        self.assertFalse(result["present"])
        self.assertIn("no instalado", result["error"])

    def test_public_tunnel_status_never_contains_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = tunnel_core.STATE
            try:
                tunnel_core.STATE = Path(tmp) / "tunnel.json"
                tunnel_core.STATE.write_text(json.dumps({
                    "pid": 123, "url": "https://demo.trycloudflare.com",
                    "generated_api_key": "must-not-leak"
                }), encoding="utf-8")
                public = tunnel_core.status(public=True)
                self.assertNotIn("generated_api_key", public)
                self.assertIn("api_key_set", public)
            finally:
                tunnel_core.STATE = old

    def test_evaluation_metrics_are_bounded_and_rankable(self):
        samples = [{"ok": True, "duration_ms": 100, "decode_tok_s": 20, "error": None},
                   {"ok": True, "duration_ms": 200, "decode_tok_s": 10, "error": None}]
        metrics = evaluation_core._aggregate(samples)
        self.assertEqual(metrics["successful"], 2)
        self.assertEqual(metrics["latency_ms"]["p95"], 200)
        score = evaluation_core._score(metrics, metrics)
        self.assertIn("score", score)
        self.assertGreaterEqual(score["long_short_speed_ratio"], 0)

        root = Path(__file__).parent
        self.assertTrue((root / "data" / "params_help.json").is_file())
        contract = json.loads((root / "docs" / "api" / "openapi.json").read_text())
        self.assertEqual(contract["openapi"], "3.0.3")
        self.assertIn("/api/status", contract["paths"])


if __name__ == "__main__":
    unittest.main()
