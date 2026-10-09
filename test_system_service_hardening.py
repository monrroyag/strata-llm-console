import subprocess
import unittest
from unittest.mock import patch

import console_core
import systemd_helper


class SystemServiceHardeningTests(unittest.TestCase):
    def test_system_service_uses_template_without_writing_etc(self):
        old = console_core.SYSTEM_SERVICE
        try:
            console_core.SYSTEM_SERVICE = True
            entry = {"id": "demo", "unit": "ignored"}
            self.assertEqual(console_core.unit_name(entry), "strata-console-model@demo.service")
            self.assertEqual(console_core.ensure_unit(entry, {}), "strata-console-model@demo.service")
        finally:
            console_core.SYSTEM_SERVICE = old

    @patch("console_core.subprocess.run")
    def test_system_service_routes_lifecycle_through_narrow_helper(self, run):
        run.return_value = subprocess.CompletedProcess([], 0)
        old = console_core.SYSTEM_SERVICE
        try:
            console_core.SYSTEM_SERVICE = True
            self.assertTrue(console_core.systemctl("restart", "strata-console-model@demo.service"))
            command = run.call_args.args[0]
            self.assertEqual(command[:5], ["sudo", "-n", "/usr/bin/python3", console_core.SYSTEM_HELPER, "model"])
            self.assertEqual(command[-2:], ["restart", "demo"])
            self.assertFalse(console_core.systemctl("restart", "untrusted.service"))
        finally:
            console_core.SYSTEM_SERVICE = old

    def test_helper_rejects_uncontrolled_units(self):
        self.assertEqual(systemd_helper.main(["helper", "model", "restart", "../root"]), 2)
        self.assertEqual(systemd_helper.main(["helper", "connection", "remote"]), 2)


if __name__ == "__main__":
    unittest.main()
