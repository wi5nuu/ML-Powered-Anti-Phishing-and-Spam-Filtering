"""
Email fetcher — mengambil email dari Mailpit via REST API dan push ke Redis queue.
Mailpit tidak mendukung IMAP, jadi kita pakai API HTTP-nya.
"""

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

MAILPIT_API_URL = os.getenv("MAILPIT_API_URL", "http://localhost:8025/api/v1")
POLL_INTERVAL = int(os.getenv("IMAP_POLL_INTERVAL", "30"))


class EmailFetcher:
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self.seen_ids: set = set()

    async def connect(self):
        self.client = httpx.AsyncClient(base_url=MAILPIT_API_URL)
        logger.info("Connected to Mailpit API at %s", MAILPIT_API_URL)

    async def fetch_new_emails(self) -> list[dict]:
        if self.client is None:
            await self.connect()

        try:
            resp = await self.client.get("/messages")
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error("mailpit_api_error", error=str(e))
            return []

        result = []
        for msg in data.get("messages", []):
            msg_id = msg.get("ID", "")
            if msg_id in self.seen_ids:
                continue

            raw_resp = await self.client.get(f"/message/{msg_id}/raw")
            if raw_resp.status_code != 200:
                continue

            raw_email = raw_resp.text
            email_id = hashlib.sha256(raw_email.encode()).hexdigest()[:16]
            self.seen_ids.add(msg_id)

            result.append({
                "email_id": email_id,
                "raw_email": raw_email,
                "received_at": datetime.now(timezone.utc).isoformat(),
                "raw_hash": email_id,
            })

        return result

    async def run_once(self) -> list[dict]:
        return await self.fetch_new_emails()
