class ObdSimulation:
    def __init__(self, initial_fuel_percent: float = 75, target_coolant_temperature: float = 90):
        self.coolant_temperature_c = 25.0
        self.fuel_level_percent = initial_fuel_percent
        self.target_coolant_temperature_c = target_coolant_temperature

    def advance(self, seconds: float, speed_kmh: int, state: str):
        # Στη μεγάλη στάση ο κινητήρας σβήνει.
        # Στις σύντομες στάσεις της διαδρομής παραμένει στο ρελαντί.
        engine_running = state not in ("DESTINATION_WAIT", "AT_BASE")

        if engine_running:
            # Η θερμοκρασία πλησιάζει σταδιακά τον στόχο του σεναρίου.
            if self.coolant_temperature_c < self.target_coolant_temperature_c:
                self.coolant_temperature_c = min(
                    self.target_coolant_temperature_c,
                    self.coolant_temperature_c + seconds * 0.15,
                )
            else:
                self.coolant_temperature_c = max(
                    self.target_coolant_temperature_c,
                    self.coolant_temperature_c - seconds * 0.03,
                )

            # Παραδοχές προσομοίωσης:
            # ρεζερβουάρ 50 λίτρων, 8 λίτρα/100 km και 0.8 λίτρα/ώρα στο ρελαντί.
            distance_km = speed_kmh * seconds / 3600
            consumed_litres = distance_km * 0.08

            if speed_kmh == 0:
                consumed_litres = 0.8 * seconds / 3600

            self.fuel_level_percent = max(
                0.0,
                self.fuel_level_percent - consumed_litres / 50 * 100,
            )
        else:
            # Με σβηστό κινητήρα η θερμοκρασία επιστρέφει προς τους 25 °C.
            self.coolant_temperature_c = max(
                25.0,
                self.coolant_temperature_c - seconds * 0.03,
            )

    def build_io_elements(self, speed_kmh: int, state: str) -> dict:
        engine_running = state not in ("DESTINATION_WAIT", "AT_BASE")

        ignition = 0
        engine_rpm = 0

        if engine_running:
            ignition = 1
            engine_rpm = min(4500, 800 + speed_kmh * 25)

        return {
            239: ignition.to_bytes(1, byteorder="big"),
            32: round(self.coolant_temperature_c).to_bytes(1, byteorder="big", signed=True),
            48: round(self.fuel_level_percent).to_bytes(1, byteorder="big"),
            30: (0).to_bytes(1, byteorder="big"),
            36: engine_rpm.to_bytes(2, byteorder="big"),
        }