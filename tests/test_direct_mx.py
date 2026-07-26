import unittest
from unittest.mock import AsyncMock, patch

from mail_delivery import direct_mx


class FakeDirectSMTP:
    """
    Async SMTP stub for unit tests.

    State is stored as instance-level lists/sets so tests never share
    mutable data across test-method boundaries.  The asyncSetUp helper
    resets them explicitly, but instance isolation prevents accidental
    cross-contamination when tests run concurrently.
    """

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        # Instance-level state — not class-level, to avoid cross-test pollution
        self.__class__._instances.append(self)

    # Registry used only so asyncSetUp can find & reset all instances
    _instances: list = []
    # These are reset in asyncSetUp; kept as class attrs for the patch to work
    attempts: list = []
    accepted: list = []
    failing_hosts: set = set()

    async def __aenter__(self):
        self.__class__.attempts.append(self.kwargs["hostname"])
        if self.kwargs["hostname"] in self.failing_hosts:
            raise OSError("connection refused")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def sendmail(self, sender, recipients, message):
        self.__class__.accepted.append((sender, recipients, message, self.kwargs))


class DirectMxDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Reset all mutable class-level state before every test
        FakeDirectSMTP.attempts = []
        FakeDirectSMTP.accepted = []
        FakeDirectSMTP.failing_hosts = set()
        FakeDirectSMTP._instances = []

    async def test_uses_next_mx_when_preferred_host_fails(self):
        FakeDirectSMTP.failing_hosts.add("mx1.example.net")
        resolve = AsyncMock(return_value=["mx1.example.net", "mx2.example.net"])
        with (
            patch.object(direct_mx, "_resolve_mx", resolve),
            patch.object(direct_mx.aiosmtplib, "SMTP", FakeDirectSMTP),
        ):
            delivered = await direct_mx.deliver_direct_mx(
                "From: bantuan@zenime.my.id\r\nTo: user@example.net\r\n\r\nHello",
                "cognimail@zenime.my.id",
                ["user@example.net"],
                helo_hostname="cognimail.zenime.my.id",
            )

        self.assertEqual(delivered, {"example.net": "mx2.example.net"})
        self.assertEqual(FakeDirectSMTP.attempts, ["mx1.example.net", "mx2.example.net"])
        accepted = FakeDirectSMTP.accepted[0]
        self.assertEqual(accepted[0], "cognimail@zenime.my.id")
        self.assertEqual(accepted[1], ["user@example.net"])
        self.assertEqual(accepted[3]["local_hostname"], "cognimail.zenime.my.id")

    async def test_reports_domain_when_all_mx_hosts_fail(self):
        FakeDirectSMTP.failing_hosts.update({"mx1.example.net", "mx2.example.net"})
        with (
            patch.object(
                direct_mx,
                "_resolve_mx",
                AsyncMock(return_value=["mx1.example.net", "mx2.example.net"]),
            ),
            patch.object(direct_mx.aiosmtplib, "SMTP", FakeDirectSMTP),
        ):
            with self.assertRaises(direct_mx.DirectDeliveryError) as raised:
                await direct_mx.deliver_direct_mx(
                    "Subject: test\r\n\r\nHello",
                    "cognimail@zenime.my.id",
                    ["user@example.net"],
                )

        self.assertIn("example.net", raised.exception.failures)


if __name__ == "__main__":
    unittest.main()
