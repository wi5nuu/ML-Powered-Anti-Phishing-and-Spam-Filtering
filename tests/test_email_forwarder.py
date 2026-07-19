import unittest
from email import policy
from email.parser import BytesParser

from worker.email_forwarder import _prepare_forward_message


class ForwardMessageTests(unittest.TestCase):
    def test_rewrites_sender_for_dmarc_and_preserves_reply_address(self):
        raw = (
            "From: Sender <sender@example.net>\r\n"
            "To: bantuan@zenime.my.id\r\n"
            "Return-Path: <bounce@example.net>\r\n"
            "Subject: Test\r\n\r\nHello"
        )

        forwarded = _prepare_forward_message(
            raw,
            "bantuan@zenime.my.id",
            ["destination@gmail.com"],
            "CLEAN",
            0.1,
        )
        message = BytesParser(policy=policy.default).parsebytes(forwarded)

        self.assertEqual(message["From"], "bantuan@zenime.my.id")
        self.assertEqual(message["To"], "destination@gmail.com")
        self.assertEqual(message["Reply-To"], "Sender <sender@example.net>")
        self.assertEqual(
            message["X-CogniMail-Original-From"],
            "Sender <sender@example.net>",
        )
        self.assertIsNone(message["Return-Path"])

    def test_warn_message_gets_scan_header(self):
        forwarded = _prepare_forward_message(
            "From: sender@example.net\r\n\r\nHello",
            "bantuan@zenime.my.id",
            ["destination@gmail.com"],
            "WARN",
            0.75,
        )
        message = BytesParser(policy=policy.default).parsebytes(forwarded)

        self.assertIn("0.75", message["X-Spam-Reason"])


if __name__ == "__main__":
    unittest.main()
