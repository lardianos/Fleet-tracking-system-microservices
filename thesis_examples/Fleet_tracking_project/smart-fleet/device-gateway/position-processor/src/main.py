import json
import os
import logging
from kafka import KafkaConsumer
from redis import Redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    kafka_bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    topic = os.getenv("KAFKA_TOPIC_TELEMETRY", "telemetry.positions")
    group_id = os.getenv("KAFKA_CONSUMER_GROUP", "position-processor-group")

    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))

    redis_client = Redis(
        host=redis_host,
        port=redis_port,
        decode_responses=True
    )

    logger.info("Starting Position Processor...")
    logger.info(f"Consuming topic: {topic}")
    logger.info(f"Redis: {redis_host}:{redis_port}")

    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=kafka_bootstrap_servers,
        group_id=group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        key_deserializer=lambda k: k.decode("utf-8") if k else None,
    )

    for message in consumer:
        imei = message.key
        telemetry = message.value

        redis_key = f"vehicle:latest:{imei}"

        redis_client.set(redis_key, json.dumps(telemetry, ensure_ascii=False))

        logger.info(
            "Saved latest position to Redis: key=%s lat=%s lon=%s speed=%s",
            redis_key,
            telemetry.get("latitude"),
            telemetry.get("longitude"),
            telemetry.get("speed_kmh"),
        )


if __name__ == "__main__":
    main()