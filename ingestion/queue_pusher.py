"""
Redis queue producer — push email yang sudah diparse ke Redis queue.

Queue name dikonfigurasi via env REDIS_QUEUE_NAME (default: email_pipeline).
"""

import json
import logging
import os
from typing import Optional

import redis.asyncio as aio_redis

logger = logging.getLogger(__name__)

REDIS_URL     = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE_NAME    = os.getenv("REDIS_QUEUE_NAME", "email_pipeline")


class QueuePusher:
    def __init__(self):
        self._redis: Optional[aio_redis.Redis] = None

    async def connect(self):
        self._redis = aio_redis.from_url(REDIS_URL)
        await self._redis.ping()
        logger.info("Connected to Redis at %s", REDIS_URL)

    async def push_email(self, email_data: dict) -> bool:
        if self._redis is None:
            await self.connect()

        try:
            payload = json.dumps(email_data, default=str)
            await self._redis.rpush(QUEUE_NAME, payload)
            logger.debug("Pushed email %s to queue %s",
                         email_data.get("email_id", "unknown"), QUEUE_NAME)
            return True
        except Exception as e:
            logger.error("Failed to push to Redis queue: %s", e)
            return False

    async def push_batch(self, emails: list[dict]) -> int:
        success = 0
        for email_data in emails:
            if await self.push_email(email_data):
                success += 1
        return success
