"""
Locust load testing for LTI Anti-Phishing classifier API.
Usage: locust -f tests/locustfile.py --host=http://localhost:8001 --headless -u 50 -r 10
"""

from locust import HttpUser, task, between
import random

PHISHING_EMAILS = [
    {
        "subject": "URGENT: Your account has been compromised!!!",
        "body": "Dear valued customer, your account requires immediate verification. "
                "Click here to secure your account: http://bit.ly/3xK9mN2 "
                "Failure to verify within 24 hours will result in account suspension.",
        "sender": "security@bank-login-security.com",
    },
    {
        "subject": "RE: Invoice #INV-2024-08912 -- Payment Overdue",
        "body": "Please find attached the updated invoice for your reference. "
                "This payment is now overdue by 14 days. "
                "Download attachment: http://tinyurl.com/invoice-payment",
        "sender": "accounts@billing-update.net",
    },
]

LEGIT_EMAILS = [
    {
        "subject": "Meeting: Project Update Tomorrow",
        "body": "Hi team, just a reminder about our project update meeting tomorrow at 10am. "
                "Please prepare your weekly reports. Best regards, Manager.",
        "sender": "manager@company.com",
    },
    {
        "subject": "Your Invoice Attached",
        "body": "Dear customer, thank you for your purchase. "
                "Please find your invoice attached to this email. "
                "Regards, Support Team",
        "sender": "support@legitimate-store.com",
    },
]


class PipelineUser(HttpUser):
    wait_time = between(0.5, 3)

    @task(3)
    def predict_phishing(self):
        email = random.choice(PHISHING_EMAILS)
        raw = (
            f"From: {email['sender']}\r\n"
            f"Subject: {email['subject']}\r\n"
            f"\r\n{email['body']}"
        )
        self.client.post("/predict", json={"raw_email": raw, "email_id": f"load-test-{random.randint(1,10000)}"})

    @task(2)
    def predict_legit(self):
        email = random.choice(LEGIT_EMAILS)
        raw = (
            f"From: {email['sender']}\r\n"
            f"Subject: {email['subject']}\r\n"
            f"\r\n{email['body']}"
        )
        self.client.post("/predict", json={"raw_email": raw, "email_id": f"load-test-legit-{random.randint(1,10000)}"})

    @task(1)
    def health_check(self):
        self.client.get("/health")
