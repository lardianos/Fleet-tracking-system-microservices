
"""
Καταναλώνουμε telemetry και fleet events από το Kafka.
Συσχετίζουμε τις θέσεις με τα οχήματα, αποθηκεύουμε το ιστορικό
στο TimescaleDB και δημοσιεύουμε τις επεξεργασμένες θέσεις.
"""

import json
import os
import logging
import psycopg2

from kafka import KafkaConsumer
from redis import Redis
from kafka_producer import PositionEventProducer
from kafka.errors import NoBrokersAvailable

from db_repository import PositionRepository
from threading import Event
from contextlib import ExitStack

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def connect_position_dependencies(stop_event: Event):
    kafka_bootstrap_servers = os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS",
        "kafka:9092",
    )

    topic = os.getenv(
        "KAFKA_TOPIC_TELEMETRY",
        "telemetry.positions",
    )

    fleet_topic = os.getenv(
        "KAFKA_TOPIC_FLEET_VEHICLES",
        "fleet.vehicles",
    )

    group_id = os.getenv(
        "KAFKA_CONSUMER_GROUP",
        "position-processor-group",
    )

    while not stop_event.is_set():
        try:
            # Αν αποτύχει κάποιο επόμενο βήμα, κλείνουμε όσα έχουν ήδη ανοίξει.
            with ExitStack() as connections:
                position_repository = PositionRepository()
                connections.callback(position_repository.close)

                position_event_producer = PositionEventProducer()
                connections.callback(position_event_producer.close)

                consumer = KafkaConsumer(
                    topic,
                    fleet_topic,
                    bootstrap_servers=kafka_bootstrap_servers,
                    group_id=group_id,
                    auto_offset_reset="earliest",
                    enable_auto_commit=True,
                    value_deserializer=lambda value: json.loads(value.decode("utf-8")),
                    key_deserializer=lambda key: key.decode("utf-8") if key else None,
                )

                connections.callback(consumer.close)

                if stop_event.is_set():
                    return None

                # Οι συνδέσεις δημιουργήθηκαν επιτυχώς.
                # Από εδώ και πέρα τις κλείνει το υπάρχον finally της consume_positions.
                connections.pop_all()

                logger.info(
                    "Position dependencies connected. Starting consumption."
                )

                return (
                    consumer,
                    position_repository,
                    position_event_producer,
                    fleet_topic,
                )

        except (NoBrokersAvailable, psycopg2.OperationalError) as error:
            logger.warning(
                "Position dependencies unavailable: %s; retrying in 5 seconds",
                error,
            )

            # Διακόπτουμε την αναμονή αμέσως αν ζητηθεί τερματισμός.
            if stop_event.wait(5):
                return None

    return None

def consume_positions(stop_event: Event):
    connections = connect_position_dependencies(stop_event)

    if connections is None:
        return

    consumer, position_repository, position_event_producer, fleet_topic = connections
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
                        if event.get("event_type") in ("vehicle.created", "vehicle.mapping.updated"):
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