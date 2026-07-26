import os
import unittest
from unittest.mock import patch

# Must be set BEFORE any project imports so dashboard.database uses SQLite
os.environ["ENV"] = "testing"
os.environ["DASHBOARD_DB_URL"] = "sqlite:///:memory:"

from dashboard.app import _upsert_seed_user, seed_admin  # noqa: E402
from dashboard.auth import hash_password, verify_password  # noqa: E402
from dashboard.database import engine, SessionLocal  # noqa: E402
from database.models import Base, User  # noqa: E402


class SeedUserTests(unittest.TestCase):
    def setUp(self):
        # Each test gets a fresh in-memory schema so rows don't bleed between tests
        Base.metadata.create_all(engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()
        # Drop all tables so the next setUp starts clean
        Base.metadata.drop_all(engine)

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

    def test_startup_does_not_recreate_admin_or_user_from_environment(self):
        renamed_admin = User(
            username="renamed-admin",
            hashed_password=hash_password("DatabaseAdmin9"),
            role="admin",
            is_active=True,
        )
        database_user = User(
            username="database-user",
            hashed_password=hash_password("DatabaseUser9"),
            role="user",
            is_active=True,
        )
        self.db.add_all([renamed_admin, database_user])
        self.db.commit()

        with patch.dict(
            os.environ,
            {
                "ADMIN_USERNAME": "admin-from-env",
                "ADMIN_PASSWORD": "AdminFromEnv9",
                "USER_USERNAME": "user-from-env",
                "USER_PASSWORD": "UserFromEnv9",
            },
        ):
            seed_admin()

        self.assertIsNone(
            self.db.query(User).filter(User.username == "admin-from-env").first()
        )
        self.assertIsNone(
            self.db.query(User).filter(User.username == "user-from-env").first()
        )
        self.assertIsNotNone(
            self.db.query(User).filter(User.username == "renamed-admin").first()
        )
        self.assertIsNotNone(
            self.db.query(User).filter(User.username == "database-user").first()
        )


if __name__ == "__main__":
    unittest.main()
