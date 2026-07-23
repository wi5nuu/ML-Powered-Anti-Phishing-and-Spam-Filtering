import io
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["ENV"] = "testing"
os.environ["DASHBOARD_DB_URL"] = "sqlite:///:memory:"
os.environ.setdefault("DASHBOARD_SECRET_KEY", "test-secret-key-that-is-long-enough")

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from dashboard.app import app  # noqa: E402
from dashboard.auth import hash_password  # noqa: E402
from dashboard.database import get_db  # noqa: E402
from database.models import (  # noqa: E402
    AdminMailbox,
    AdminMailboxAccess,
    AuditLog,
    AuditTrail,
    Base,
    Feedback,
    Organization,
    QuarantineEmail,
    TrainingSample,
    User,
)


test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


class DashboardUserFlowTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(test_engine)
        Base.metadata.create_all(test_engine)
        app.dependency_overrides[get_db] = override_get_db
        self.db = TestingSessionLocal()
        self.organization = Organization(name="Route Test Organization")
        self.superadmin = User(
            username="route-test-superadmin",
            email="route-superadmin@example.test",
            hashed_password=hash_password("test-password-123"),
            role="superadmin",
            is_active=True,
        )
        self.db.add_all([self.organization, self.superadmin])
        self.db.commit()
        self.client = TestClient(app, base_url="http://localhost")
        response = self.client.post(
            "/api/auth/login",
            data={"username": self.superadmin.username, "password": "test-password-123"},
        )
        self.assertEqual(response.status_code, 200, response.text)

    def tearDown(self):
        self.client.close()
        self.db.close()
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(test_engine)

    def test_api_routes_have_no_duplicate_method_and_shape(self):
        seen = {}
        duplicates = []
        for route in app.routes:
            normalized = re.sub(r"\{[^}]+\}", "{}", getattr(route, "path", ""))
            for method in getattr(route, "methods", set()) or set():
                if method in {"HEAD", "OPTIONS"}:
                    continue
                key = (method, normalized)
                if key in seen:
                    duplicates.append((key, seen[key], route.name))
                seen[key] = route.name
        self.assertEqual(duplicates, [])

    def test_snoozed_mailbox_page_does_not_crash(self):
        response = self.client.get("/api/emails", params={"folder": "snoozed"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("emails", response.json())

    def test_read_status_updates_the_entire_reply_thread(self):
        messages = [
            QuarantineEmail(
                email_id="thread-incoming-1",
                subject="Status thread",
                label="CLEAN",
                status="released",
                fused_score=0.0,
                sender="Sender <sender@example.test>",
                recipient_list="mailbox@example.test",
                is_read=True,
            ),
            QuarantineEmail(
                email_id="thread-sent-1",
                subject="Re: Status thread",
                label="SENT",
                status="sent",
                fused_score=0.0,
                sender="mailbox@example.test",
                recipient_list="Sender <sender@example.test>",
                is_read=False,
            ),
            QuarantineEmail(
                email_id="thread-incoming-2",
                subject="Re: Status thread",
                label="CLEAN",
                status="released",
                fused_score=0.0,
                sender="Sender <sender@example.test>",
                recipient_list="mailbox@example.test",
                is_read=False,
            ),
        ]
        self.db.add_all(messages)
        self.db.commit()

        response = self.client.put("/api/emails/thread-incoming-1/read", json={"is_read": True})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["updated_count"], 2)
        self.db.expire_all()
        incoming = self.db.query(QuarantineEmail).filter(
            QuarantineEmail.email_id.in_(["thread-incoming-1", "thread-incoming-2"])
        ).all()
        self.assertTrue(all(message.is_read for message in incoming))

        detail = self.client.get("/api/emails/thread-incoming-1")
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertTrue(detail.json()["thread_is_read"])
        self.assertFalse(detail.json()["thread_has_unread"])

        response = self.client.put("/api/emails/thread-incoming-2/read", json={"is_read": False})
        self.assertEqual(response.status_code, 200, response.text)
        self.db.expire_all()
        incoming = self.db.query(QuarantineEmail).filter(
            QuarantineEmail.email_id.in_(["thread-incoming-1", "thread-incoming-2"])
        ).all()
        self.assertTrue(all(not message.is_read for message in incoming))

    def test_superadmin_can_create_and_hard_delete_admin_by_username(self):
        with patch.dict(os.environ, {"VITE_MAIL_DOMAIN": "example.test"}):
            create_response = self.client.post(
                "/api/admin/users",
                json={
                    "username": "delete-flow-admin",
                    "email": "delete-flow-admin@example.test",
                    "password": "test-password-123",
                    "role": "admin",
                },
            )
        self.assertEqual(create_response.status_code, 201, create_response.text)

        delete_response = self.client.delete("/api/admin/users/delete-flow-admin/hard")
        self.assertEqual(delete_response.status_code, 200, delete_response.text)
        self.assertIsNone(
            self.db.query(User).filter(User.username == "delete-flow-admin").first()
        )

    def test_profile_avatar_upload_and_profile_response(self):
        image_buffer = io.BytesIO()
        Image.new("RGB", (32, 32), color=(30, 100, 220)).save(image_buffer, format="PNG")
        image_buffer.seek(0)

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("dashboard.app.static_dir", Path(temp_dir)):
                upload_response = self.client.post(
                    "/api/auth/profile/avatar",
                    files={"avatar": ("avatar.png", image_buffer.getvalue(), "image/png")},
                )
                self.assertEqual(upload_response.status_code, 200, upload_response.text)
                avatar_url = upload_response.json()["avatar_url"]
                self.assertTrue(avatar_url.startswith("/static/avatars/user_"))
                self.assertTrue((Path(temp_dir) / "avatars" / Path(avatar_url).name).is_file())

                profile_response = self.client.get("/api/auth/profile")
                self.assertEqual(profile_response.status_code, 200, profile_response.text)
                self.assertEqual(profile_response.json()["avatar_url"], avatar_url)

    def test_global_admin_cannot_manage_users_but_can_manage_domain_mailboxes(self):
        admin = User(
            username="domain-admin",
            email="admin@managed.test",
            hashed_password=hash_password("test-password-123"),
            role="admin",
            organization_id=None,
            is_active=True,
        )
        self.db.add(admin)
        self.db.commit()

        admin_client = TestClient(app, base_url="http://localhost")
        try:
            login_response = admin_client.post(
                "/api/auth/login",
                data={"username": admin.username, "password": "test-password-123"},
            )
            self.assertEqual(login_response.status_code, 200, login_response.text)

            with patch.dict(os.environ, {"VITE_MAIL_DOMAIN": "managed.test"}):
                config_response = admin_client.get("/api/admin/config")
                self.assertEqual(config_response.status_code, 200, config_response.text)
                self.assertEqual(config_response.json()["mail_domain"], "managed.test")

                create_user_response = admin_client.post(
                    "/api/admin/users",
                    json={
                        "username": "managed-user",
                        "email": "managed-user@managed.test",
                        "password": "test-password-123",
                        "role": "user",
                    },
                )
                self.assertEqual(create_user_response.status_code, 403, create_user_response.text)

                list_response = admin_client.get("/api/admin/users")
                self.assertEqual(list_response.status_code, 403, list_response.text)

                mailbox_response = admin_client.post(
                    "/api/admin/mailboxes",
                    json={
                        "email": "support@managed.test",
                        "domain": "managed.test",
                        "password": "Strong-Test-123!",
                        "sender_name": "Support",
                    },
                )
                self.assertEqual(mailbox_response.status_code, 200, mailbox_response.text)
                mailbox_id = self.db.query(AdminMailbox).filter(
                    AdminMailbox.email == "support@managed.test"
                ).one().id

                forward_response = admin_client.put(
                    f"/api/admin/mailboxes/{mailbox_id}/forwarder",
                    json={
                        "target": "archive@example.test",
                        "enabled": True,
                        "keep_copy": True,
                    },
                )
                self.assertEqual(forward_response.status_code, 200, forward_response.text)
                self.assertTrue(forward_response.json()["forward_enabled"])

                token_response = admin_client.post(
                    f"/api/admin/mailboxes/{mailbox_id}/autologin-token"
                )
                self.assertEqual(token_response.status_code, 200, token_response.text)
                self.assertTrue(token_response.json().get("token"))
        finally:
            admin_client.close()

    def test_mailbox_listing_login_and_empty_inbox(self):
        mailbox = AdminMailbox(
            email="route-inbox@example.test",
            domain="example.test",
            password_hash=hash_password("mailbox-password-123"),
            sender_name="Route Inbox",
            created_by=self.superadmin.username,
            is_active=True,
        )
        self.db.add(mailbox)
        self.db.flush()
        self.db.add(
            AdminMailboxAccess(
                mailbox_id=mailbox.id,
                username=self.superadmin.username,
            )
        )
        self.db.commit()

        list_response = self.client.get("/api/user/mailboxes")
        self.assertEqual(list_response.status_code, 200, list_response.text)
        self.assertIn(mailbox.id, [item["id"] for item in list_response.json()])

        token_response = self.client.post(
            f"/api/admin/mailboxes/{mailbox.id}/autologin-token"
        )
        self.assertEqual(token_response.status_code, 200, token_response.text)
        autologin_client = TestClient(app, base_url="http://localhost")
        try:
            redeem_response = autologin_client.post(
                "/api/mailboxes/autologin",
                json={"token": token_response.json()["token"]},
            )
            self.assertEqual(redeem_response.status_code, 200, redeem_response.text)
            me_response = autologin_client.get("/api/auth/me")
            self.assertEqual(me_response.status_code, 200, me_response.text)
            self.assertTrue(me_response.json()["authenticated"])
            self.assertEqual(me_response.json()["user"]["role"], "mailbox")
            autologin_inbox = autologin_client.get(
                "/api/emails",
                params={"mailbox_id": mailbox.id, "mailbox": mailbox.email},
            )
            self.assertEqual(autologin_inbox.status_code, 200, autologin_inbox.text)
        finally:
            autologin_client.close()

        mailbox_client = TestClient(app, base_url="http://localhost")
        try:
            login_response = mailbox_client.post(
                "/api/mailboxes/login",
                json={
                    "email": mailbox.email,
                    "password": "mailbox-password-123",
                },
            )
            self.assertEqual(login_response.status_code, 200, login_response.text)

            profile_response = mailbox_client.get("/api/auth/profile")
            self.assertEqual(profile_response.status_code, 200, profile_response.text)
            self.assertEqual(profile_response.json()["mailbox_email"], mailbox.email)

            inbox_response = mailbox_client.get("/api/emails")
            self.assertEqual(inbox_response.status_code, 200, inbox_response.text)
        finally:
            mailbox_client.close()

    def test_mailbox_status_and_permanent_delete_are_distinct_and_atomic(self):
        mailbox = AdminMailbox(
            email="delete-me@managed.test",
            domain="managed.test",
            password_hash=hash_password("Strong-Test-123!"),
            sender_name="Delete Me",
            assigned_to="mailbox-manager",
            created_by=self.superadmin.username,
            is_active=True,
        )
        manager = User(
            username="mailbox-manager",
            email="manager@managed.test",
            hashed_password=hash_password("Strong-Test-123!"),
            role="admin",
            is_active=True,
        )
        incoming = QuarantineEmail(
            email_id="delete-incoming",
            label="CLEAN",
            fused_score=0.0,
            status="released",
            sender="Sender <sender@example.test>",
            recipient_list="Delete Me <delete-me@managed.test>",
        )
        outgoing = QuarantineEmail(
            email_id="delete-outgoing",
            label="SENT",
            fused_score=0.0,
            status="sent",
            sender="Delete Me <delete-me@managed.test>",
            recipient_list="recipient@example.test",
        )
        unrelated = QuarantineEmail(
            email_id="keep-unrelated",
            label="CLEAN",
            fused_score=0.0,
            status="released",
            sender="sender@example.test",
            recipient_list="other@managed.test",
        )
        self.db.add_all([manager, mailbox, incoming, outgoing, unrelated])
        self.db.flush()
        self.db.add_all([
            AdminMailboxAccess(mailbox_id=mailbox.id, username=manager.username),
            Feedback(email_id=incoming.email_id, feedback_type="correct", notes="delete"),
            TrainingSample(
                email_id=outgoing.email_id,
                raw_email="raw",
                original_label="CLEAN",
                corrected_label="spam",
                feedback_type="relabel",
                reported_by=manager.username,
            ),
            AuditLog(user=manager.username, action="read", email_id=incoming.email_id),
            AuditTrail(
                actor=manager.username,
                action="inference",
                target_type="email",
                target_id=outgoing.email_id,
                status="SUCCESS",
            ),
        ])
        self.db.commit()
        mailbox_id = mailbox.id
        incoming_id = incoming.email_id
        outgoing_id = outgoing.email_id
        unrelated_id = unrelated.email_id

        access_before = self.client.get(f"/api/mailboxes/{mailbox_id}/access")
        self.assertEqual(access_before.status_code, 200, access_before.text)

        token_response = self.client.post(
            f"/api/admin/mailboxes/{mailbox_id}/autologin-token"
        )
        self.assertEqual(token_response.status_code, 200, token_response.text)
        mailbox_client = TestClient(app, base_url="http://localhost")
        redeem = mailbox_client.post(
            "/api/mailboxes/autologin", json={"token": token_response.json()["token"]}
        )
        self.assertEqual(redeem.status_code, 200, redeem.text)
        mailbox_me = mailbox_client.get("/api/auth/me")
        self.assertTrue(mailbox_me.json()["authenticated"])

        disable = self.client.put(
            f"/api/admin/mailboxes/{mailbox_id}", json={"is_active": False}
        )
        self.assertEqual(disable.status_code, 200, disable.text)
        self.assertFalse(disable.json()["is_active"])
        self.assertEqual(
            self.db.query(AdminMailboxAccess).filter_by(mailbox_id=mailbox_id).count(), 1
        )
        self.assertEqual(self.db.query(QuarantineEmail).count(), 3)
        disabled_access = self.client.get(f"/api/mailboxes/{mailbox_id}/access")
        self.assertEqual(disabled_access.status_code, 404, disabled_access.text)

        activate = self.client.put(
            f"/api/admin/mailboxes/{mailbox_id}", json={"is_active": True}
        )
        self.assertEqual(activate.status_code, 200, activate.text)
        self.assertTrue(activate.json()["is_active"])
        self.assertEqual(
            self.db.query(AdminMailboxAccess).filter_by(mailbox_id=mailbox_id).count(), 1
        )
        active_access = self.client.get(f"/api/mailboxes/{mailbox_id}/access")
        self.assertEqual(active_access.status_code, 200, active_access.text)

        permanent_delete = self.client.delete(f"/api/admin/mailboxes/{mailbox_id}")
        self.assertEqual(permanent_delete.status_code, 200, permanent_delete.text)
        self.assertEqual(permanent_delete.json()["deleted"]["emails"], 2)
        self.db.expire_all()
        self.assertIsNone(self.db.query(AdminMailbox).filter_by(id=mailbox_id).first())
        self.assertEqual(
            [row.email_id for row in self.db.query(QuarantineEmail).all()],
            [unrelated_id],
        )
        self.assertEqual(self.db.query(Feedback).filter_by(email_id=incoming_id).count(), 0)
        self.assertEqual(self.db.query(TrainingSample).filter_by(email_id=outgoing_id).count(), 0)
        self.assertEqual(self.db.query(AuditLog).filter_by(email_id=incoming_id).count(), 0)
        self.assertEqual(self.db.query(AuditTrail).filter_by(target_id=outgoing_id).count(), 0)
        self.assertEqual(self.db.query(AdminMailboxAccess).filter_by(mailbox_id=mailbox_id).count(), 0)
        deleted_access = self.client.get(f"/api/mailboxes/{mailbox_id}/access")
        self.assertEqual(deleted_access.status_code, 404, deleted_access.text)
        deleted_inbox = self.client.get(
            "/api/emails", params={"mailbox_id": mailbox_id, "folder": "inbox"}
        )
        self.assertEqual(deleted_inbox.status_code, 404, deleted_inbox.text)
        deleted_mailbox_me = mailbox_client.get("/api/auth/me")
        self.assertFalse(deleted_mailbox_me.json()["authenticated"])
        mailbox_client.close()

    def test_admin_mailbox_ownership_is_strict_and_reassignment_is_atomic(self):
        password = "Strong-Test-123!"
        admin_one = User(
            username="mail-admin-one",
            email="admin-one@managed.test",
            hashed_password=hash_password(password),
            role="admin",
            is_active=True,
        )
        admin_two = User(
            username="mail-admin-two",
            email="admin-two@managed.test",
            hashed_password=hash_password(password),
            role="admin",
            is_active=True,
        )
        mailbox_a = AdminMailbox(
            email="a@managed.test",
            domain="managed.test",
            password_hash=hash_password(password),
            sender_name="Mailbox A",
            assigned_to=admin_one.username,
            created_by=self.superadmin.username,
            is_active=True,
        )
        mailbox_b = AdminMailbox(
            email="b@managed.test",
            domain="managed.test",
            password_hash=hash_password(password),
            sender_name="Mailbox B",
            assigned_to=admin_two.username,
            created_by=self.superadmin.username,
            is_active=True,
        )
        self.db.add_all([admin_one, admin_two, mailbox_a, mailbox_b])
        self.db.flush()
        self.db.add_all([
            AdminMailboxAccess(mailbox_id=mailbox_a.id, username=admin_one.username),
            AdminMailboxAccess(mailbox_id=mailbox_b.id, username=admin_two.username),
            QuarantineEmail(
                email_id="mailbox-a-draft-1",
                label="DRAFT",
                fused_score=0.0,
                status="draft",
                sender=mailbox_a.email,
                recipient_list="recipient@example.test",
            ),
            QuarantineEmail(
                email_id="mailbox-a-draft-2",
                label="DRAFT",
                fused_score=0.0,
                status="draft",
                sender=mailbox_a.email,
                recipient_list="recipient@example.test",
            ),
            QuarantineEmail(
                email_id="mailbox-b-clean-1",
                label="CLEAN",
                fused_score=0.0,
                status="released",
                sender="sender@example.test",
                recipient_list=mailbox_b.email,
            ),
        ])
        self.db.commit()

        def login_admin(username):
            client = TestClient(app, base_url="http://localhost")
            response = client.post(
                "/api/auth/login",
                data={"username": username, "password": password},
            )
            self.assertEqual(response.status_code, 200, response.text)
            return client

        client_one = login_admin(admin_one.username)
        client_two = login_admin(admin_two.username)
        try:
            list_one = client_one.get("/api/admin/mailboxes")
            list_two = client_two.get("/api/admin/mailboxes")
            self.assertEqual([row["email"] for row in list_one.json()], [mailbox_a.email])
            self.assertEqual([row["email"] for row in list_two.json()], [mailbox_b.email])
            self.assertEqual(list_one.json()[0]["assigned_to"], admin_one.username)

            stats_a = client_one.get("/api/stats", params={"mailbox_id": mailbox_a.id})
            stats_b = client_two.get("/api/stats", params={"mailbox_id": mailbox_b.id})
            self.assertEqual(stats_a.status_code, 200, stats_a.text)
            self.assertEqual(stats_b.status_code, 200, stats_b.text)
            self.assertEqual(stats_a.json()["draft"], 2)
            self.assertEqual(stats_a.json()["total"], 0)
            self.assertEqual(stats_b.json()["draft"], 0)
            self.assertEqual(stats_b.json()["total"], 1)

            denied_token = client_one.post(
                f"/api/admin/mailboxes/{mailbox_b.id}/autologin-token"
            )
            self.assertEqual(denied_token.status_code, 403, denied_token.text)
            denied_inbox = client_one.get(
                "/api/emails",
                params={"mailbox_id": mailbox_b.id, "mailbox": mailbox_b.email},
            )
            self.assertEqual(denied_inbox.status_code, 403, denied_inbox.text)
            allowed_token = client_two.post(
                f"/api/admin/mailboxes/{mailbox_b.id}/autologin-token"
            )
            self.assertEqual(allowed_token.status_code, 200, allowed_token.text)

            reassign = self.client.put(
                f"/api/admin/mailboxes/{mailbox_b.id}",
                json={"assigned_to": admin_one.username},
            )
            self.assertEqual(reassign.status_code, 200, reassign.text)
            self.assertEqual(reassign.json()["assigned_to"], admin_one.username)

            list_one_after = client_one.get("/api/admin/mailboxes")
            list_two_after = client_two.get("/api/admin/mailboxes")
            self.assertEqual(
                {row["email"] for row in list_one_after.json()},
                {mailbox_a.email, mailbox_b.email},
            )
            self.assertEqual(list_two_after.json(), [])

            manager_access = self.db.query(AdminMailboxAccess).filter(
                AdminMailboxAccess.mailbox_id == mailbox_b.id,
                AdminMailboxAccess.username.in_([admin_one.username, admin_two.username]),
            ).all()
            self.assertEqual([row.username for row in manager_access], [admin_one.username])

            delete_owner = self.client.delete(f"/api/admin/users/{admin_one.username}/hard")
            self.assertEqual(delete_owner.status_code, 409, delete_owner.text)
        finally:
            client_one.close()
            client_two.close()


if __name__ == "__main__":
    unittest.main()
