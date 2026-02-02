# src/codec8_parser.py
from typing import List, Dict, Any, Tuple
import struct
import decimal

from models import AvlRecord


class Codec8ParseError(Exception):
    pass


# -------------------------
# Helpers
# -------------------------

def _read_int(buf: bytes, offset: int, size: int, signed: bool = False) -> Tuple[int, int]:
    """Read big-endian integer of given size from buf starting at offset."""
    end = offset + size
    if end > len(buf):
        raise Codec8ParseError("Unexpected end of buffer while reading integer")
    value = int.from_bytes(buf[offset:end], byteorder="big", signed=signed)
    return value, end


def _read_bytes(buf: bytes, offset: int, size: int) -> Tuple[bytes, int]:
    """Read raw bytes from buf starting at offset."""
    end = offset + size
    if end > len(buf):
        raise Codec8ParseError("Unexpected end of buffer while reading bytes")
    return buf[offset:end], end


# -------------------------
# IO parsing functions (από τον δικό σου κώδικα, προσαρμοσμένα)
# -------------------------

def parse_data_integer(hex_str: str) -> int:
    return int(hex_str, 16)


def int_multiply_01(hex_str: str) -> float:
    return float(decimal.Decimal(int(hex_str, 16)) * decimal.Decimal("0.1"))


def int_multiply_001(hex_str: str) -> float:
    return float(decimal.Decimal(int(hex_str, 16)) * decimal.Decimal("0.01"))


def int_multiply_0001(hex_str: str) -> float:
    return float(decimal.Decimal(int(hex_str, 16)) * decimal.Decimal("0.001"))


def signed_no_multiply(hex_str: str) -> int:
    """Signed 32-bit (big-endian) from hex string."""
    try:
        binary = bytes.fromhex(hex_str.zfill(8))
        value = struct.unpack(">i", binary)[0]
        return value
    except Exception as e:
        # Fallback – keep raw
        return int(hex_str, 16)


# ίδιο dictionary με τον δικό σου κώδικα
parse_functions_dictionary = {
    240: parse_data_integer,
    239: parse_data_integer,
    80: parse_data_integer,
    21: parse_data_integer,
    200: parse_data_integer,
    69: parse_data_integer,
    181: int_multiply_01,
    182: int_multiply_01,
    66: int_multiply_0001,
    24: parse_data_integer,
    205: parse_data_integer,
    206: parse_data_integer,
    67: int_multiply_0001,
    68: int_multiply_0001,
    241: parse_data_integer,
    299: parse_data_integer,
    16: parse_data_integer,
    1: parse_data_integer,
    9: parse_data_integer,
    179: parse_data_integer,
    12: int_multiply_0001,
    13: int_multiply_001,
    17: signed_no_multiply,
    18: signed_no_multiply,
    19: signed_no_multiply,
    11: parse_data_integer,
    10: parse_data_integer,
    2: parse_data_integer,
    3: parse_data_integer,
    6: int_multiply_0001,
    180: parse_data_integer,
}


def sorting_hat(key: int, value_bytes: bytes) -> Any:
    """
    Παίρνει IO ID (key) και raw value bytes.
    Τα μετατρέπει σε hex string και καλεί την κατάλληλη parse_function αν υπάρχει.
    """
    hex_value = value_bytes.hex()
    if key in parse_functions_dictionary:
        parse_function = parse_functions_dictionary[key]
        return parse_function(hex_value)
    else:
        # Αν δεν έχουμε mapping, κρατάμε raw hex
        return f"0x{hex_value}"


# -------------------------
# Core parser (Codec 8 + 8E)
# -------------------------

def parse_codec8_payload(payload: bytes, imei: str) -> List[AvlRecord]:
    """
    Parse Teltonika Codec8 / Codec8E payload (χωρίς preamble, data_length, CRC).
    payload: bytes από CodecID μέχρι NumberOfData2.
    Επιστρέφει λίστα από AvlRecord με io_elements.
    """
    if len(payload) < 3:
        raise Codec8ParseError("Payload too short")

    codec_id = payload[0]
    if codec_id not in (0x08, 0x8E):
        raise Codec8ParseError(f"Unsupported codec id: 0x{codec_id:02X}")

    # Για 08 και 8E, NumberOfData1 είναι 1 byte
    number_of_data_1 = payload[1]
    offset = 2

    records: List[AvlRecord] = []

    for _ in range(number_of_data_1):
        # 1) Timestamp (8 bytes, ms)
        timestamp_ms, offset = _read_int(payload, offset, 8, signed=False)

        # 2) Priority (1 byte)
        if offset >= len(payload):
            raise Codec8ParseError("Unexpected end at priority")
        priority = payload[offset]
        offset += 1

        # 3) GPS element (lon, lat, altitude, angle, satellites, speed)
        lon_raw, offset = _read_int(payload, offset, 4, signed=True)
        lat_raw, offset = _read_int(payload, offset, 4, signed=True)
        altitude, offset = _read_int(payload, offset, 2, signed=True)
        angle, offset = _read_int(payload, offset, 2, signed=False)

        if offset >= len(payload):
            raise Codec8ParseError("Unexpected end at satellites")
        satellites = payload[offset]
        offset += 1

        speed, offset = _read_int(payload, offset, 2, signed=False)

        # 4) IO element (διαφέρει μεταξύ 08 και 8E)
        io_elements: Dict[int, Any] = {}

        if codec_id == 0x08:
            # Codec 8 – 1-byte ids & counters
            event_io_id, offset = _read_int(payload, offset, 1, signed=False)
            total_io, offset = _read_int(payload, offset, 1, signed=False)

            # 1-byte IO
            n1, offset = _read_int(payload, offset, 1, signed=False)
            for _i in range(n1):
                io_id, offset = _read_int(payload, offset, 1, signed=False)
                value_bytes, offset = _read_bytes(payload, offset, 1)
                io_elements[io_id] = sorting_hat(io_id, value_bytes)

            # 2-byte IO
            n2, offset = _read_int(payload, offset, 1, signed=False)
            for _i in range(n2):
                io_id, offset = _read_int(payload, offset, 1, signed=False)
                value_bytes, offset = _read_bytes(payload, offset, 2)
                io_elements[io_id] = sorting_hat(io_id, value_bytes)

            # 4-byte IO
            n4, offset = _read_int(payload, offset, 1, signed=False)
            for _i in range(n4):
                io_id, offset = _read_int(payload, offset, 1, signed=False)
                value_bytes, offset = _read_bytes(payload, offset, 4)
                io_elements[io_id] = sorting_hat(io_id, value_bytes)

            # 8-byte IO
            n8, offset = _read_int(payload, offset, 1, signed=False)
            for _i in range(n8):
                io_id, offset = _read_int(payload, offset, 1, signed=False)
                value_bytes, offset = _read_bytes(payload, offset, 8)
                io_elements[io_id] = sorting_hat(io_id, value_bytes)

        else:
            # Codec 8E – 2-byte ids & counters + X-byte IO
            event_io_id, offset = _read_int(payload, offset, 2, signed=False)
            total_io, offset = _read_int(payload, offset, 2, signed=False)

            # 1-byte IO
            n1, offset = _read_int(payload, offset, 2, signed=False)
            for _i in range(n1):
                io_id, offset = _read_int(payload, offset, 2, signed=False)
                value_bytes, offset = _read_bytes(payload, offset, 1)
                io_elements[io_id] = sorting_hat(io_id, value_bytes)

            # 2-byte IO
            n2, offset = _read_int(payload, offset, 2, signed=False)
            for _i in range(n2):
                io_id, offset = _read_int(payload, offset, 2, signed=False)
                value_bytes, offset = _read_bytes(payload, offset, 2)
                io_elements[io_id] = sorting_hat(io_id, value_bytes)

            # 4-byte IO
            n4, offset = _read_int(payload, offset, 2, signed=False)
            for _i in range(n4):
                io_id, offset = _read_int(payload, offset, 2, signed=False)
                value_bytes, offset = _read_bytes(payload, offset, 4)
                io_elements[io_id] = sorting_hat(io_id, value_bytes)

            # 8-byte IO
            n8, offset = _read_int(payload, offset, 2, signed=False)
            for _i in range(n8):
                io_id, offset = _read_int(payload, offset, 2, signed=False)
                value_bytes, offset = _read_bytes(payload, offset, 8)
                io_elements[io_id] = sorting_hat(io_id, value_bytes)

            # X-byte IO (μόνο σε 8E)
            nX, offset = _read_int(payload, offset, 2, signed=False)
            for _i in range(nX):
                io_id, offset = _read_int(payload, offset, 2, signed=False)
                value_len, offset = _read_int(payload, offset, 2, signed=False)
                value_bytes, offset = _read_bytes(payload, offset, value_len)
                io_elements[io_id] = sorting_hat(io_id, value_bytes)

        # Μετατροπή συντεταγμένων
        latitude = lat_raw / 10_000_000.0
        longitude = lon_raw / 10_000_000.0

        rec = AvlRecord(
            imei=imei,
            codec_id=codec_id,
            timestamp_ms=timestamp_ms,
            latitude=latitude,
            longitude=longitude,
            speed_kmh=speed,
            angle_deg=angle,
            altitude_m=altitude,
            satellites=satellites,
            priority=priority,
            event_io_id=event_io_id,
            io_elements=io_elements,
        )
        records.append(rec)

    # NumberOfData2 (τελευταίο byte)
    if offset >= len(payload):
        raise Codec8ParseError("Missing NumberOfData2")
    number_of_data_2 = payload[offset]
    if number_of_data_2 != number_of_data_1:
        raise Codec8ParseError(
            f"NumberOfData1 ({number_of_data_1}) != NumberOfData2 ({number_of_data_2})"
        )

    return records