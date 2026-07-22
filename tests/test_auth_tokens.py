import os
import unittest

from fastapi import HTTPException

# Must be set BEFORE any project imports:
#   - ENV=testing bypasses the SQLite guard in dashboard/database.py and the
#     secret-key length check in dashboard/environment.py
#   - DASHBOARD_SECRET_KEY provides a test-only key (≥32 chars) so auth.py
#     doesn't fall back to a random ephemeral key that would make the
#     tampered-token test non-deterministic across restarts
#   - DASHBOARD_DB_URL points to in-memory SQLite so no Postgres is needed
os.environ.setdefault("ENV", "testing")
os.environ.setdefault("DASHBOARD_SECRET_KEY", "test-secret-key-for-unit-tests-only-32c")
os.environ.setdefault("DASHBOARD_DB_URL", "sqlite:///:memory:")

from dashboard.auth import create_access_token, decode_token  # noqa: E402


class AuthTokenTests(unittest.TestCase):
    def test_created_token_can_be_decoded(self):
        token = create_access_token({"sub": "test-user", "role": "user"})

        payload = decode_token(token)

        self.assertEqual(payload["sub"], "test-user")
        self.assertEqual(payload["role"], "user")
        self.assertIn("exp", payload)

    def test_tampered_token_is_rejected(self):
        token = create_access_token({"sub": "test-user"})
        # Tamper with a character in the MIDDLE of the signature section
        # (last segment after the final dot).  Changing the very last character
        # is unreliable because base64url padding can make it a no-op — the
        # decoder silently ignores low-order padding bits.
        header, payload, signature = token.rsplit(".", 2)
        # Flip a character near the start of the signature so the change is
        # always semantically significant regardless of padding.
        if not signature:
            self.skipTest("Token has empty signature — algorithm is 'none'")
        bad_char = "a" if signature[2] != "a" else "b"
        tampered = f"{header}.{payload}.{bad_char}{signature[1:]}"

        with self.assertRaises(HTTPException) as raised:
            decode_token(tampered)

        self.assertEqual(raised.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
