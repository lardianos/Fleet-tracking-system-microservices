#!/usr/bin/env python3
"""
Teltonika Codec 8 TCP simulator (sends IMEI, waits ACK 0x01, then sends Codec8 AVL packet).
Compatible with Teltonika Codec 8 (minimal AVL record, no IO elements or with simple IO).
"""
import socket
import struct
import time
import random
import argparse
from typing import Tuple

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
def run_simulator(server_host: str, server_port: int, imei: str,
                  interval: float = 5.0, jitter: float = 0.1):
    while True:
        try:
            with socket.create_connection((server_host, server_port), timeout=10) as sock:
                print(f"[+] Connected to {server_host}:{server_port}")

                # Send IMEI blob
                imei_blob = build_imei_blob(imei)
                sock.sendall(imei_blob)
                print(f"[>] Sent IMEI: {imei}")

                # Wait for 1-byte ACK
                ack = sock.recv(1)
                if not ack:
                    print("[-] No ACK from server, closing.")
                    return
                if ack == b'\x01':
                    print("[<] Server accepted IMEI (0x01). Sending AVL data...")
                else:
                    print(f"[<] Server rejected IMEI or returned: {ack.hex()}. Exiting.")
                    return

                # Send AVL packets in a loop
                while True:
                    # generate sample GPS (you can modify to read from a track file)
                    lat = random.uniform(37.90, 38.05)     # example around Athens area
                    lon = random.uniform(23.60, 23.85)
                    speed = random.randint(0, 120)
                    alt = random.randint(0, 300)
                    angle = random.randint(0, 359)
                    sats = random.randint(3, 12)
                    priority = 0x00

                    codec_payload = build_codec8_avl_packet(latitude=lat, longitude=lon,
                                                            speed_kmh=speed, altitude_m=alt,
                                                            angle_deg=angle, satellites=sats,
                                                            priority=priority)
                    tcp_packet = build_full_tcp_packet(codec_payload)

                    sock.sendall(tcp_packet)
                    print(f"[>] Sent AVL packet (len {len(tcp_packet)} bytes) lat={lat:.6f}, lon={lon:.6f}, speed={speed}")

                    # After sending AVL packet, the server should reply with 4-byte accepted records integer.
                    # Some servers send 4-bytes. We'll attempt to read up to 4 bytes (blocking read).
                    try:
                        resp = sock.recv(4)
                        if resp:
                            print(f"[<] Server response (raw): {resp.hex()}")
                        else:
                            print("[-] No server response after AVL packet (connection might be closed).")
                            break
                    except socket.timeout:
                        print("[-] No response within timeout after AVL packet.")
                        break

                    time.sleep(interval + random.uniform(-jitter, jitter))

        except (ConnectionRefusedError, OSError) as e:
            print(f"[-] Connection error: {e}. Retrying in 5s...")
            time.sleep(5.0)

# -------------------------
# CLI
# -------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Teltonika Codec8 TCP simulator")
    p.add_argument("--host", "-H", default="127.0.0.1", help="Server host")
    p.add_argument("--port", "-P", type=int, default=7494, help="Server port")
    p.add_argument("--imei", "-i", default="123456789012345", help="IMEI (15 digits)")
    p.add_argument("--interval", "-t", type=float, default=5.0, help="Seconds between AVL packets")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    run_simulator(args.host, args.port, args.imei, interval=args.interval)