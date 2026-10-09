import unittest
from pathlib import Path
from unittest.mock import patch

import runtime_drivers


class RuntimeDriverTests(unittest.TestCase):
    def test_strata_capabilities_require_checkout_or_live_health(self):
        with patch.object(runtime_drivers.StrataDriver, "_request", side_effect=[(None, None), (None, None)]):
            offline = runtime_drivers.StrataDriver("127.0.0.1", 8090, "/tmp/missing").discover()
        self.assertFalse(offline.available)
        self.assertEqual(offline.health, "offline")

        with patch.object(runtime_drivers.StrataDriver, "_request", side_effect=[(200, {"status": "ok"}), (200, {"data": [{"id": "m"}]})]):
            live = runtime_drivers.StrataDriver("127.0.0.1", 8090).discover()
        self.assertTrue(live.available)
        self.assertTrue(live.running)
        self.assertEqual(live.model_count, 1)

    def test_ollama_and_vllm_report_evidence_without_starting_processes(self):
        with patch.object(runtime_drivers.OllamaDriver, "_request", side_effect=[(None, None), (None, None)]), patch("runtime_drivers.shutil.which", return_value=None):
            ollama = runtime_drivers.OllamaDriver().discover()
        self.assertFalse(ollama.available)
        self.assertEqual(ollama.features, ("detect",))

        with patch.object(runtime_drivers.VllmDriver, "_request", return_value=(200, {"data": [{"id": "m"}]})), patch("runtime_drivers.shutil.which", return_value=None):
            vllm = runtime_drivers.VllmDriver().discover()
        self.assertTrue(vllm.running)
        self.assertEqual(vllm.model_count, 1)
        self.assertEqual(vllm.evidence["models_http"], 200)


if __name__ == "__main__":
    unittest.main()
