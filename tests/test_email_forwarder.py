import unittest
from email import policy
from email.parser import BytesParser

from worker.email_forwarder import _prepare_forward_message, build_warning_xai_header


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
        xai_header = build_warning_xai_header(0.75, {
            "ml_probability": 0.8123,
            "sa_score": 2.5,
            "anomaly_score": 0.3456,
            "shap_features": [{"name": "url_count", "shap": 0.4312}],
            "routing_reason": "Borderline score from real detectors",
        })
        forwarded = _prepare_forward_message(
            "From: sender@example.net\r\n\r\nHello",
            "bantuan@zenime.my.id",
            ["destination@gmail.com"],
            "WARN",
            0.75,
            xai_header,
        )
        message = BytesParser(policy=policy.default).parsebytes(forwarded)

        self.assertEqual(message["X-CogniMail-Classification"], "WARN")
        self.assertIn("Fused=0.7500", message["X-Spam-Reason"])
        self.assertIn("ML=0.8123", message["X-Spam-Reason"])
        self.assertIn("TopSHAP=url_count:+0.4312", message["X-Spam-Reason"])

    def test_warn_header_strips_untrusted_line_breaks(self):
        header = build_warning_xai_header(0.7, {
            "routing_reason": "measured\r\nX-Forged: yes",
        })
        self.assertNotIn("\r", header)
        self.assertNotIn("\n", header)
        self.assertIn("X-Forged: yes", header)


if __name__ == "__main__":
    unittest.main()
