import base64
import os
import unittest
from email.mime.text import MIMEText
from unittest.mock import patch

import dkim
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from mail_delivery.dkim_signer import DkimConfigurationError, sign_outbound_message


class DkimSignerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.private_pem = cls.key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
        public_der = cls.key.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        cls.dns_record = b"v=DKIM1; k=rsa; p=" + base64.b64encode(public_der)

    def _message(self):
        message = MIMEText("DKIM test", "plain", "utf-8")
        message["From"] = "bantuan@zenime.my.id"
        message["To"] = "recipient@example.net"
        message["Subject"] = "DKIM test"
        message["Date"] = "Fri, 24 Jul 2026 00:00:00 GMT"
        message["Message-ID"] = "<test@zenime.my.id>"
        return message

    def test_signs_and_verifies_outbound_message(self):
        env = {
            "OUTBOUND_DKIM_PRIVATE_KEY_B64": base64.b64encode(self.private_pem).decode(),
            "OUTBOUND_DKIM_DOMAIN": "zenime.my.id",
            "OUTBOUND_DKIM_SELECTOR": "cognimail",
            "OUTBOUND_DKIM_REQUIRED": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            signed = sign_outbound_message(self._message(), "bantuan@zenime.my.id")

        self.assertTrue(signed.startswith(b"DKIM-Signature:"))
        self.assertTrue(dkim.verify(signed, dnsfunc=lambda _name, **_kwargs: self.dns_record))

    def test_required_dkim_rejects_missing_private_key(self):
        env = {
            "OUTBOUND_DKIM_PRIVATE_KEY_B64": "",
            "OUTBOUND_DKIM_PRIVATE_KEY": "",
            "OUTBOUND_DKIM_PRIVATE_KEY_FILE": "",
            "OUTBOUND_DKIM_REQUIRED": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaises(DkimConfigurationError):
                sign_outbound_message(self._message(), "bantuan@zenime.my.id")


if __name__ == "__main__":
    unittest.main()
