"""
Kafka Producer για το Fleet API.

Το Fleet API παραμένει υπεύθυνο για τη MongoDB και τα vehicle metadata.
Όταν δημιουργείται ένα όχημα, δημοσιεύει ένα event στο Kafka ώστε
τα υπόλοιπα services να ενημερώνονται χωρίς direct calls.
"""

import json
import os
import logging
from kafka import KafkaProducer

logger = logging.getLogger(__name__)


class FleetEventProducer:
    def __init__(self):
        # Ο Kafka broker και το topic διαβάζονται από environment variables,
        # ώστε να μη δένουμε τον κώδικα με συγκεκριμένο περιβάλλον.
        bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
        self.topic = os.getenv("KAFKA_TOPIC_FLEET_VEHICLES", "fleet.vehicles")

        # Ο producer μετατρέπει τα Python dictionaries σε JSON bytes.
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda value: json.dumps(value, ensure_ascii=False).encode("utf-8"),
            key_serializer=lambda key: key.encode("utf-8") if key else None,
        )

        logger.info("Fleet Kafka producer connected to %s", bootstrap_servers)

    def publish_vehicle_created(self, vehicle: dict):
        # Δημοσιεύουμε event δημιουργίας οχήματος.
        # Δεν στέλνουμε όλο το vehicle document, μόνο τα απαραίτητα στοιχεία
        # που χρειάζονται άλλα services για συσχέτιση IMEI → vehicle_id.
        event = {
            "event_type": "vehicle.created",
            "vehicle_id": str(vehicle["_id"]),
            "device_imei": vehicle["device_imei"],
        }

        future = self.producer.send(
            self.topic,
            key=event["device_imei"],
            value=event,
        )

        metadata = future.get(timeout=10)

        logger.info(
            "Published vehicle.created event: imei=%s topic=%s partition=%s offset=%s",
            event["device_imei"],
            metadata.topic,
            metadata.partition,
            metadata.offset,
        )