# Κάθε καταχώριση αντιστοιχεί σε ένα rule_id του Alert Engine.
# Η επιλογή παραληπτών και καναλιών ανήκει αποκλειστικά στο Notification.
ALERT_POLICIES = {
    "SPEED_LIMIT": {
        "recipients": {
            "driver": ["dashboard"],
            "fleet_manager": ["dashboard", "email"],
            "admin": ["dashboard", "email"],
        },
        "title": "Speed limit exceeded - {plate_number}",
        "message": "Speed {speed_kmh} km/h exceeded the {speed_limit_kmh} km/h limit.",
    },
    "ENGINE_STARTED": {
        "recipients": {
            "driver": ["dashboard"],
        },
        "title": "Engine started - {plate_number}",
        "message": "The engine of your vehicle {plate_number} has started.",
    },
    "HIGH_COOLANT_TEMPERATURE": {
        "recipients": {
            "driver": ["dashboard"],
            "fleet_manager": ["dashboard", "email"],
            "admin": ["dashboard", "email"],
        },
        "title": "High engine temperature - {plate_number}",
        "message": (
            "Coolant temperature is {coolant_temperature_c} °C, "
            "above the {temperature_limit_c} °C limit."
        ),
    },
    "LOW_FUEL": {
        "recipients": {
            "driver": ["dashboard"],
        },
        "title": "Low fuel level - {plate_number}",
        "message": (
            "Your vehicle's fuel level is {fuel_level_percent}%, "
            "below the {fuel_limit_percent}% limit."
        ),
    },
}


def get_alert_policy(rule_id: str) -> dict:
    policy = ALERT_POLICIES.get(rule_id)

    if policy is None:
        raise ValueError(f"No notification policy configured for rule: {rule_id}")

    return policy


def build_alert_text(alert: dict, context: dict) -> tuple[str, str]:
    policy = get_alert_policy(alert["rule_id"])

    # Οι μετρήσεις προέρχονται από το alert και η πινακίδα από το vehicle context.
    values = dict(alert)
    values["plate_number"] = context["plate_number"]

    title = policy["title"].format(**values)
    message = policy["message"].format(**values)

    return title, message