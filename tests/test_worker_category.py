import os
import unittest

os.environ.setdefault("ENV", "testing")
os.environ["WORKER_DB_URL"] = "postgresql+asyncpg://test:test@localhost:5432/test"

from decision_engine.fusion import FusionResult  # noqa: E402
from worker.pipeline_worker import (  # noqa: E402
    apply_content_guard,
    infer_threat_category,
    parse_message_for_storage,
)


class WorkerCategoryTests(unittest.TestCase):
    def test_legacy_malware_category_is_phishing(self):
        self.assertEqual(
            infer_threat_category("", "QUARANTINE", "malware"),
            "phishing",
        )

    def test_dangerous_attachment_overrides_spam_category(self):
        raw = 'Content-Disposition: attachment; filename="payload.vbs"'
        self.assertEqual(
            infer_threat_category(raw, "QUARANTINE", "spam"),
            "phishing",
        )

    def test_envelope_recipient_cannot_be_overridden_by_to_header(self):
        raw = (
            "From: attacker@example.test\r\n"
            "To: victim@example.test\r\n"
            "Subject: forged routing target\r\n\r\nbody"
        )
        parsed = parse_message_for_storage(
            raw,
            {"recipients": ["actual-mailbox@zenime.my.id"]},
        )
        self.assertEqual(parsed["recipients"], ["actual-mailbox@zenime.my.id"])

    def test_warn_with_executable_attachment_is_upgraded_to_quarantine(self):
        warning = FusionResult(
            sa_score=4.0,
            ml_probability=0.6,
            anomaly_score=0.4,
            sa_normalized=0.2,
            fused_score=0.62,
            label="WARN",
            routing_reason="Review required",
        )
        guarded, category = apply_content_guard(
            warning,
            'Content-Disposition: attachment; filename="invoice.exe"',
            0.6,
            4.0,
            0.4,
        )
        self.assertEqual(guarded.label, "QUARANTINE")
        self.assertEqual(category, "phishing")

    def test_existing_quarantine_still_gets_content_category(self):
        quarantined = FusionResult(
            sa_score=0.8,
            ml_probability=0.98,
            anomaly_score=0.68,
            sa_normalized=0.04,
            fused_score=0.68,
            label="QUARANTINE",
            routing_reason="ML review threshold",
        )
        guarded, category = apply_content_guard(
            quarantined,
            "Konfirmasi kartu di http://parcel-fee.example/pay hari ini.",
            0.98,
            0.8,
            0.68,
        )
        self.assertIs(guarded, quarantined)
        self.assertEqual(category, "phishing")


if __name__ == "__main__":
    unittest.main()
