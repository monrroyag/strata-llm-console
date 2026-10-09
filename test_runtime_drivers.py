import unittest
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

    def test_discovery_exposes_only_strata(self):
        with patch.object(runtime_drivers.StrataDriver, "discover") as discover:
            discover.return_value = runtime_drivers.RuntimeSnapshot(
                "strata", "Strata", True, True, "reachable", "http://127.0.0.1:8090/v1"
            )
            result = runtime_drivers.discover_all("127.0.0.1", 8090)
        self.assertEqual([item["id"] for item in result], ["strata"])


if __name__ == "__main__":
    unittest.main()
