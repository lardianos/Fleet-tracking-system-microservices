"""
Position Processor Service.

Αυτή η υπηρεσία καταναλώνει telemetry δεδομένα από το Kafka,
αποθηκεύει την τελευταία γνωστή θέση κάθε οχήματος στη Redis
και αποθηκεύει το ιστορικό θέσεων στην TimescaleDB.

Ροή:
Kafka Topic: telemetry.positions
    ↓
Position Processor
    ├── Redis key: vehicle:latest:{imei}
    └── TimescaleDB table: vehicle_positions
"""

import json
import os
import logging
from kafka import KafkaConsumer
from redis import Redis

from db_repository import PositionRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # -------------------------
    # Kafka Configuration
    # -------------------------
    kafka_bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    topic = os.getenv("KAFKA_TOPIC_TELEMETRY", "telemetry.positions")
    group_id = os.getenv("KAFKA_CONSUMER_GROUP", "position-processor-group")

    # -------------------------
    # Redis Configuration
    # -------------------------
    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))

    redis_client = Redis(
        host=redis_host,
        port=redis_port,
        decode_responses=True,
    )

    # -------------------------
    # TimescaleDB Repository
    # -------------------------
    position_repository = PositionRepository()

    logger.info("Starting Position Processor...")
    logger.info("Consuming topic: %s", topic)
    logger.info("Redis: %s:%s", redis_host, redis_port)

    # -------------------------
    # Kafka Consumer
    # -------------------------
    fleet_topic = os.getenv("KAFKA_TOPIC_FLEET_VEHICLES", "fleet.vehicles")

    consumer = KafkaConsumer(
        topic,
        fleet_topic,
        bootstrap_servers=kafka_bootstrap_servers,
        group_id=group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        key_deserializer=lambda k: k.decode("utf-8") if k else None,
    )

    # -------------------------
    # Main Processing Loop
    # -------------------------
    for message in consumer:
        if message.topic == fleet_topic:
            event = message.value

            # Επεξεργαζόμαστε μόνο vehicle.created events.
            # Αυτά τα events έρχονται από το Fleet API όταν δημιουργείται νέο όχημα.
            if event.get("event_type") == "vehicle.created":
                position_repository.save_imei_vehicle_mapping(
                    device_imei=event["device_imei"],
                    vehicle_id=event["vehicle_id"],
                )

            continue
        imei = message.key
        telemetry = message.value

        # Αν για κάποιο λόγο το Kafka key λείπει, χρησιμοποιούμε το imei από το payload.
        # Αυτό προστατεύει το service από μη πλήρη Kafka messages.
        if not telemetry.get("imei"):
            telemetry["imei"] = imei

        redis_key = f"vehicle:latest:{imei}"

        # Αποθηκεύουμε την τελευταία γνωστή θέση στη Redis για live χρήση.
        redis_client.set(redis_key, json.dumps(telemetry, ensure_ascii=False))

        # Αποθηκεύουμε το ίδιο telemetry record στην TimescaleDB για ιστορικό.
        position_repository.save_position(telemetry)

        logger.info(
            "Processed telemetry: imei=%s lat=%s lon=%s speed=%s",
            imei,
            telemetry.get("latitude"),
            telemetry.get("longitude"),
            telemetry.get("speed_kmh"),
        )


if __name__ == "__main__":
    main()