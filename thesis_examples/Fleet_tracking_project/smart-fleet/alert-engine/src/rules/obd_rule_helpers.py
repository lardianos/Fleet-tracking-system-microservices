import math

from uuid import NAMESPACE_URL, uuid5


def read_obd_sample(position: dict, states: dict):
    imei = position.get("imei")
    vehicle_id = position.get("vehicle_id")
    timestamp = position.get("timestamp_ms")

    if not isinstance(imei, str) or not imei:
        return None

    if not isinstance(vehicle_id, str) or not vehicle_id:
        return None

    if type(timestamp) is not int or timestamp <= 0:
        return None

    state = states.get(imei)

    # Δεν αλλάζουμε την κατάσταση από διπλές ή παλαιότερες εγγραφές.
    if state is not None and timestamp <= state["timestamp_ms"]:
        return None

    gap_ms = 0

    # Η κατάσταση αφορά συγκεκριμένη συσκευή και συγκεκριμένο όχημα.
    if state is None or state["vehicle_id"] != vehicle_id:
        state = {
            "vehicle_id": vehicle_id,
            "timestamp_ms": timestamp,
            "alert_sent": False,
            "engine_running": None,
        }

        states[imei] = state
    else:
        gap_ms = timestamp - state["timestamp_ms"]

    state["timestamp_ms"] = timestamp

    obd = position.get("obd")

    if position.get("device_model") != "FMC003" or not isinstance(obd, dict):
        obd = {}

    return obd, state, gap_ms


def valid_obd_number(value, minimum: float, maximum: float) -> bool:
    # Το bool δεν αντιμετωπίζεται ως αριθμητική μέτρηση.
    return (
        type(value) in (int, float)
        and math.isfinite(value)
        and minimum <= value <= maximum
    )


def create_obd_alert(rule_id: str, position: dict, measurements: dict) -> dict:
    # Το ίδιο συμβάν και timestamp παράγουν το ίδιο αναγνωριστικό.
    alert_id = str(uuid5(
        NAMESPACE_URL,
        f"smart-fleet:{rule_id}:{position['vehicle_id']}:{position['imei']}:{position['timestamp_ms']}",
    ))

    alert = {
        "event_type": "alert.triggered",
        "alert_id": alert_id,
        "rule_id": rule_id,
        "vehicle_id": position["vehicle_id"],
        "imei": position["imei"],
        "timestamp_ms": position["timestamp_ms"],
        "latitude": position.get("latitude"),
        "longitude": position.get("longitude"),
    }

    alert.update(measurements)

    return alert