import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

os.environ["ENV"] = "testing"
os.environ["DASHBOARD_DB_URL"] = "sqlite:///:memory:"
os.environ.setdefault("DASHBOARD_SECRET_KEY", "test-secret-key-that-is-long-enough")

from dashboard.app import append_thread_context, email_body_preview  # noqa: E402
from worker.pipeline_worker import parse_message_for_storage  # noqa: E402


class EmailThreadingTests(unittest.TestCase):
    def test_reply_uses_collapsible_gmail_quote_without_escaped_breaks(self):
        original = SimpleNamespace(
            sender="Muhammad Briliantama <sender@example.org>",
            received_at=datetime(2026, 7, 24, 5, 2, 52, tzinfo=timezone.utc),
            subject="halo",
            recipient_list="bantuan@example.org",
            raw_content="halo",
        )

        rendered = append_thread_context("halo briliant", original, "reply")

        self.assertIn('<div dir="ltr">halo briliant</div><br>', rendered)
        self.assertIn('class="gmail_quote gmail_quote_container"', rendered)
        self.assertIn('class="gmail_attr"', rendered)
        self.assertIn('<blockquote class="gmail_quote"', rendered)
        self.assertNotIn("&lt;br&gt;", rendered)
        self.assertNotIn("2026-07-24 05:02:52.323315+00", rendered)

    def test_incoming_message_keeps_threading_headers(self):
        raw_email = (
            "From: Sender <sender@example.org>\r\n"
            "To: bantuan@example.org\r\n"
            "Subject: Re: halo\r\n"
            "Message-ID: <reply-2@example.org>\r\n"
            "In-Reply-To: <original-1@example.org>\r\n"
            "References: <original-1@example.org> <reply-1@example.org>\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n"
            "\r\n"
            "Balasan baru"
        )

        parsed = parse_message_for_storage(raw_email, {})

        self.assertEqual(parsed["message_id_header"], "<reply-2@example.org>")
        self.assertEqual(
            parsed["references_header"],
            "<original-1@example.org> <reply-1@example.org>",
        )

    def test_preview_decodes_legacy_html_and_hides_quoted_history(self):
        legacy = (
            'halo briliant&lt;br&gt;&lt;br&gt;'
            '&lt;div class="gmail_quote"&gt;Pada tanggal lama menulis:'
            '&lt;blockquote&gt;isi lama&lt;/blockquote&gt;&lt;/div&gt;'
        )

        self.assertEqual(email_body_preview(legacy), "halo briliant")


if __name__ == "__main__":
    unittest.main()
