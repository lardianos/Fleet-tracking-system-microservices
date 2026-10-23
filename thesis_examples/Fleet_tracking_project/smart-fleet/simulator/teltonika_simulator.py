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

def build_codec8_avl_packet(latitude: float, longitude: float, speed_kmh: int = 0,
                            altitude_m: int = 0, angle_deg: int = 0, satellites: int = 0,
                            priority: int = 0) -> bytes:
    """
    Build an AVL packet payload according to Codec 8 structure.
    Returns bytes from CodecID .. NumberOfData2 (CRC is calculated separately).
    We'll produce NumberOfData1 = 1, a single AVL record, with no IO elements (simplest valid packet).
    """

    # Codec ID for Codec 8
    codec_id = b'\x08'
    number_of_data_1 = b'\x01'  # one record

    # Timestamp in milliseconds (8 bytes, big-endian)
    timestamp_ms = int(time.time() * 1000)
    timestamp_bytes = struct.pack(">Q", timestamp_ms)

    # Priority (1 byte)
    priority_byte = struct.pack("B", priority & 0xFF)

    # GPS element
    lon_i = pack_int32_deg7(longitude)
    lat_i = pack_int32_deg7(latitude)
    lon_bytes = struct.pack(">i", lon_i)
    lat_bytes = struct.pack(">i", lat_i)

    altitude_bytes = struct.pack(">h", int(altitude_m) & 0xFFFF)  # 2 bytes
    angle_bytes = struct.pack(">H", int(angle_deg) & 0xFFFF)      # 2 bytes
    satellites_byte = struct.pack("B", satellites & 0xFF)         # 1 byte
    speed_bytes = struct.pack(">H", int(speed_kmh) & 0xFFFF)      # 2 bytes

    gps_part = lon_bytes + lat_bytes + altitude_bytes + angle_bytes + satellites_byte + speed_bytes

    # IO element minimal: Event IO ID (1 byte), N of total ID (1 byte), then N1,N2,N4,N8 (all zero)
    event_io_id = b'\x00'
    n_total_id = b'\x00'
    n1 = b'\x00'
    n2 = b'\x00'
    n4 = b'\x00'
    n8 = b'\x00'

    # Compose AVL Data (single record)
    avl_record = timestamp_bytes + priority_byte + gps_part + event_io_id + n_total_id + n1 + n2 + n4 + n8

    # Number of Data 2 (should equal Number of Data 1)
    number_of_data_2 = number_of_data_1

    payload = codec_id + number_of_data_1 + avl_record + number_of_data_2
    return payload  # CRC not included here

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
                        simulation.advance(now - last_update)

                    last_update = now

                    if pending_packet is None and now >= next_send:
                        pending_position = simulation.snapshot()

                        latitude, longitude, speed, angle, state = pending_position

                        payload = build_codec8_avl_packet(
                            latitude=latitude,
                            longitude=longitude,
                            speed_kmh=speed,
                            altitude_m=80,
                            angle_deg=angle,
                            satellites=10,
                            priority=0,
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