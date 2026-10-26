#!/usr/bin/env python3
"""
Teltonika Codec 8 TCP simulator (sends IMEI, waits ACK 0x01, then sends Codec8 AVL packet).
Compatible with Teltonika Codec 8 (minimal AVL record, no IO elements or with simple IO).
"""
import socket
import struct
import time
import math
import logging
import argparse
from vehicle_simulation import VehicleSimulation
from obd_simulation import ObdSimulation

from typing import Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------
# CRC-16/IBM (poly 0xA001) utility
# -------------------------
def crc16_ibm(data: bytes) -> int:
    crc = 0x0000
    for b in data:
        crc ^= b
        for _ in range(8):
            if (crc & 0x0001):
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF

# -------------------------
# Packet builders (Codec 8)
# -------------------------
def build_imei_blob(imei: str) -> bytes:
    imei_bytes = imei.encode('ascii')
    length = len(imei_bytes)
    return struct.pack(">H", length) + imei_bytes  # 2 bytes big-endian length, then ASCII

def pack_int32_deg7(value_deg: float) -> int:
    """
    Convert degrees float to Teltonika internal integer (deg * 10^7) as signed 32-bit
    """
    return int(value_deg * 1e7)

def build_codec8_io(io_elements: dict | None) -> bytes:
    # Χωρίς πρόσθετα δεδομένα επιστρέφουμε το ίδιο κενό IO τμήμα όπως πριν.
    if io_elements is None:
        return b"\x00\x00\x00\x00\x00\x00"

    if len(io_elements) > 255:
        raise ValueError("Too many Codec 8 IO elements.")

    # Event IO ID = 0: περιοδική εγγραφή, χωρίς συγκεκριμένο IO event.
    io_part = bytes([0, len(io_elements)])

    for size in (1, 2, 4, 8):
        matching_elements = []

        for io_id, value in io_elements.items():
            if not 0 <= io_id <= 255:
                raise ValueError("Codec 8 IO IDs must be between 0 and 255.")

            if not isinstance(value, bytes) or len(value) not in (1, 2, 4, 8):
                raise ValueError("Invalid Codec 8 IO value.")

            if len(value) == size:
                matching_elements.append((io_id, value))

        io_part += bytes([len(matching_elements)])

        for io_id, value in matching_elements:
            io_part += bytes([io_id]) + value

    return io_part

def build_codec8_avl_packet(latitude: float, longitude: float, speed_kmh: int = 0,
                            altitude_m: int = 0, angle_deg: int = 0, satellites: int = 0,
                            priority: int = 0, io_elements: dict | None = None) -> bytes:
    # Διατηρούμε Codec 8 και μία εγγραφή ανά πακέτο.
    timestamp_ms = int(time.time() * 1000)

    gps_part = (
        struct.pack(">i", pack_int32_deg7(longitude))
        + struct.pack(">i", pack_int32_deg7(latitude))
        + struct.pack(">h", int(altitude_m))
        + struct.pack(">H", int(angle_deg))
        + struct.pack("B", satellites)
        + struct.pack(">H", int(speed_kmh))
    )

    avl_record = (
        struct.pack(">Q", timestamp_ms)
        + struct.pack("B", priority)
        + gps_part
        + build_codec8_io(io_elements)
    )

    return b"\x08\x01" + avl_record + b"\x01"

def build_full_tcp_packet(codec_payload: bytes) -> bytes:
    """
    For TCP (Codec 8) packet structure:
    - 4 bytes preamble zeros (0x00000000)
    - 4 bytes data length (size from CodecID to NumberOfData2)
    - payload (CodecID ... NumberOfData2)
    - 4 bytes CRC-16 (first two bytes zero, last two are CRC)
    """
    preamble = b'\x00\x00\x00\x00'
    data_field_length = struct.pack(">I", len(codec_payload))  # 4 bytes
    crc_value = crc16_ibm(codec_payload)
    crc_4bytes = struct.pack(">I", crc_value & 0xFFFF)  # The top 2 bytes are zeros per Teltonika wiki
    full = preamble + data_field_length + codec_payload + crc_4bytes
    return full

# -------------------------
# Simulator main
# -------------------------
# Συνθετικές κλειστές διαδρομές για ελεγχόμενες δοκιμές.
# Τα σημεία δεν αποτελούν αντιστοίχιση στο οδικό δίκτυο.
SIMULATOR_ROUTES = {
    "route_1": [
        (38.0250, 23.7800),
        (38.0250, 23.7880),
        (38.0300, 23.7880),
        (38.0300, 23.7800),
        (38.0250, 23.7800),
    ],
    "route_2": [
        (37.9900, 23.7350),
        (37.9900, 23.7430),
        (37.9960, 23.7430),
        (37.9960, 23.7350),
        (37.9900, 23.7350),
    ],
}


def calculate_distance_m(first: tuple, second: tuple) -> float:
    # Υπολογίζουμε την απόσταση δύο σημείων με τον τύπο Haversine.
    latitude_1 = math.radians(first[0])
    latitude_2 = math.radians(second[0])
    latitude_difference = latitude_2 - latitude_1
    longitude_difference = math.radians(second[1] - first[1])

    value = (
        math.sin(latitude_difference / 2) ** 2
        + math.cos(latitude_1) * math.cos(latitude_2)
        * math.sin(longitude_difference / 2) ** 2
    )

    value = max(0.0, min(1.0, value))

    return 6371000 * 2 * math.atan2(
        math.sqrt(value),
        math.sqrt(1 - value),
    )


def calculate_angle_deg(first: tuple, second: tuple) -> int:
    # Η κατεύθυνση ακολουθεί το τμήμα της διαδρομής που διανύουμε.
    latitude_1 = math.radians(first[0])
    latitude_2 = math.radians(second[0])
    longitude_difference = math.radians(second[1] - first[1])

    horizontal = math.sin(longitude_difference) * math.cos(latitude_2)

    vertical = (
        math.cos(latitude_1) * math.sin(latitude_2)
        - math.sin(latitude_1) * math.cos(latitude_2)
        * math.cos(longitude_difference)
    )

    return round(math.degrees(math.atan2(horizontal, vertical))) % 360


class SimulatedRoute:
    def __init__(self, route_name: str, start_point: int):
        self.points = SIMULATOR_ROUTES[route_name]
        self.segment_lengths = []

        for index in range(len(self.points) - 1):
            self.segment_lengths.append(
                calculate_distance_m(
                    self.points[index],
                    self.points[index + 1],
                )
            )

        self.total_length = sum(self.segment_lengths)

        # Κάθε container μπορεί να ξεκινά από διαφορετική γωνία της διαδρομής.
        self.distance_m = sum(self.segment_lengths[:start_point])

    def advance(self, elapsed_seconds: float, speed_kmh: int) -> tuple:
        # Η μετακίνηση εξαρτάται από την ταχύτητα και τον πραγματικό χρόνο.
        # Όταν ολοκληρωθεί ένας κύκλος, συνεχίζουμε από την αρχή.
        self.distance_m = (
            self.distance_m + speed_kmh / 3.6 * elapsed_seconds
        ) % self.total_length

        remaining_distance = self.distance_m

        for index, segment_length in enumerate(self.segment_lengths):
            if remaining_distance < segment_length:
                first = self.points[index]
                second = self.points[index + 1]
                fraction = remaining_distance / segment_length

                latitude = first[0] + (second[0] - first[0]) * fraction
                longitude = first[1] + (second[1] - first[1]) * fraction
                angle = calculate_angle_deg(first, second)

                return latitude, longitude, angle

            remaining_distance -= segment_length

        # Καλύπτουμε μικρές αποκλίσεις κινητής υποδιαστολής στο τέλος του κύκλου.
        return (
            self.points[0][0],
            self.points[0][1],
            calculate_angle_deg(self.points[0], self.points[1]),
        )

def receive_exact(sock: socket.socket, length: int) -> bytes:
    # Το TCP μπορεί να παραδώσει το ACK σε περισσότερα από ένα recv.
    received = bytearray()

    while len(received) < length:
        part = sock.recv(length - len(received))

        if not part:
            raise ConnectionError("Gateway closed the connection.")

        received.extend(part)

    return bytes(received)


def run_simulator(args):
    obd_simulation = None

    if args.device_type == "obd":
        obd_simulation = ObdSimulation()
    simulation = None

    while simulation is None:
        try:
            simulation = VehicleSimulation(args)
        except OSError as error:
            logger.warning(
                "Routing unavailable: %s; retrying in 5 seconds",
                error,
            )

            time.sleep(5)

    logger.info(
        "Routes ready: imei=%s outbound=%.0fm return=%.0fm",
        args.imei,
        simulation.routes[0].length,
        simulation.routes[1].length,
    )

    pending_packet = None
    pending_position = None
    last_update = None
    next_send = 0.0

    while True:
        try:
            with socket.create_connection(
                (args.host, args.port),
                timeout=10,
            ) as sock:
                sock.sendall(build_imei_blob(args.imei))

                if receive_exact(sock, 1) != b"\x01":
                    raise ConnectionError("Gateway rejected the IMEI.")

                while True:
                    now = time.monotonic()

                    if last_update is not None:
                        elapsed_seconds = now - last_update

                        # Ενημερώνουμε τα OBD στοιχεία με την κατάσταση του προηγούμενου διαστήματος.
                        if obd_simulation is not None:
                            previous_position = simulation.snapshot()

                            obd_simulation.advance(
                                elapsed_seconds,
                                previous_position[2],
                                previous_position[4],
                            )

                        simulation.advance(elapsed_seconds)

                    last_update = now

                    if pending_packet is None and now >= next_send:
                        pending_position = simulation.snapshot()
                        latitude, longitude, speed, angle, state = pending_position

                        io_elements = None

                        if obd_simulation is not None:
                            io_elements = obd_simulation.build_io_elements(speed, state)

                        payload = build_codec8_avl_packet(
                            latitude=latitude,
                            longitude=longitude,
                            speed_kmh=speed,
                            altitude_m=80,
                            angle_deg=angle,
                            satellites=10,
                            priority=0,
                            io_elements=io_elements,
                        )

                        pending_packet = build_full_tcp_packet(payload)

                    if pending_packet is not None:
                        sock.sendall(pending_packet)

                        accepted = struct.unpack(
                            ">I",
                            receive_exact(sock, 4),
                        )[0]

                        if accepted != 1:
                            raise ConnectionError(
                                "Gateway did not acknowledge the record."
                            )

                        latitude, longitude, speed, angle, state = pending_position

                        logger.info(
                            "ACK imei=%s state=%s lat=%.7f lon=%.7f speed=%s angle=%s",
                            args.imei,
                            state,
                            latitude,
                            longitude,
                            speed,
                            angle,
                        )

                        # Το πακέτο διατηρείται μέχρι το ACK, ακόμη και σε επανασύνδεση.
                        pending_packet = None
                        next_send = time.monotonic() + args.interval

                    time.sleep(0.2)

        except OSError as error:
            logger.warning(
                "Connection interrupted: imei=%s error=%s; retrying in 5 seconds",
                args.imei,
                error,
            )

            time.sleep(5)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Teltonika road trip simulator"
    )

    parser.add_argument("--host", "-H", default="127.0.0.1")
    parser.add_argument("--port", "-P", type=int, default=7494)
    parser.add_argument("--imei", "-i", default="123456789012345")
    parser.add_argument("--interval", "-t", type=float, default=5)

    parser.add_argument(
        "--routing-url",
        default="http://simulator-routing:5000",
    )

    parser.add_argument("--base-latitude", type=float, required=True)
    parser.add_argument("--base-longitude", type=float, required=True)

    parser.add_argument("--destination-latitude", type=float, required=True)
    parser.add_argument("--destination-longitude", type=float, required=True)

    parser.add_argument("--max-speed", type=int, default=140)
    parser.add_argument("--destination-wait-seconds", type=float, default=1800)

    parser.add_argument("--acceleration", type=float, default=1.5)
    parser.add_argument("--deceleration", type=float, default=2.5)

    parser.add_argument("--speed-change-seconds", type=float, default=20)
    parser.add_argument("--stop-every-seconds", type=float, default=180)
    parser.add_argument("--stop-seconds", type=float, default=30)

    parser.add_argument("--device-type", choices=("gps", "obd"), default="gps")
    args = parser.parse_args()

    if len(args.imei) != 15 or not args.imei.isascii() or not args.imei.isdigit():
        parser.error("IMEI must contain exactly 15 ASCII digits.")

    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535.")

    if not 1 <= args.max_speed <= 140:
        parser.error("Maximum speed must be between 1 and 140 km/h.")

    for name in (
        "interval",
        "acceleration",
        "deceleration",
        "speed_change_seconds",
        "stop_every_seconds",
        "stop_seconds",
    ):
        value = getattr(args, name)

        if not math.isfinite(value) or value <= 0:
            parser.error(f"{name} must be a positive finite number.")

    if (
        not math.isfinite(args.destination_wait_seconds)
        or args.destination_wait_seconds < 0
    ):
        parser.error("Destination wait must be a non-negative finite number.")

    for name, maximum in (
        ("base_latitude", 90),
        ("base_longitude", 180),
        ("destination_latitude", 90),
        ("destination_longitude", 180),
    ):
        value = getattr(args, name)

        if not math.isfinite(value) or abs(value) > maximum:
            parser.error(f"Invalid coordinate: {name}.")

    return args


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    try:
        run_simulator(parse_args())
    except KeyboardInterrupt:
        logger.info("Simulator stopped.")