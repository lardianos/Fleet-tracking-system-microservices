import socket
import struct
import json
import threading
import logging
from typing import Tuple

from codec8_parser import parse_codec8_payload, Codec8ParseError
from kafka_producer import TelemetryProducer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

producer = TelemetryProducer()


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
        logger.info(f"[+] New connection from {addr}")

        # 1) Διαβάζουμε IMEI
        imei_len_bytes = read_exact(conn, 2)
        imei_len = struct.unpack(">H", imei_len_bytes)[0]
        imei_bytes = read_exact(conn, imei_len)
        imei = imei_bytes.decode("ascii", errors="ignore")
        logger.info(f"[<] IMEI: {imei}")

        # 2) Στέλνουμε ACK (0x01)
        conn.sendall(b"\x01")
        logger.info("[>] Sent IMEI ACK (0x01)")

        # 3) Loop για AVL πακέτα
        while True:
            preamble = read_exact(conn, 4)
            if preamble != b"\x00\x00\x00\x00":
                logger.warning(f"[-] Invalid preamble from {addr}: {preamble.hex()}")
                continue

            data_len_bytes = read_exact(conn, 4)
            data_len = struct.unpack(">I", data_len_bytes)[0]

            payload = read_exact(conn, data_len)

            crc_bytes = read_exact(conn, 4)
            logger.info(f"[<] Received AVL payload (len={len(payload)}), CRC={crc_bytes.hex()}")

            try:
                records = parse_codec8_payload(payload, imei)
            except Codec8ParseError as e:
                logger.error(f"[-] Codec8 parse error from {addr}: {e}")
                conn.sendall(struct.pack(">I", 0))
                continue

            for rec in records:
                record_dict = rec.to_dict()

                try:
                    producer.publish_record(record_dict, key=imei)
                    logger.info(f"[AVL->KAFKA] {json.dumps(record_dict, ensure_ascii=False)}")
                except Exception as e:
                    logger.exception(f"[-] Failed to publish record to Kafka: {e}")

            conn.sendall(struct.pack(">I", len(records)))
            logger.info(f"[>] ACK records = {len(records)}")

    except ConnectionError as e:
        logger.warning(f"[-] Connection error with {addr}: {e}")
    except Exception as e:
        logger.exception(f"[-] Unexpected error with {addr}: {e}")
    finally:
        conn.close()
        logger.info(f"[x] Connection closed {addr}")


def start_gateway_server(host: str = "0.0.0.0", port: int = 5000):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(100)
    logger.info(f"[+] Device Gateway listening on {host}:{port}")

    try:
        while True:
            conn, addr = server_sock.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
    finally:
        producer.flush()
        server_sock.close()