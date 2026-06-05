"""
Client για επικοινωνία με το Live Tracking Service.

Το WebSocket Gateway δεν διαβάζει απευθείας Redis.
Ζητά την τελευταία θέση μέσω REST API από το Live Tracking Service.
"""

import os
import httpx


class LiveTrackingClient:
    def __init__(self):
        self.base_url = os.getenv(
            "LIVE_TRACKING_SERVICE_URL",
            "http://live-tracking-service:8002",
        )

    async def get_latest_position(self, imei: str) -> dict | None:
        url = f"{self.base_url}/vehicles/{imei}/latest-position"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5)

        if response.status_code == 404:
            return None

        response.raise_for_status()
        return response.json()