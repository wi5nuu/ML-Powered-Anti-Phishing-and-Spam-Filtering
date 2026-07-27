import unittest
from email.message import EmailMessage

from classifier.features import EmailParser, FeatureExtractor


class ClassifierFeatureRegressionTests(unittest.TestCase):
    def _extract(self, display_name: str, html_body: str, text_body: str):
        message = EmailMessage()
        message["From"] = f"{display_name} <lapakonline867@gmail.com>"
        message["To"] = "bantuan@zenime.my.id"
        message["Subject"] = "Selamat Datang di Sistem Kami!"
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")
        return FeatureExtractor().extract(EmailParser().parse(message.as_string()))

    def test_person_name_containing_bri_is_not_bank_impersonation(self):
        text = "Halo. Terima kasih sudah mendaftar. Akun Anda berhasil dibuat."
        features = self._extract(
            "Muhammad Ahda Briliantama",
            f"<div>{text}</div>",
            text,
        )

        self.assertFalse(features.display_name_mismatch)

    def test_gmail_wrapper_markup_does_not_inflate_html_text_ratio(self):
        text = "Halo. Terima kasih sudah mendaftar. Akun Anda berhasil dibuat."
        wrappers = '<span class="gmail_extra"></span>' * 100
        features = self._extract(
            "Muhammad Ahda Briliantama",
            f'<div dir="ltr"><div>{text}</div>{wrappers}</div>',
            text,
        )

        self.assertLessEqual(features.html_text_ratio, 1.1)

    def test_real_brand_name_from_unrelated_domain_is_still_detected(self):
        text = "Informasi akun Anda."
        features = self._extract("Bank BRI", f"<div>{text}</div>", text)

        self.assertTrue(features.display_name_mismatch)


if __name__ == "__main__":
    unittest.main()
