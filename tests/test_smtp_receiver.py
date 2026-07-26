import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from worker import smtp_receiver


class SmtpRecipientValidationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.handler = smtp_receiver.EmailReceiverHandler()
        self.session = SimpleNamespace(peer=("203.0.113.10", 12345))
        self.envelope = SimpleNamespace(rcpt_tos=[])

    async def test_rejects_recipient_outside_local_domains(self):
        result = await self.handler.handle_RCPT(
            None, self.session, self.envelope, "victim@example.net", [],
        )

        self.assertTrue(result.startswith("550"))
        self.assertEqual(self.envelope.rcpt_tos, [])

    async def test_rejects_unknown_local_mailbox(self):
        with patch.object(smtp_receiver, "mailbox_exists", AsyncMock(return_value=False)):
            result = await self.handler.handle_RCPT(
                None, self.session, self.envelope, "unknown@zenime.my.id", [],
            )

        self.assertTrue(result.startswith("550"))
        self.assertEqual(self.envelope.rcpt_tos, [])

    async def test_accepts_registered_active_mailbox(self):
        with patch.object(smtp_receiver, "mailbox_exists", AsyncMock(return_value=True)):
            result = await self.handler.handle_RCPT(
                None, self.session, self.envelope, "Bantuan@Zenime.My.Id", [],
            )

        self.assertTrue(result.startswith("250"))
        self.assertEqual(self.envelope.rcpt_tos, ["bantuan@zenime.my.id"])


if __name__ == "__main__":
    unittest.main()
