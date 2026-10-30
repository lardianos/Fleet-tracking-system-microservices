
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
from kafka.errors import NoBrokersAvailable, KafkaError
from kafka.structs import OffsetAndMetadata, TopicPartition

from db_repository import PositionRepository
from threading import Event
from contextlib import ExitStack

from obd_decoder import decode_fmc003_obd

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
                    enable_auto_commit=False,
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
    while not stop_event.is_set():
        connections = connect_position_dependencies(stop_event)

        if connections is None:
            return

        consumer, position_repository, position_event_producer, fleet_topic = connections

        try:
            while not stop_event.is_set():
                message_batches = consumer.poll(timeout_ms=1000, max_records=100)

                for messages in message_batches.values():
                    for message in messages:
                        if stop_event.is_set():
                            return

                        if message.topic == fleet_topic:
                            event = message.value

                            if event.get("event_type") in ("vehicle.created", "vehicle.mapping.updated"):
                                # Το fleet event ολοκληρώνεται όταν αποθηκευτεί η αντιστοίχιση.
                                position_repository.save_imei_vehicle_mapping(
                                    device_imei=event["device_imei"],
                                    vehicle_id=event["vehicle_id"],
                                    device_model=event.get("device_model", "GPS"),
                                )

                        else:
                            telemetry = message.value

                            if not telemetry.get("imei"):
                                telemetry["imei"] = message.key

                            device_mapping = position_repository.find_device_mapping_by_imei(
                                telemetry["imei"]
                            )

                            telemetry["vehicle_id"] = None
                            telemetry["device_model"] = None
                            telemetry["obd"] = None

                            if device_mapping is not None:
                                telemetry["vehicle_id"] = device_mapping["vehicle_id"]
                                telemetry["device_model"] = device_mapping["device_model"]

                                if device_mapping["device_model"] == "FMC003":
                                    io_elements = telemetry.get("io_elements")

                                    if isinstance(io_elements, dict):
                                        telemetry["obd"] = decode_fmc003_obd(io_elements)

                            # Πρώτα ολοκληρώνεται η αποθήκευση της ιστορικής εγγραφής.
                            position_repository.save_position(telemetry)

                            # Μετά περιμένουμε επιβεβαίωση δημοσίευσης στο Kafka.
                            position_event_producer.publish_position(telemetry)

                            if telemetry["obd"] is not None:
                                logger.info(
                                    "Decoded OBD: imei=%s data=%s",
                                    telemetry["imei"],
                                    telemetry["obd"],
                                )

                            logger.info(
                                "Processed telemetry: imei=%s lat=%s lon=%s speed=%s vehicle_id=%s",
                                telemetry["imei"],
                                telemetry.get("latitude"),
                                telemetry.get("longitude"),
                                telemetry.get("speed_kmh"),
                                telemetry.get("vehicle_id"),
                            )

                        # Επιβεβαιώνουμε μόνο τη συγκεκριμένη εγγραφή που ολοκληρώθηκε.
                        # Δεν επιβεβαιώνουμε άλλα μηνύματα του batch πριν επεξεργαστούν.
                        partition = TopicPartition(message.topic, message.partition)

                        consumer.commit({
                            partition: OffsetAndMetadata(message.offset + 1, ""),
                        })

        except (KafkaError, psycopg2.Error):
            logger.exception(
                "Position processing failed. Uncommitted messages will be retried after reconnect."
            )

        finally:
            # Κλείνουμε τις παλιές συνδέσεις πριν δημιουργήσουμε καινούριες.
            try:
                consumer.close()
            finally:
                try:
                    position_event_producer.close()
                finally:
                    position_repository.close()

        if not stop_event.is_set():
            stop_event.wait(5)

    logger.info("Position consumption stopped.")