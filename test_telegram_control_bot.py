import os
import unittest
from unittest.mock import patch

os.environ["TELEGRAM_STRATA_ADMIN_IDS"] = "42"
os.environ["TELEGRAM_STRATA_BOT_TOKEN"] = "test-token"
import telegram_control_bot as bot


class TelegramControlBotTests(unittest.TestCase):
    def test_menu_has_control_surfaces(self):
        calls = []
        with patch.object(bot, "send", side_effect=lambda *a, **k: calls.append((a, k))):
            bot.menu(42)
        rows = calls[0][1].get("rows") or calls[0][0][2]
        data = {item[1] for row in rows for item in row}
        self.assertTrue({"status", "models", "traces", "opt", "connection", "backends", "update", "stop"} <= data)

    def test_unauthorized_chat_is_rejected(self):
        with patch.object(bot, "send") as send:
            bot.handle({"message": {"chat": {"id": 99}, "text": "/status"}})
        send.assert_called_once()
        self.assertIn("not authorized", send.call_args.args[1])

    def test_stop_requires_confirmation(self):
        with patch.object(bot, "send") as send, patch.object(bot, "tg"), patch.object(bot, "local") as local:
            bot.callback(42, "askstop:model-x", "cb-1")
        local.assert_not_called()
        self.assertIn("Confirm stopping", send.call_args.args[1])

    def test_confirm_stop_calls_console(self):
        with patch.object(bot, "send"), patch.object(bot, "tg"), patch.object(bot, "local", return_value={}) as local:
            bot.callback(42, "stop:model-x", "cb-2")
        self.assertEqual(local.call_args_list[0].args, ("/api/stop", {"model": "model-x"}))


if __name__ == "__main__":
    unittest.main()
