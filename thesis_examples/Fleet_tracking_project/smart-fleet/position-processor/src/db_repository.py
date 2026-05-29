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
                vehicle_id,
                latitude,
                longitude,
                speed_kmh,
                altitude_m,
                angle_deg,
                satellites
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (time, imei) DO NOTHING;
        """

        values = (
            position_time,
            telemetry.get("imei"),
            telemetry.get("vehicle_id"),
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

    def save_imei_vehicle_mapping(self, device_imei: str, vehicle_id: str):
        # Αποθηκεύουμε τη συσχέτιση IMEI → vehicle_id στο read model του Position Processor.
        # Το Fleet API παραμένει η πηγή αλήθειας για τα οχήματα.
        # Εδώ κρατάμε μόνο το ελάχιστο mapping που χρειάζεται το telemetry pipeline.
        query = """
            INSERT INTO imei_vehicle_mappings (
                device_imei,
                vehicle_id,
                updated_at
            )
            VALUES (%s, %s, now())
            ON CONFLICT (device_imei)
            DO UPDATE SET
            vehicle_id = EXCLUDED.vehicle_id,
            updated_at = now();
        """

        with self.connection.cursor() as cursor:
            cursor.execute(query, (device_imei, vehicle_id))

        logger.info(
            "Saved IMEI mapping: device_imei=%s vehicle_id=%s",
            device_imei,
            vehicle_id,
        )

    def find_vehicle_id_by_imei(self, device_imei: str):
        query = """
            SELECT vehicle_id from imei_vehicle_mappings
            where device_imei = %s
        """
        with self.connection.cursor() as cursor:
            cursor.execute(query, (device_imei,))
            row = cursor.fetchall()
        if not row:
            logger.warning("No vehicle ID for imei=%s", device_imei)
            return None
        return row[0]

    def close(self):
        # Κλείνουμε τη σύνδεση όταν τερματίζει το service.
        self.connection.close()