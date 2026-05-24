"""
Position Processor Service.

Αυτή η υπηρεσία παίρνει telemetry δεδομένα από τον Kafka
και αποθηκεύει την τελευταία γνωστή θέση κάθε οχήματος στη Redis.

Ροή:
Kafka Topic: telemetry.positions
    ↓
Position Processor
    ↓
Redis key: vehicle:latest:{imei}
"""

import json
import os
import logging
from kafka import KafkaConsumer
from redis import Redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    # -------------------------
    # Kafka Configuration
    # -------------------------

    # Διαβάζουμε τις ρυθμίσεις Kafka από environment variables,
    # ώστε να μπορούμε να τις αλλάζουμε από το docker-compose.yml.
    kafka_bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    topic = os.getenv("KAFKA_TOPIC_TELEMETRY", "telemetry.positions")
    group_id = os.getenv("KAFKA_CONSUMER_GROUP", "position-processor-group")

    # -------------------------
    # Redis Configuration
    # -------------------------

    # Η Redis χρησιμοποιείται για γρήγορη αποθήκευση της τελευταίας θέσης
    # κάθε οχήματος, ώστε αργότερα να μπορεί να τη διαβάζει το WebSocket Gateway.
    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))

    redis_client = Redis(
        host=redis_host,
        port=redis_port,
        decode_responses=True,
    )

    logger.info("Starting Position Processor...")
    logger.info("Consuming topic: %s", topic)
    logger.info("Redis: %s:%s", redis_host, redis_port)

    # -------------------------
    # Kafka Consumer
    # -------------------------

    # Δημιουργούμε Kafka consumer που ακούει το topic telemetry.positions.
    # Το auto_offset_reset="earliest" σημαίνει ότι αν το consumer group είναι καινούργιο,
    # θα ξεκινήσει να διαβάζει από τα παλιότερα διαθέσιμα μηνύματα.
    consumer = KafkaConsumer(
        topic,
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

    # Για κάθε μήνυμα που έρχεται από το Kafka:
    # 1. παίρνουμε το IMEI από το Kafka key
    # 2. παίρνουμε το telemetry payload από το Kafka value
    # 3. αποθηκεύουμε το τελευταίο στίγμα στη Redis
    for message in consumer:
        imei = message.key
        telemetry = message.value

        # Δημιουργούμε μοναδικό Redis key για κάθε συσκευή/όχημα.
        # Παράδειγμα: vehicle:latest:123456789012345
        redis_key = f"vehicle:latest:{imei}"

        # Αποθηκεύουμε όλο το telemetry object ως JSON string.
        # Έτσι κρατάμε latitude, longitude, speed, timestamp κτλ.
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