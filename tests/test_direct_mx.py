import unittest
from unittest.mock import AsyncMock, patch

from mail_delivery import direct_mx


class FakeDirectSMTP:
    attempts = []
    accepted = []
    failing_hosts = set()

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.__class__.attempts.append(kwargs["hostname"])

    async def __aenter__(self):
        if self.kwargs["hostname"] in self.failing_hosts:
            raise OSError("connection refused")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def sendmail(self, sender, recipients, message):
        self.__class__.accepted.append((sender, recipients, message, self.kwargs))


class DirectMxDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        FakeDirectSMTP.attempts.clear()
        FakeDirectSMTP.accepted.clear()
        FakeDirectSMTP.failing_hosts.clear()

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
