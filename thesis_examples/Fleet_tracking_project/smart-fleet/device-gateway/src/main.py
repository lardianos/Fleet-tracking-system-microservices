# src/main.py
import os
from gateway_server import start_gateway_server


def main():
    host = os.getenv("GATEWAY_HOST", "127.0.0.1")
    port = int(os.getenv("GATEWAY_PORT", "7494"))
    print("[*] Starting Device Gateway microservice...")
    start_gateway_server(host, port)


if __name__ == "__main__":
    main()