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
            value_serializer=lambda value: json.dumps( value, ensure_ascii=False,).encode("utf-8"),
            key_serializer=lambda key: key.encode("utf-8"),
            acks="all",
            retries=3,
            max_in_flight_requests_per_connection=1,
        )

        logger.info(
            "Position Event Producer connected to Kafka"
        )

    def publish_position(self, telemetry: dict):
        # Το IMEI κρατά τις εγγραφές της ίδιας συσκευής στο ίδιο partition.
        future = self.producer.send(
            self.topic,
            key=telemetry["imei"],
            value=telemetry,
        )

        # Δεν επιστρέφουμε επιτυχία πριν επιβεβαιώσει ο Kafka broker.
        metadata = future.get(timeout=10)

        logger.info(
            "Published processed position: imei=%s partition=%s offset=%s",
            telemetry["imei"],
            metadata.partition,
            metadata.offset,
        )

    def close(self):
        # Περιμένουμε την αποστολή των εκκρεμών μηνυμάτων και κλείνουμε τον producer.
        self.producer.close()