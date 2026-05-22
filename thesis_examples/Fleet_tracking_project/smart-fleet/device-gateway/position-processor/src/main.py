import json
import os
import logging
from kafka import KafkaConsumer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    topic = os.getenv("KAFKA_TOPIC_TELEMETRY", "telemetry.positions")
    group_id = os.getenv("KAFKA_CONSUMER_GROUP", "position-processor-group")

    logger.info("Starting Position Processor...")
    logger.info(f"Kafka bootstrap servers: {bootstrap_servers}")
    logger.info(f"Consuming topic: {topic}")
    logger.info(f"Consumer group: {group_id}")

    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        key_deserializer=lambda k: k.decode("utf-8") if k else None,
    )

    for message in consumer:
        imei = message.key
        telemetry = message.value

        logger.info(
            "Received telemetry: imei=%s lat=%s lon=%s speed=%s timestamp_ms=%s",
            imei,
            telemetry.get("latitude"),
            telemetry.get("longitude"),
            telemetry.get("speed_kmh"),
            telemetry.get("timestamp_ms"),
        )


if __name__ == "__main__":
    main()