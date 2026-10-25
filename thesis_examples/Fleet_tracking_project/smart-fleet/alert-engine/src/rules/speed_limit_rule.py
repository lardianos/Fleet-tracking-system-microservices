import logging
import math
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

logger = logging.getLogger(__name__)


@dataclass
class SpeedRuleState:
    vehicle_id: str
    last_timestamp_ms: int
    started_at_ms: int | None = None
    alert_sent: bool = False
    maximum_speed_kmh: float = 0


class SpeedLimitRule:
    rule_id = "SPEED_LIMIT"

    def __init__(self, speed_limit: float, duration_seconds: float, max_gap_seconds: float):
        for value in (speed_limit, duration_seconds, max_gap_seconds):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Rule settings must be positive finite numbers.")

        self.speed_limit = speed_limit
        self.duration_ms = round(duration_seconds * 1000)
        self.max_gap_ms = round(max_gap_seconds * 1000)
        self.states: dict[str, SpeedRuleState] = {}

    def reset_device(self, imei: str):
        self.states.pop(imei, None)

    def evaluate(self, position: dict) -> dict | None:
        imei = position.get("imei")

        if not isinstance(imei, str) or not imei:
            return None

        timestamp = position.get("timestamp_ms")
        speed = position.get("speed_kmh")
        vehicle_id = position.get("vehicle_id")
        latitude = position.get("latitude")
        longitude = position.get("longitude")

        valid_numbers = all(
            type(value) in (int, float) and math.isfinite(value)
            for value in (speed, latitude, longitude)
        )

        if (
            type(timestamp) is not int or timestamp <= 0
            or not valid_numbers
            or speed < 0 or not -90 <= latitude <= 90 or not -180 <= longitude <= 180
            or not isinstance(vehicle_id, str) or not vehicle_id
        ):
            self.reset_device(imei)
            logger.warning("Cannot evaluate speed rule: imei=%s", imei)
            return None

        state = self.states.get(imei)

        # Αγνοούμε διπλά ή παλαιότερα δείγματα πριν αλλάξουμε την κατάσταση.
        if state is not None and timestamp <= state.last_timestamp_ms:
            return None

        if state is None or state.vehicle_id != vehicle_id:
            state = SpeedRuleState(vehicle_id, timestamp)
            self.states[imei] = state

        elif timestamp - state.last_timestamp_ms > self.max_gap_ms:
            # Με μεγάλο κενό δεν τεκμηριώνεται συνεχόμενη υπέρβαση.
            state.started_at_ms = None
            state.alert_sent = False
            state.maximum_speed_kmh = 0

        state.last_timestamp_ms = timestamp

        if speed <= self.speed_limit:
            # Κλείνουμε το περιστατικό χωρίς δεύτερο alert.
            state.started_at_ms = None
            state.alert_sent = False
            state.maximum_speed_kmh = 0
            return None

        if state.started_at_ms is None:
            state.started_at_ms = timestamp

        state.maximum_speed_kmh = max(state.maximum_speed_kmh, speed)

        if state.alert_sent or timestamp - state.started_at_ms < self.duration_ms:
            return None

        state.alert_sent = True

        # Ίδια αρχή περιστατικού δίνει το ίδιο ID σε πιθανή επαναποστολή.
        alert_id = str(uuid5(
            NAMESPACE_URL,
            f"smart-fleet:{self.rule_id}:{vehicle_id}:{imei}:{state.started_at_ms}",
        ))

        return {
            "event_type": "alert.triggered",
            "alert_id": alert_id,
            "rule_id": self.rule_id,
            "vehicle_id": vehicle_id,
            "imei": imei,
            "started_at_ms": state.started_at_ms,
            "timestamp_ms": timestamp,
            "speed_limit_kmh": self.speed_limit,
            "required_duration_ms": self.duration_ms,
            "speed_kmh": speed,
            "maximum_speed_kmh": state.maximum_speed_kmh,
            "latitude": latitude,
            "longitude": longitude,
        }