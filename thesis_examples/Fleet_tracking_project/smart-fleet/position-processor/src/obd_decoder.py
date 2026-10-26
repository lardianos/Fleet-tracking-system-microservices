def read_obd_value(io_elements: dict, io_id: int, size: int, signed: bool = False) -> int | None:
    # Ο υπάρχων parser χρησιμοποιεί αριθμητικά IDs.
    # Μετά τη μετατροπή σε JSON, τα ίδια IDs γίνονται strings.
    value = io_elements.get(io_id)

    if value is None:
        value = io_elements.get(str(io_id))

    if value is None:
        return None

    # Τα άγνωστα IO πεδία διατηρούνται από τον parser ως hexadecimal strings.
    if isinstance(value, str):
        if not value.startswith("0x"):
            return None

        try:
            raw_value = bytes.fromhex(value[2:])
        except ValueError:
            return None

        if len(raw_value) != size:
            return None

        return int.from_bytes(raw_value, byteorder="big", signed=signed)

    if isinstance(value, bool) or not isinstance(value, int):
        return None

    # Ελέγχουμε ότι η ήδη αποκωδικοποιημένη τιμή χωράει στο αντίστοιχο πεδίο.
    minimum = 0
    maximum = (1 << (size * 8)) - 1

    if signed:
        minimum = -(1 << (size * 8 - 1))
        maximum = (1 << (size * 8 - 1)) - 1

    if value < minimum or value > maximum:
        return None

    return value


def decode_fmc003_obd(io_elements: dict) -> dict:
    # Κρατάμε κατανοητά ονόματα και μονάδες αντί για αριθμητικά IO IDs.
    ignition_value = read_obd_value(io_elements, 239, 1)
    engine_rpm = read_obd_value(io_elements, 36, 2)
    coolant_temperature = read_obd_value(io_elements, 32, 1, signed=True)
    fuel_level = read_obd_value(io_elements, 48, 1)
    dtc_count = read_obd_value(io_elements, 30, 1)

    ignition_on = None

    if ignition_value == 0:
        ignition_on = False
    elif ignition_value == 1:
        ignition_on = True

    # Απούσα ή μη έγκυρη μέτρηση παραμένει None, όχι μηδέν.
    if engine_rpm is not None and engine_rpm > 16384:
        engine_rpm = None

    if fuel_level is not None and fuel_level > 100:
        fuel_level = None

    return {
        "ignition_on": ignition_on,
        "engine_rpm": engine_rpm,
        "coolant_temperature_c": coolant_temperature,
        "fuel_level_percent": fuel_level,
        "dtc_count": dtc_count,
    }