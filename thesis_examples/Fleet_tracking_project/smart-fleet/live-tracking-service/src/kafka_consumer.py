"""
Consumer του processed.positions topic.

Παραλαμβάνει processed telemetry events
και ενημερώνει τη Redis cache.
"""

import json
import logging
import os

from kafka import KafkaConsumer

logger = logging.getLogger(__name__)


def create_consumer():

    topic = os.getenv("KAFKA_TOPIC_PROCESSED_POSITIONS", "processed.positions",)

    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=os.getenv( "KAFKA_BOOTSTRAP_SERVERS",            "kafka:9092",
        ),
        group_id="live-tracking-group",
            auto_offset_reset="latest",
            enable_auto_commit=True,
            value_deserializer=lambda value: json.loads(  value.decode("utf-8")
        ),
    )

    logger.info(
        "Consuming topic: %s",
        topic,
    )

    return consumer