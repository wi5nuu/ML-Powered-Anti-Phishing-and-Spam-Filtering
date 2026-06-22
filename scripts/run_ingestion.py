"""
CLI runner untuk ingestion pipeline:
  Poll Mailpit API -> Parse email -> Push ke Redis queue.
"""

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.fetcher import EmailFetcher
from ingestion.queue_pusher import QueuePusher

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper()),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingestion_runner")

POLL_INTERVAL = int(os.getenv("IMAP_POLL_INTERVAL", "30"))


async def main():
    fetcher = EmailFetcher()
    pusher = QueuePusher()
    await fetcher.connect()
    await pusher.connect()
    logger.info("Ingestion runner started, polling every %ds", POLL_INTERVAL)

    while True:
        try:
            emails = await fetcher.fetch_new_emails()
            if emails:
                pushed = await pusher.push_batch(emails)
                logger.info("Fetched %d new emails, pushed %d to queue", len(emails), pushed)
            else:
                logger.debug("No new emails")
        except Exception as e:
            logger.error("Ingestion cycle error: %s", e)

        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
