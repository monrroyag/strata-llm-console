import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import console_core
import evaluation_core
import history_core
import optimize_core
import state_store
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

    def test_runtime_state_migrates_and_commits_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_db = state_store.DB
            try:
                state_store.DB = root / "state.sqlite3"
                legacy = root / "legacy.json"
                legacy.write_text(json.dumps({"mode": "local"}), encoding="utf-8")
                migrated = state_store.load_or_migrate("connection", legacy, {}) or {}
                self.assertEqual(migrated["mode"], "local")
                state_store.put("connection", {"mode": "lan", "cors": True})
                self.assertEqual(state_store.get("connection")["mode"], "lan")
                state_store.atomic_json_export(legacy, state_store.get("connection"))
                self.assertEqual(json.loads(legacy.read_text())["cors"], True)
                self.assertEqual(legacy.stat().st_mode & 0o777, 0o600)
            finally:
                state_store.DB = old_db

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
        self.assertEqual(metrics["usage_coverage"], 0)

    def test_optimizer_reports_evidence_when_telemetry_is_missing(self):
        with patch.object(optimize_core, "_gpu", return_value={"measured": False, "free_mib": None, "total_mib": None, "gpu_count": 0}):
            result = optimize_core.optimize(200000, profile="balanced", entry=None)
        self.assertEqual(result["confidence"], "baja")
        self.assertIn("GPU telemetry unavailable", result["confidence_reasons"])
        self.assertFalse(result["evidence"]["gpu_measured"])

        root = Path(__file__).parent
        self.assertTrue((root / "data" / "params_help.json").is_file())
        contract = json.loads((root / "docs" / "api" / "openapi.json").read_text())
        self.assertEqual(contract["openapi"], "3.0.3")
        self.assertIn("/api/status", contract["paths"])


if __name__ == "__main__":
    unittest.main()
