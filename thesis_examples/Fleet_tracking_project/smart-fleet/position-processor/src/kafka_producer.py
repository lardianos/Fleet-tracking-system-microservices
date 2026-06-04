"""
Kafka Producer για processed telemetry events.

Ο Position Processor δημοσιεύει τα καθαρισμένα και εμπλουτισμένα
δεδομένα θέσης ώστε να μπορούν να τα καταναλώσουν άλλα services
(WebSocket Gateway, Alert Engine, Trips Service κτλ).
"""

import json
import logging
import os

from kafka import KafkaProducer

logger = logging.getLogger(__name__)


class PositionEventProducer:

    def __init__(self):

        bootstrap_servers = os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS",
            "kafka:9092",
        )

        self.topic = os.getenv(
            "KAFKA_TOPIC_PROCESSED_POSITIONS",
            "processed.positions",
        )

        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda value: json.dumps(
                value,
                ensure_ascii=False,
            ).encode("utf-8"),
        )

        logger.info(
            "Position Event Producer connected to Kafka"
        )

    def publish_position(self, telemetry: dict):

        self.producer.send(
            self.topic,
            value=telemetry,
        )

        logger.info(
            "Published processed position: imei=%s",
            telemetry.get("imei"),
        )