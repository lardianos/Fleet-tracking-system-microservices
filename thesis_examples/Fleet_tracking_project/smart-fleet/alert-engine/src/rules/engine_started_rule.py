from rules.obd_rule_helpers import read_obd_sample, valid_obd_number, create_obd_alert


class EngineStartedRule:
    rule_id = "ENGINE_STARTED"

    def __init__(self, max_gap_seconds: float = 15):
        if not valid_obd_number(max_gap_seconds, 0.001, float("inf")):
            raise ValueError("Engine start maximum gap must be a positive finite number.")

        self.max_gap_ms = round(max_gap_seconds * 1000)
        self.states = {}

    def evaluate(self, position: dict) -> dict | None:
        sample = read_obd_sample(position, self.states)

        if sample is None:
            return None

        obd, state, gap_ms = sample

        # Με κενό άνω των 15 δευτερολέπτων δεν συμπεραίνουμε νέα εκκίνηση.
        # Ακολουθούμε τον χρόνο αναφοράς των simulators μας, που στέλνουν ανά 5 δευτερόλεπτα.
        if gap_ms > self.max_gap_ms:
            state["engine_running"] = None

        ignition = obd.get("ignition_on")
        rpm = obd.get("engine_rpm")

        if type(ignition) is not bool or not valid_obd_number(rpm, 0, 16384):
            # Η απουσία δεδομένων δεν σημαίνει σβηστός κινητήρας.
            state["engine_running"] = None
            return None

        if ignition is False and rpm == 0:
            state["engine_running"] = False
            return None

        if ignition is True and rpm > 0:
            previous_running = state["engine_running"]
            state["engine_running"] = True

            # Ειδοποιούμε μόνο αφού έχουμε παρατηρήσει σβηστό κινητήρα.
            if previous_running is False:
                return create_obd_alert(self.rule_id, position, {
                    "ignition_on": True,
                    "engine_rpm": rpm,
                })

        # Ignition On με μηδενικές στροφές δεν επιβεβαιώνει εκκίνηση.
        return None