"""
Async Kafka consumer για το Live Tracking Service.

Η ευθύνη αυτού του αρχείου είναι να δημιουργεί Kafka consumer
για το topic processed.positions.
"""

import json
import logging
import os

from aiokafka import AIOKafkaConsumer

logger = logging.getLogger(__name__)


async def create_consumer():
    # Διαβάζουμε το Kafka topic από environment variable.
    # Αν δεν υπάρχει, χρησιμοποιούμε το default processed.positions.
    topic = os.getenv( "KAFKA_TOPIC_PROCESSED_POSITIONS", "processed.positions", )

    # Δημιουργούμε async Kafka consumer.
    # Το aiokafka ταιριάζει καλύτερα με FastAPI γιατί δουλεύει με asyncio.
    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=os.getenv( "KAFKA_BOOTSTRAP_SERVERS", "kafka:9092", ),
        group_id="live-tracking-group",
        auto_offset_reset="latest",
        value_deserializer=lambda value: json.loads( value.decode("utf-8") ),
    )

    # Ξεκινάμε τον consumer ασύγχρονα.
    await consumer.start()

    logger.info("Consuming Kafka topic: %s", topic)

    return consumer