"""
Repository υπεύθυνο για την αποθήκευση
και ανάκτηση της τελευταίας θέσης οχήματος.

Η Redis χρησιμοποιείται ως cache και όχι
ως μόνιμη βάση δεδομένων.
"""

import json
import logging
import os

import redis

logger = logging.getLogger(__name__)


class RedisRepository:

    def __init__(self):

        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            decode_responses=True,
        )

        logger.info(
            "Connected to Redis at %s:%s",
            os.getenv("REDIS_HOST", "redis"),
            os.getenv("REDIS_PORT", "6379"),
        )

    def save_latest_position(self, telemetry: dict):

        imei = telemetry["imei"]

        redis_key = f"vehicle:latest:{imei}"

        self.redis_client.set(
            redis_key,
            json.dumps(
                telemetry,
                ensure_ascii=False,
            ),
        )

        logger.info(
            "Saved latest position for imei=%s",
            imei,
        )

    def get_latest_position(self, imei: str):

        redis_key = f"vehicle:latest:{imei}"

        data = self.redis_client.get(redis_key)

        if not data:
            return None

        return json.loads(data)