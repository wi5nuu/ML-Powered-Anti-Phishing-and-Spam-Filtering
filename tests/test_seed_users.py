import os
import unittest

os.environ["ENV"] = "testing"
os.environ["DASHBOARD_DB_URL"] = "sqlite:///:memory:"

from dashboard.app import _upsert_seed_user  # noqa: E402
from dashboard.auth import hash_password, verify_password  # noqa: E402
from dashboard.database import SessionLocal  # noqa: E402
from database.models import User  # noqa: E402


class SeedUserTests(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_custom_password_survives_restart_seed(self):
        user = User(
            username="seed-custom-test",
            hashed_password=hash_password("already-changed-password"),
            role="admin",
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()

        _upsert_seed_user(
            self.db,
            "seed-custom-test",
            "password-from-env",
            "admin",
            insecure_passwords=["admin"],
        )

        self.assertTrue(verify_password("already-changed-password", user.hashed_password))
        self.db.delete(user)
        self.db.commit()

    def test_default_password_is_upgraded_from_environment(self):
        user = User(
            username="seed-default-test",
            hashed_password=hash_password("admin"),
            role="admin",
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()

        _upsert_seed_user(
            self.db,
            "seed-default-test",
            "password-from-env",
            "admin",
            insecure_passwords=["admin"],
        )

        self.assertTrue(verify_password("password-from-env", user.hashed_password))
        self.db.delete(user)
        self.db.commit()


if __name__ == "__main__":
    unittest.main()
