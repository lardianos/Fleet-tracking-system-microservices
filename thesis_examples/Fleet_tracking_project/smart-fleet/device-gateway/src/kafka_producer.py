"""
Kafka Producer για το Device Gateway.

Αυτό το αρχείο είναι υπεύθυνο για την αποστολή των parsed AVL records
στο Kafka topic telemetry.positions.

Ροή:
Device Gateway
    ↓
Kafka Producer
    ↓
Kafka Topic: telemetry.positions
"""

import json
import logging
import os
from kafka import KafkaProducer

logger = logging.getLogger(__name__)


class TelemetryProducer:
    def __init__(self):
        # Διαβάζουμε τις ρυθμίσεις από environment variables,
        # ώστε το service να μπορεί να τρέχει εύκολα μέσα σε Docker.
        bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
        self.topic = os.getenv("KAFKA_TOPIC_TELEMETRY", "telemetry.positions")

        # Δημιουργούμε Kafka producer.
        # Το value_serializer μετατρέπει το Python dict σε JSON bytes.
        # Το key_serializer μετατρέπει το IMEI σε bytes ώστε να χρησιμοποιηθεί ως Kafka key.
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
            key_serializer=lambda v: v.encode("utf-8") if v else None,
        )

        logger.info(
            "Kafka producer connected to %s, topic=%s",
            bootstrap_servers,
            self.topic,
        )

    def publish_record(self, record: dict, key: str | None = None):
        # Στέλνουμε ένα telemetry record στο Kafka.
        # Ως key χρησιμοποιούμε συνήθως το IMEI, ώστε τα δεδομένα της ίδιας συσκευής
        # να μπορούν να πάνε στο ίδιο partition.
        future = self.producer.send(self.topic, key=key, value=record)

        # Περιμένουμε επιβεβαίωση από τον Kafka ότι το μήνυμα γράφτηκε επιτυχώς.
        metadata = future.get(timeout=10)

        logger.info(
            "Published to Kafka topic=%s, partition=%s, offset=%s",
            metadata.topic,
            metadata.partition,
            metadata.offset,
        )

    def flush(self):
        # Αναγκάζουμε τον producer να στείλει όσα μηνύματα έχουν μείνει buffered
        # πριν κλείσει το service.
        self.producer.flush()