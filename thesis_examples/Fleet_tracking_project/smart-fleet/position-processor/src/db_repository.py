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

    def find_device_mapping_by_imei(self, device_imei: str) -> dict | None:
        # Διαβάζουμε την καταχωρισμένη αντιστοίχιση χωρίς να μαντεύουμε το μοντέλο.
        query = """
            SELECT vehicle_id, device_model
            FROM imei_vehicle_mappings
            WHERE device_imei = %s;
        """

        with self.connection.cursor() as cursor:
            cursor.execute(query, (device_imei,))
            row = cursor.fetchone()

        if row is None:
            logger.warning("No device mapping for imei=%s", device_imei)
            return None

        return {
            "vehicle_id": row[0],
            "device_model": row[1],
        }

    def save_position(self, telemetry: dict):
        # Η θέση και οι OBD μετρήσεις αποθηκεύονται στην ίδια χρονική εγγραφή.
        timestamp_ms = telemetry["timestamp_ms"]
        position_time = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

        obd = telemetry.get("obd")

        if not isinstance(obd, dict):
            obd = {}

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
                satellites,
                device_model,
                ignition_on,
                engine_rpm,
                coolant_temperature_c,
                fuel_level_percent,
                dtc_count
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
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
            telemetry.get("device_model"),
            obd.get("ignition_on"),
            obd.get("engine_rpm"),
            obd.get("coolant_temperature_c"),
            obd.get("fuel_level_percent"),
            obd.get("dtc_count"),
        )

        with self.connection.cursor() as cursor:
            cursor.execute(query, values)

        logger.info(
            "Saved historical position to TimescaleDB: imei=%s time=%s device_model=%s",
            telemetry.get("imei"),
            position_time,
            telemetry.get("device_model"),
        )


    def save_imei_vehicle_mapping(self, device_imei: str, vehicle_id: str, device_model: str = "GPS"):
        # Αποθηκεύουμε μαζί το όχημα και το μοντέλο της συσκευής.
        # Τα παλαιότερα events χωρίς μοντέλο αντιμετωπίζονται ως GPS.
        query = """
            WITH removed_mappings AS (
                DELETE FROM imei_vehicle_mappings
                WHERE vehicle_id = %s
                  AND device_imei <> %s
            )
            INSERT INTO imei_vehicle_mappings (
                device_imei,
                vehicle_id,
                device_model,
                updated_at
            )
            VALUES (%s, %s, %s, now())
            ON CONFLICT (device_imei)
            DO UPDATE SET
                vehicle_id = EXCLUDED.vehicle_id,
                device_model = EXCLUDED.device_model,
                updated_at = now();
        """

        values = (
            vehicle_id,
            device_imei,
            device_imei,
            vehicle_id,
            device_model,
        )

        with self.connection.cursor() as cursor:
            cursor.execute(query, values)

        logger.info(
            "Saved IMEI mapping: device_imei=%s vehicle_id=%s device_model=%s",
            device_imei,
            vehicle_id,
            device_model,
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
        return row[0][0]

    def get_vehicle_position_history(self, vehicle_id: str, start_time: datetime, end_time: datetime,
                                     limit: int, after_time: datetime | None = None, after_imei: str | None = None, ) -> dict:
        # Τα δύο στοιχεία ορίζουν μαζί τη θέση συνέχισης της προηγούμενης σελίδας.
        if (after_time is None) != (after_imei is None):
            raise ValueError("after_time and after_imei must be provided together.")

        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000.")

        # Αναζητούμε με vehicle_id ώστε το ιστορικό να αφορά το όχημα,
        # ακόμη και αν έχει χρησιμοποιήσει διαφορετικές συσκευές.
        query = """
            SELECT time, imei, vehicle_id, latitude, longitude,
                   speed_kmh, altitude_m, angle_deg, satellites,
                   device_model, ignition_on, engine_rpm,
                   coolant_temperature_c, fuel_level_percent, dtc_count
            FROM vehicle_positions
            WHERE vehicle_id = %s
              AND time >= %s
              AND time < %s
        """

        values = [vehicle_id, start_time, end_time]

        if after_time is not None:
            # Συνεχίζουμε μετά την τελευταία θέση της προηγούμενης σελίδας.
            # Το IMEI ξεχωρίζει εγγραφές με την ίδια χρονική στιγμή.
            query += " AND (time, imei) > (%s, %s)"
            values.extend([after_time, after_imei])

        query += " ORDER BY time ASC, imei ASC LIMIT %s"

        # Ζητάμε μία επιπλέον εγγραφή για να γνωρίζουμε αν υπάρχει επόμενη σελίδα.
        values.append(limit + 1)

        with self.connection.cursor() as cursor:
            cursor.execute(query, values)
            rows = cursor.fetchall()

        has_more = len(rows) > limit
        rows = rows[:limit]
        positions = []

        for row in rows:
            obd = None

            # Επιστρέφουμε τις μετρήσεις που αποθηκεύτηκαν στη συγκεκριμένη εγγραφή.
            # Δεν χρησιμοποιούμε το σημερινό μοντέλο συσκευής για παλιές θέσεις.
            if row[9] == "FMC003":
                obd = {
                    "ignition_on": row[10],
                    "engine_rpm": row[11],
                    "coolant_temperature_c": row[12],
                    "fuel_level_percent": row[13],
                    "dtc_count": row[14],
                }

            positions.append({
                "timestamp_ms": int(row[0].timestamp() * 1000),
                "imei": row[1],
                "vehicle_id": row[2],
                "latitude": row[3],
                "longitude": row[4],
                "speed_kmh": row[5],
                "altitude_m": row[6],
                "angle_deg": row[7],
                "satellites": row[8],
                "device_model": row[9],
                "obd": obd,
            })

        next_cursor = None

        if has_more:
            last_row = rows[-1]

            # Κρατάμε την ακριβή ώρα της βάσης για τη συνέχεια της αναζήτησης.
            next_cursor = {
                "after_time": last_row[0].isoformat(),
                "after_imei": last_row[1],
            }

        return {
            "vehicle_id": vehicle_id,
            "positions": positions,
            "has_more": has_more,
            "next_cursor": next_cursor,
        }

    def close(self):
        # Κλείνουμε τη σύνδεση όταν τερματίζει το service.
        self.connection.close()