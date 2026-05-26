"""
Repository για την TimescaleDB.

Αυτό το αρχείο περιέχει όλη τη λογική που σχετίζεται με την αποθήκευση
ιστορικών θέσεων οχημάτων στη βάση TimescaleDB.

Ροή:
Position Processor
    ↓
TimescaleDB table: vehicle_positions
"""

import os
import logging
from datetime import datetime, timezone
import psycopg2

logger = logging.getLogger(__name__)


class PositionRepository:
    def __init__(self):
        # Διαβάζουμε τα στοιχεία σύνδεσης από environment variables.
        # Έτσι το service μπορεί να αλλάζει ρυθμίσεις χωρίς αλλαγή στον κώδικα.
        self.db_host = os.getenv("TIMESCALE_HOST", "timescaledb")
        self.db_port = int(os.getenv("TIMESCALE_PORT", "5432"))
        self.db_name = os.getenv("TIMESCALE_DB", "fleet_tracking")
        self.db_user = os.getenv("TIMESCALE_USER", "fleet_user")
        self.db_password = os.getenv("TIMESCALE_PASSWORD", "fleet_password")

        # Δημιουργούμε σύνδεση με την TimescaleDB.
        # Η σύνδεση μένει ανοιχτή όσο τρέχει το service.
        self.connection = psycopg2.connect(
            host=self.db_host,
            port=self.db_port,
            dbname=self.db_name,
            user=self.db_user,
            password=self.db_password,
        )

        # Ενεργοποιούμε autocommit ώστε κάθε insert να αποθηκεύεται άμεσα.
        self.connection.autocommit = True

        logger.info("Connected to TimescaleDB at %s:%s", self.db_host, self.db_port)

    def save_position(self, telemetry: dict):
        # Μετατρέπουμε το timestamp από milliseconds σε UTC datetime.
        # Το Kafka message έχει timestamp_ms από τη συσκευή Teltonika.
        timestamp_ms = telemetry.get("timestamp_ms")
        position_time = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

        # Εισάγουμε την ιστορική θέση στον πίνακα vehicle_positions.
        # Το ON CONFLICT χρησιμοποιείται για να μη σκάει το insert αν έρθει διπλότυπο
        # με ίδιο time και ίδιο imei.
        query = """
            INSERT INTO vehicle_positions (
                time,
                imei,
                latitude,
                longitude,
                speed_kmh,
                altitude_m,
                angle_deg,
                satellites
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (time, imei) DO NOTHING;
        """

        values = (
            position_time,
            telemetry.get("imei"),
            telemetry.get("latitude"),
            telemetry.get("longitude"),
            telemetry.get("speed_kmh"),
            telemetry.get("altitude_m"),
            telemetry.get("angle_deg"),
            telemetry.get("satellites"),
        )

        with self.connection.cursor() as cursor:
            cursor.execute(query, values)

        logger.info(
            "Saved historical position to TimescaleDB: imei=%s time=%s",
            telemetry.get("imei"),
            position_time,
        )

    def close(self):
        # Κλείνουμε τη σύνδεση όταν τερματίζει το service.
        self.connection.close()