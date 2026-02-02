# src/gateway_server.py
import socket
import struct
import json
import threading
from typing import Tuple, List

from codec8_parser import parse_codec8_payload, Codec8ParseError


def read_exact(conn: socket.socket, size: int) -> bytes:
    """Διαβάζει ακριβώς `size` bytes ή πετάει exception αν κλείσει η σύνδεση."""
    buf = b""
    while len(buf) < size:
        chunk = conn.recv(size - len(buf))
        if not chunk:
            raise ConnectionError("Client disconnected")
        buf += chunk
    return buf


def handle_client(conn: socket.socket, addr: Tuple[str, int]):
    try:
        print(f"[+] New connection from {addr}")

        # 1) Διαβάζουμε IMEI
        imei_len_bytes = read_exact(conn, 2)
        imei_len = struct.unpack(">H", imei_len_bytes)[0]
        imei_bytes = read_exact(conn, imei_len)
        imei = imei_bytes.decode("ascii", errors="ignore")
        print(f"[<] IMEI: {imei}")

        # 2) Στέλνουμε ACK (0x01)
        conn.sendall(b"\x01")
        print("[>] Sent IMEI ACK (0x01)")

        # 3) Loop για AVL πακέτα
        while True:
            # Διαβάζουμε preamble (4 bytes)
            preamble = read_exact(conn, 4)
            if preamble != b"\x00\x00\x00\x00":
                print(f"[-] Invalid preamble from {addr}: {preamble.hex()}")
                # μπορείς να αποφασίσεις εδώ αν θα κάνεις continue ή break
                continue

            # Διαβάζουμε data_length (4 bytes)
            data_len_bytes = read_exact(conn, 4)
            data_len = struct.unpack(">I", data_len_bytes)[0]

            # Διαβάζουμε payload (data_len bytes)
            payload = read_exact(conn, data_len)

            # Διαβάζουμε CRC (4 bytes)
            crc_bytes = read_exact(conn, 4)
            # προς το παρόν ΔΕΝ κάνουμε validate CRC, αλλά μπορούμε να το προσθέσουμε

            print(f"[<] Received AVL payload (len={len(payload)}), CRC={crc_bytes.hex()}")

            # Parse Codec8
            try:
                records = parse_codec8_payload(payload, imei)
            except Codec8ParseError as e:
                print(f"[-] Codec8 parse error from {addr}: {e}")
                # απαντάμε ότι 0 records έγιναν accept
                conn.sendall(struct.pack(">I", 0))
                continue

            # Εδώ είναι το “σημείο εξόδου” των δεδομένων:
            for rec in records:
                as_json = json.dumps(rec.to_dict(), ensure_ascii=False)
                # ✨ εδώ αργότερα θα κάνεις publish σε Kafka/RabbitMQ/HTTP κτλ.
                print(f"[AVL] {as_json}")

            # Στέλνουμε αριθμό accepted records (4 bytes, big-endian)
            conn.sendall(struct.pack(">I", len(records)))
            print(f"[>] ACK records = {len(records)}")

    except ConnectionError as e:
        print(f"[-] Connection error with {addr}: {e}")
    finally:
        conn.close()
        print(f"[x] Connection closed {addr}")


def start_gateway_server(host: str = "0.0.0.0", port: int = 5000):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(100)
    print(f"[+] Device Gateway listening on {host}:{port}")

    try:
        while True:
            conn, addr = server_sock.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
    finally:
        server_sock.close()