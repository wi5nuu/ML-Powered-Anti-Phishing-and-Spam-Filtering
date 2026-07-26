import unittest

from decision_engine.content_guard import content_threat_evidence, dangerous_attachment_name


class ContentThreatGuardTests(unittest.TestCase):
    def test_credential_harvesting_with_external_link_is_phishing(self):
        raw = """Subject: Payment confirmation required

Immediate action required. Confirm your banking password and credit card
details at http://zenime-security.example/confirm within 30 minutes.
"""
        category, reason = content_threat_evidence(raw, 0.8004, 5.5, 0.6934)
        self.assertEqual(category, "phishing")
        self.assertIn("credential request", reason)

    def test_ceo_wire_transfer_with_secrecy_is_phishing(self):
        raw = """Subject: CEO wire transfer

I am in a meeting and need an urgent confidential wire transfer today.
Do not discuss this request. Reply with the bank confirmation.
"""
        category, reason = content_threat_evidence(raw, 0.3281, 6.5, 0.4523)
        self.assertEqual(category, "phishing")
        self.assertIn("BEC payment request", reason)

    def test_mailbox_scare_with_login_link_is_phishing(self):
        raw = """Subject: Mailbox quota warning

Your mailbox is full and will be deleted. Login immediately at
http://mailbox-zenime.example/verify to retain access.
"""
        category, reason = content_threat_evidence(raw, 0.4418, 5.5, 0.7180)
        self.assertEqual(category, "phishing")
        self.assertIn("account/mailbox pressure", reason)

    def test_normal_invoice_review_has_no_threat_evidence(self):
        raw = """Subject: Invoice review

Hello Finance, please review the legitimate invoice summary for vendor ACME
and confirm the payment schedule during business hours.
"""
        category, reason = content_threat_evidence(raw, 0.1497, 1.0, 0.20)
        self.assertEqual((category, reason), ("", ""))

    def test_indonesian_promotion_with_high_ml_score_is_spam(self):
        raw = """Subject: Promo hadiah gratis

Anda pemenang undian. Klaim hadiah gratis dan beli sekarang karena
penawaran terbatas hanya hari ini.
"""
        category, reason = content_threat_evidence(raw, 0.79, 0.8, 0.42)
        self.assertEqual(category, "spam")
        self.assertIn("strong spam language", reason)

    def test_indonesian_card_confirmation_link_is_phishing(self):
        raw = """Subject: Paket tertahan

Paket Anda tertahan. Konfirmasi kartu di
http://parcel-fee.example/pay hari ini agar paket tidak dikembalikan.
"""
        category, reason = content_threat_evidence(raw, 0.98, 0.8, 0.68)
        self.assertEqual(category, "phishing")
        self.assertIn("credential request", reason)

    def test_executable_attachment_is_quarantined_as_phishing(self):
        raw = """Subject: Invoice
Content-Disposition: attachment; filename="invoice.exe"

Please see the attached invoice.
"""
        self.assertEqual(dangerous_attachment_name(raw), "invoice.exe")
        category, reason = content_threat_evidence(raw, 0.0, 0.0, 0.0)
        self.assertEqual(category, "phishing")
        self.assertIn("dangerous attachment=invoice.exe", reason)


if __name__ == "__main__":
    unittest.main()
