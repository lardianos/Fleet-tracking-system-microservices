from rules.obd_rule_helpers import read_obd_sample, valid_obd_number, create_obd_alert


class HighCoolantTemperatureRule:
    rule_id = "HIGH_COOLANT_TEMPERATURE"

    def __init__(self, temperature_limit_c: float = 100):
        if not valid_obd_number(temperature_limit_c, -128, 127):
            raise ValueError("Coolant temperature limit must be between -128 and 127 °C.")

        self.temperature_limit_c = temperature_limit_c
        self.states = {}

    def evaluate(self, position: dict) -> dict | None:
        sample = read_obd_sample(position, self.states)

        if sample is None:
            return None

        obd, state, _ = sample
        temperature = obd.get("coolant_temperature_c")

        if not valid_obd_number(temperature, -128, 127):
            return None

        if temperature <= self.temperature_limit_c:
            # Νέο alert επιτρέπεται αφού η θερμοκρασία επιστρέψει εντός ορίου.
            state["alert_sent"] = False
            return None

        if state["alert_sent"]:
            return None

        state["alert_sent"] = True

        return create_obd_alert(self.rule_id, position, {
            "coolant_temperature_c": temperature,
            "temperature_limit_c": self.temperature_limit_c,
        })