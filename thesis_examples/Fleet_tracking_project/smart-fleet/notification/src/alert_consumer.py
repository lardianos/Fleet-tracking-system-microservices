import json
import logging
import os

import httpx

from contextlib import ExitStack

from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
from kafka.structs import OffsetAndMetadata, TopicPartition

from alert_delivery import deliver_alert
from alert_recipients import AlertRecipientResolver


logger = logging.getLogger(__name__)


def run_alert_notifications(stop_event):
    # Κρατάμε προσωρινά μόνο τις εκκρεμείς αποστολές.
    # Η πληροφορία αυτή δεν αποθηκεύεται σε βάση.
    pending_deliveries = {}

    while not stop_event.is_set():
        try:
            with ExitStack() as connections:
                http_client = httpx.Client(timeout=10.0)
                connections.callback(http_client.close)

                resolver = AlertRecipientResolver(http_client)

                producer = KafkaProducer(
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

                connections.callback(producer.close, timeout=10)

                consumer = KafkaConsumer(
                    os.getenv("KAFKA_TOPIC_ALERTS", "fleet.alerts"),
                    bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
                    group_id=os.getenv("NOTIFICATION_ALERTS_GROUP", "notification-alerts-group"),
                    auto_offset_reset="latest",
                    enable_auto_commit=False,
                    max_poll_records=10,
                )

                connections.callback(consumer.close)
                initialized_partitions = set()

                logger.info("Notification consuming vehicle alerts.")

                while not stop_event.is_set():
                    batches = consumer.poll(timeout_ms=1000, max_records=10)

                    for messages in batches.values():
                        for message in messages:
                            if stop_event.is_set():
                                return

                            partition = TopicPartition(
                                message.topic,
                                message.partition,
                            )

                            # Αποθηκεύουμε το αρχικό σημείο πριν από εξωτερικές
                            # αποστολές, ώστε ένα αποτυχημένο μήνυμα να ξαναζητηθεί.
                            if partition not in initialized_partitions:
                                consumer.commit({
                                    partition: OffsetAndMetadata(message.offset, ""),
                                })
                                initialized_partitions.add(partition)

                            alert = None
                            processed_alert_id = None

                            try:
                                alert = json.loads(message.value.decode("utf-8"))
                            except (UnicodeDecodeError, json.JSONDecodeError):
                                logger.error(
                                    "Invalid alert JSON: partition=%s offset=%s",
                                    message.partition,
                                    message.offset,
                                )

                            if isinstance(alert, dict) and alert.get("event_type") == "alert.triggered":
                                valid_ids = all(
                                    isinstance(alert.get(field), str) and alert[field].strip()
                                    for field in ("alert_id", "vehicle_id", "rule_id")
                                )

                                valid_time = (
                                    type(alert.get("timestamp_ms")) is int
                                    and alert["timestamp_ms"] > 0
                                )

                                if not valid_ids or not valid_time:
                                    logger.error(
                                        "Alert is missing required fields: offset=%s",
                                        message.offset,
                                    )
                                else:
                                    processed_alert_id = alert["alert_id"]

                                    if processed_alert_id not in pending_deliveries:
                                        pending_deliveries[processed_alert_id] = {
                                            "context": resolver.resolve_alert_recipients(alert),
                                            "completed": set(),
                                        }

                                    pending = pending_deliveries[processed_alert_id]

                                    deliver_alert(
                                        alert,
                                        pending["context"],
                                        producer,
                                        pending["completed"],
                                    )

                            # Επιβεβαιώνουμε μετά την ολοκλήρωση των αποστολών.
                            consumer.commit({
                                partition: OffsetAndMetadata(message.offset + 1, ""),
                            })

                            if processed_alert_id is not None:
                                pending_deliveries.pop(processed_alert_id, None)

        except (KafkaError, httpx.HTTPError, OSError, RuntimeError, ValueError):
            logger.exception(
                "Alert notification failed. Retrying in 5 seconds."
            )
            stop_event.wait(5)