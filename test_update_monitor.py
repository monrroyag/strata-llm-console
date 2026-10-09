import time
import unittest
from unittest.mock import patch

import update_monitor


class UpdateMonitorTests(unittest.TestCase):
    def test_semver_does_not_downgrade_a_local_build(self):
        self.assertEqual(update_monitor._version_tuple("v0.3.0"), (0, 3, 0))
        with patch.object(update_monitor, "_console_version", return_value="0.3.0"), patch.object(update_monitor, "_github", return_value={"tag_name": "v0.2.6", "html_url": "https://example.invalid", "body": "old"}):
            result = update_monitor._console()
        self.assertFalse(result["update_available"])
        self.assertTrue(result["local_build_ahead"])

    def test_status_reports_stale_cache_age(self):
        old = dict(update_monitor._CACHE)
        try:
            update_monitor._CACHE.clear()
            update_monitor._CACHE.update({"checked_at": time.time() - update_monitor.INTERVAL * 3, "updates": []})
            status = update_monitor.status()
        finally:
            update_monitor._CACHE.clear()
            update_monitor._CACHE.update(old)
        self.assertTrue(status["stale"])
        self.assertGreater(status["cache_age_seconds"], update_monitor.INTERVAL)


if __name__ == "__main__":
    unittest.main()
