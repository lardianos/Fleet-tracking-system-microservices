import json
import logging
import os
from kafka import KafkaProducer

logger = logging.getLogger(__name__)


class TelemetryProducer:
    def __init__(self):
        bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
        self.topic = os.getenv("KAFKA_TOPIC_TELEMETRY", "telemetry.positions")

        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
            key_serializer=lambda v: v.encode("utf-8") if v else None,
        )

        logger.info(f"Kafka producer connected to {bootstrap_servers}, topic={self.topic}")

    def publish_record(self, record: dict, key: str | None = None):
        future = self.producer.send(self.topic, key=key, value=record)
        metadata = future.get(timeout=10)
        logger.info(
            f"Published to Kafka topic={metadata.topic}, partition={metadata.partition}, offset={metadata.offset}"
        )

    def flush(self):
        self.producer.flush()