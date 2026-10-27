import json
import logging
import os
import signal

from contextlib import ExitStack
from threading import Event

from kafka import KafkaConsumer
from kafka.errors import KafkaError
from kafka.structs import OffsetAndMetadata, TopicPartition

from kafka_producer import AlertEventProducer

from rules.speed_limit_rule import SpeedLimitRule
from rules.engine_started_rule import EngineStartedRule
from rules.high_coolant_temperature_rule import HighCoolantTemperatureRule
from rules.low_fuel_rule import LowFuelRule

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

stop_event = Event()


def request_alert_engine_shutdown(signum, frame):
    logger.info("Alert Engine shutdown requested.")
    stop_event.set()


def consume_positions_for_rules(consumer, alert_producer, rules):
    while not stop_event.is_set():
        batches = consumer.poll(timeout_ms=1000, max_records=20)

        for messages in batches.values():
            for message in messages:
                if stop_event.is_set():
                    return

                position = None

                try:
                    position = json.loads(message.value.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    logger.error(
                        "Invalid position JSON: partition=%s offset=%s",
                        message.partition,
                        message.offset,
                    )

                if isinstance(position, dict):
                    # Κάθε κανόνας αξιολογεί την ίδια θέση ανεξάρτητα.
                    for rule in rules:
                        alert = rule.evaluate(position)

                        if alert is not None:
                            alert_producer.publish_alert(alert)

                elif position is not None:
                    logger.error(
                        "Position payload must be an object: partition=%s offset=%s",
                        message.partition,
                        message.offset,
                    )

                # Επιβεβαιώνουμε μόνο το συγκεκριμένο μήνυμα που ολοκληρώθηκε.
                # Δεν κάνουμε commit για άλλα μηνύματα που έχουν ήδη φορτωθεί.
                partition = TopicPartition(message.topic, message.partition)

                consumer.commit({
                    partition: OffsetAndMetadata(message.offset + 1, ""),
                })


def run_alert_engine():
    while not stop_event.is_set():
        try:
            with ExitStack() as connections:
                alert_producer = AlertEventProducer()
                connections.callback(alert_producer.close)

                consumer = KafkaConsumer(
                    os.getenv("KAFKA_TOPIC_PROCESSED_POSITIONS", "processed.positions"),
                    bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
                    group_id=os.getenv("KAFKA_CONSUMER_GROUP", "alert-engine-group"),
                    auto_offset_reset="latest",
                    enable_auto_commit=False,
                    max_poll_records=20,
                )

                connections.callback(consumer.close)

                # Προσθέτουμε εδώ νέους κανόνες χωρίς να αλλάζουμε τον consumer.
                rules = [
                    SpeedLimitRule(
                        speed_limit=float(os.getenv("SPEED_LIMIT_KMH", "100")),
                        duration_seconds=float(os.getenv("SPEED_DURATION_SECONDS", "10")),
                        max_gap_seconds=float(os.getenv("MAX_POSITION_GAP_SECONDS", "15")),
                    ),
                    EngineStartedRule(
                        max_gap_seconds=float(os.getenv("ENGINE_STARTED_MAX_GAP_SECONDS", "15")),
                    ),
                    HighCoolantTemperatureRule(
                        temperature_limit_c=float(os.getenv("COOLANT_TEMPERATURE_LIMIT_C", "100")),
                    ),
                    LowFuelRule(
                        fuel_limit_percent=float(os.getenv("FUEL_LIMIT_PERCENT", "20")),
                    ),
                ]

                logger.info(
                    "Alert Engine consuming positions. Rules: %s",
                    [rule.rule_id for rule in rules],
                )

                consume_positions_for_rules(consumer, alert_producer, rules)

        except KafkaError:
            logger.exception(
                "Kafka operation failed. Reconnecting Alert Engine in 5 seconds."
            )

            # Η αναμονή διακόπτεται αμέσως όταν ζητηθεί τερματισμός.
            stop_event.wait(5)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, request_alert_engine_shutdown)
    signal.signal(signal.SIGINT, request_alert_engine_shutdown)

    run_alert_engine()