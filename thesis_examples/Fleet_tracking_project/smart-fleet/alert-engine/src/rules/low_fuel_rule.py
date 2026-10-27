from rules.obd_rule_helpers import read_obd_sample, valid_obd_number, create_obd_alert


class LowFuelRule:
    rule_id = "LOW_FUEL"

    def __init__(self, fuel_limit_percent: float = 20):
        if not valid_obd_number(fuel_limit_percent, 0, 100):
            raise ValueError("Fuel limit must be between 0 and 100 percent.")

        self.fuel_limit_percent = fuel_limit_percent
        self.states = {}

    def evaluate(self, position: dict) -> dict | None:
        sample = read_obd_sample(position, self.states)

        if sample is None:
            return None

        obd, state, _ = sample
        fuel_level = obd.get("fuel_level_percent")

        if not valid_obd_number(fuel_level, 0, 100):
            return None

        if fuel_level >= self.fuel_limit_percent:
            # Επιτρέπουμε νέο περιστατικό αφού το καύσιμο επιστρέψει στο όριο ή ψηλότερα.
            state["alert_sent"] = False
            return None

        if state["alert_sent"]:
            return None

        state["alert_sent"] = True

        return create_obd_alert(self.rule_id, position, {
            "fuel_level_percent": fuel_level,
            "fuel_limit_percent": self.fuel_limit_percent,
        })