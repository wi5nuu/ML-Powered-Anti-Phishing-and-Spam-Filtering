"""
Multi-channel alerting for CogniMail.
Supports Slack, Telegram, and Email alerts with severity levels.
"""

import asyncio
import logging
import os
import aiohttp
import aiosmtplib
from email.mime.text import MIMEText
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SMTP_HOST = os.getenv("ALERT_SMTP_HOST", "")
SMTP_PORT = int(os.getenv("ALERT_SMTP_PORT", "587"))
SMTP_USER = os.getenv("ALERT_SMTP_USER", "")
SMTP_PASSWORD = os.getenv("ALERT_SMTP_PASSWORD", "")
# ALERT_RECIPIENT: address that receives email alerts. Defaults to SMTP_USER
# so existing deployments keep working, but can be set independently.
ALERT_RECIPIENT = os.getenv("ALERT_RECIPIENT", "") or SMTP_USER
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://dashboard:8080")


@dataclass
class AlertPayload:
    email_id: str
    subject: str
    sender: str
    fused_score: float
    ml_probability: float
    anomaly_score: float
    label: str
    xai_summary: str
    severity: str  # CRITICAL, HIGH, MEDIUM


class AlertManager:
    def __init__(self):
        self.session: aiohttp.ClientSession = None

    async def ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def send_slack(self, payload: AlertPayload):
        if not SLACK_WEBHOOK_URL:
            return
        await self.ensure_session()
        emoji = {"CRITICAL": ":red_circle:", "HIGH": ":warning:", "MEDIUM": ":large_blue_circle:"}
        text = (
            f"{emoji.get(payload.severity, ':warning:')} *[{payload.severity}] Phishing Alert*\n"
            f"*Subject:* {payload.subject}\n"
            f"*Sender:* {payload.sender}\n"
            f"*Fused Score:* {payload.fused_score:.3f}\n"
            f"*ML Prob:* {payload.ml_probability:.4f}\n"
            f"*Anomaly:* {payload.anomaly_score:.4f}\n"
            f"*XAI:* {payload.xai_summary}\n"
            f"<{DASHBOARD_URL}/email/{payload.email_id}|View in Dashboard>"
        )
        try:
            await self.session.post(SLACK_WEBHOOK_URL, json={"text": text}, timeout=aiohttp.ClientTimeout(total=10))
            logger.info("Slack alert sent for %s", payload.email_id)
        except Exception as e:
            logger.warning("Slack alert failed: %s", e)

    async def send_telegram(self, payload: AlertPayload):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            return
        await self.ensure_session()
        emoji = {"CRITICAL": "\u26a0\ufe0f", "HIGH": "\u2757", "MEDIUM": "\ud83d\udd35"}
        severity_icon = emoji.get(payload.severity, "\u2757")
        text = (
            f"{severity_icon} *[{payload.severity}] Phishing Alert*\n"
            f"Subject: {payload.subject}\n"
            f"Sender: {payload.sender}\n"
            f"Score: {payload.fused_score:.3f} | ML: {payload.ml_probability:.4f} | Anom: {payload.anomaly_score:.4f}\n"
            f"/email_{payload.email_id}"
        )
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        try:
            await self.session.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown",
            }, timeout=aiohttp.ClientTimeout(total=10))
            logger.info("Telegram alert sent for %s", payload.email_id)
        except Exception as e:
            logger.warning("Telegram alert failed: %s", e)

    async def send_email(self, payload: AlertPayload):
        if not SMTP_HOST or not SMTP_USER:
            return
        body = (
            f"CogniMail Alert — {payload.severity}\n\n"
            f"Email ID: {payload.email_id}\n"
            f"Subject: {payload.subject}\n"
            f"Sender: {payload.sender}\n"
            f"Label: {payload.label}\n"
            f"Fused Score: {payload.fused_score:.3f}\n"
            f"ML Probability: {payload.ml_probability:.4f}\n"
            f"Anomaly Score: {payload.anomaly_score:.4f}\n"
            f"XAI: {payload.xai_summary}\n\n"
            f"Dashboard: {DASHBOARD_URL}/email/{payload.email_id}"
        )
        msg = MIMEText(body)
        msg["Subject"] = f"[{payload.severity}] CogniMail Alert — {payload.subject[:40]}"
        msg["From"] = SMTP_USER
        msg["To"] = ALERT_RECIPIENT
        try:
            await aiosmtplib.send(
                msg,
                hostname=SMTP_HOST,
                port=SMTP_PORT,
                username=SMTP_USER,
                password=SMTP_PASSWORD,
                start_tls=True,
            )
            logger.info("Email alert sent for %s", payload.email_id)
        except Exception as e:
            logger.warning("Email alert failed: %s", e)

    async def send_all(self, payload: AlertPayload):
        await asyncio.gather(
            self.send_slack(payload),
            self.send_telegram(payload),
            self.send_email(payload),
            return_exceptions=True,
        )

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()


alert_manager = AlertManager()
