
"""
Καταναλώνουμε telemetry και fleet events από το Kafka.
Συσχετίζουμε τις θέσεις με τα οχήματα, αποθηκεύουμε το ιστορικό
στο TimescaleDB και δημοσιεύουμε τις επεξεργασμένες θέσεις.
"""

import json
import os
import logging
from kafka import KafkaConsumer
from redis import Redis
from kafka_producer import PositionEventProducer
from db_repository import PositionRepository
from threading import Event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def consume_positions(stop_event: Event):
    # -------------------------
    # Kafka Configuration
    # -------------------------
    kafka_bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    topic = os.getenv("KAFKA_TOPIC_TELEMETRY", "telemetry.positions")
    group_id = os.getenv("KAFKA_CONSUMER_GROUP", "position-processor-group")

    # # -------------------------
    # # Redis Configuration
    # # -------------------------
    # redis_host = os.getenv("REDIS_HOST", "redis")
    # redis_port = int(os.getenv("REDIS_PORT", "6379"))
    #
    # redis_client = Redis(
    #     host=redis_host,
    #     port=redis_port,
    #     decode_responses=True,
    # )

    # -------------------------
    # TimescaleDB Repository
    # -------------------------
    position_repository = PositionRepository()

    position_event_producer = PositionEventProducer()

    logger.info("Starting Position Processor...")
    logger.info("Consuming topic: %s", topic)
    # logger.info("Redis: %s:%s", redis_host, redis_port)

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
    try:
        while not stop_event.is_set():
            # Περιμένουμε έως ένα δευτερόλεπτο για νέα μηνύματα.
            # Έτσι ελέγχουμε το σήμα τερματισμού ακόμη και χωρίς telemetry.
            message_batches = consumer.poll(timeout_ms=1000, max_records=100)

            for messages in message_batches.values():
                for message in messages:
                    if message.topic == fleet_topic:
                        event = message.value

                        # Ενημερώνουμε την αντιστοίχιση IMEI και οχήματος.
                        if event.get("event_type") == "vehicle.created":
                            position_repository.save_imei_vehicle_mapping(
                                device_imei=event["device_imei"],
                                vehicle_id=event["vehicle_id"],
                            )

                        continue

                    imei = message.key
                    telemetry = message.value

                    # Χρησιμοποιούμε το Kafka key αν λείπει το IMEI από το payload.
                    if not telemetry.get("imei"):
                        telemetry["imei"] = imei

                    vehicle_id = position_repository.find_vehicle_id_by_imei(telemetry["imei"])
                    telemetry["vehicle_id"] = vehicle_id

                    # Αποθηκεύουμε τη θέση πριν τη δημοσιεύσουμε στα υπόλοιπα services.
                    position_repository.save_position(telemetry)
                    position_event_producer.publish_position(telemetry)

                    logger.info(
                        "Processed telemetry: imei=%s lat=%s lon=%s speed=%s vehicle_id=%s",
                        imei,
                        telemetry.get("latitude"),
                        telemetry.get("longitude"),
                        telemetry.get("speed_kmh"),
                        telemetry.get("vehicle_id"),
                    )

            # Ολοκληρώνουμε την επεξεργασία των μηνυμάτων που παραλάβαμε
            # πριν ελέγξουμε ξανά αν ζητήθηκε τερματισμός.
    finally:
        # Κλείνουμε κάθε σύνδεση ακόμη και αν αποτύχει το προηγούμενο κλείσιμο.
        try:
            consumer.close()
        finally:
            try:
                position_event_producer.close()
            finally:
                position_repository.close()

        logger.info("Position consumption stopped.")