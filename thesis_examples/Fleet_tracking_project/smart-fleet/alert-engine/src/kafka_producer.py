import json
import logging
import os

from kafka import KafkaProducer

logger = logging.getLogger(__name__)


class AlertEventProducer:
    def __init__(self):
        self.topic = os.getenv("KAFKA_TOPIC_ALERTS", "fleet.alerts")

        self.producer = KafkaProducer(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
            key_serializer=lambda key: key.encode("utf-8"),
            value_serializer=lambda value: json.dumps(
                value,
                ensure_ascii=False,
            ).encode("utf-8"),
            acks="all",
            retries=3,
            max_in_flight_requests_per_connection=1,
        )

    def publish_alert(self, alert: dict):
        future = self.producer.send(
            self.topic,
            key=alert["imei"],
            value=alert,
        )

        # Περιμένουμε επιβεβαίωση από τον broker πριν συνεχίσουμε.
        metadata = future.get(timeout=10)

        logger.info(
            "Published alert: rule=%s vehicle_id=%s imei=%s alert_id=%s partition=%s offset=%s",
            alert["rule_id"],
            alert["vehicle_id"],
            alert["imei"],
            alert["alert_id"],
            metadata.partition,
            metadata.offset,
        )

    def close(self):
        self.producer.close(timeout=10)