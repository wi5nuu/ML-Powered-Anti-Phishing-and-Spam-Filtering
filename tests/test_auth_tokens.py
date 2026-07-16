import os
import unittest

from fastapi import HTTPException

# Authentication imports the dashboard database module, so keep this unit test
# independent from the PostgreSQL hostname that only exists inside Docker.
os.environ["DASHBOARD_DB_URL"] = "sqlite:///:memory:"

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
        replacement = "a" if token[-1] != "a" else "b"

        with self.assertRaises(HTTPException) as raised:
            decode_token(token[:-1] + replacement)

        self.assertEqual(raised.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
