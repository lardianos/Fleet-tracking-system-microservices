import json
import logging
import os
import signal

import httpx

from contextlib import ExitStack
from threading import Event, Thread

from kafka import KafkaConsumer
from kafka.errors import KafkaError
from kafka.structs import OffsetAndMetadata, TopicPartition

from keycloak_notifications import KeycloakNotificationClient
from alert_consumer import run_alert_notifications

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

stop_event = Event()


def request_notification_shutdown(signum, frame):
    logger.info("Notification service shutdown requested.")
    stop_event.set()


def consume_account_notifications(consumer, keycloak_notifications, completed_events):
    supported_events = {"driver.created", "fleet_manager.created"}

    while not stop_event.is_set():
        batches = consumer.poll(timeout_ms=1000, max_records=10)

        for messages in batches.values():
            for message in messages:
                if stop_event.is_set():
                    return

                event = None

                try:
                    event = json.loads(message.value.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    logger.error(
                        "Invalid account event JSON: partition=%s offset=%s",
                        message.partition,
                        message.offset,
                    )

                if isinstance(event, dict) and event.get("event_type") in supported_events:
                    required_fields = ("event_id", "entity_id", "keycloak_user_id")

                    valid_event = all(
                        isinstance(event.get(field), str) and event[field].strip()
                        for field in required_fields
                    )

                    if not valid_event:
                        logger.error(
                            "Account event is missing required IDs: partition=%s offset=%s",
                            message.partition,
                            message.offset,
                        )

                    elif event["event_id"] not in completed_events:
                        keycloak_notifications.send_account_setup_email(event)

                        # Η προσωρινή μνήμη αποτρέπει επανάληψη μετά από
                        # αποτυχία commit όσο παραμένει ενεργό το ίδιο process.
                        completed_events.add(event["event_id"])

                # Επιβεβαιώνουμε μόνο το μήνυμα που ολοκληρώθηκε.
                partition = TopicPartition(message.topic, message.partition)

                consumer.commit({
                    partition: OffsetAndMetadata(message.offset + 1, ""),
                })


def run_notification_service():
    completed_events: set[str] = set()

    while not stop_event.is_set():
        try:
            with ExitStack() as connections:
                http_client = httpx.Client(timeout=10.0)
                connections.callback(http_client.close)

                keycloak_notifications = KeycloakNotificationClient(http_client)

                consumer = KafkaConsumer(
                    os.getenv("KAFKA_TOPIC_ACCOUNTS", "fleet.accounts"),
                    bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
                    group_id=os.getenv("KAFKA_CONSUMER_GROUP", "notification-accounts-group"),
                    auto_offset_reset="earliest",
                    enable_auto_commit=False,
                    max_poll_records=10,
                )

                connections.callback(consumer.close)

                logger.info("Notification service consuming account events.")

                consume_account_notifications(
                    consumer,
                    keycloak_notifications,
                    completed_events,
                )

        except (KafkaError, httpx.HTTPError, RuntimeError):
            logger.exception(
                "Account notification failed. Reconnecting in 5 seconds."
            )

            # Το αποτυχημένο μήνυμα δεν έχει επιβεβαιωθεί,
            # επομένως μπορεί να ανακτηθεί ξανά από το Kafka.
            stop_event.wait(5)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, request_notification_shutdown)
    signal.signal(signal.SIGINT, request_notification_shutdown)

    alert_notification_thread = Thread(
        target=run_alert_notifications,
        args=(stop_event,),
        name="alert-notifications",
        daemon=True,
    )

    alert_notification_thread.start()

    try:
        run_notification_service()
    finally:
        stop_event.set()
        alert_notification_thread.join()