"""
WebSocket Gateway Service.

Ρόλος:
- Δέχεται WebSocket clients στο /ws
- Διαχειρίζεται subscriptions σε IMEI
- Στέλνει αρχική θέση από Live Tracking Service
- Στέλνει live updates από Kafka processed.positions
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from connection_manager import ConnectionManager
from kafka_consumer import stream_positions_to_clients
from live_tracking_client import LiveTrackingClient

from dashboard_notifications import ( dashboard_notification_endpoint, stream_dashboard_notifications,)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

manager = ConnectionManager()
live_tracking_client = LiveTrackingClient()


@asynccontextmanager
async def websocket_gateway_service(app: FastAPI):
    # Ξεκινάμε ξεχωριστές ροές για τις θέσεις και τις ειδοποιήσεις.
    position_stream_task = asyncio.create_task(
        stream_positions_to_clients(manager)
    )

    notification_stream_task = asyncio.create_task(
        stream_dashboard_notifications()
    )

    logger.info("WebSocket Gateway Service started")

    try:
        yield
    finally:
        position_stream_task.cancel()
        notification_stream_task.cancel()

        await asyncio.gather(
            position_stream_task,
            notification_stream_task,
            return_exceptions=True,
        )

        logger.info("WebSocket Gateway Service stopped")

# Δημιουργούμε την εφαρμογή πριν δηλώσουμε τα endpoints της.
app = FastAPI(
    title="WebSocket Gateway Service",
    description="Service για live θέσεις οχημάτων και ειδοποιήσεις.",
    version="0.1.0",
    lifespan=websocket_gateway_service,
)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "websocket-gateway"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        while True:
            message = await websocket.receive_json()
            action = message.get("action")
            imei = message.get("imei")

            if action == "subscribe":
                if not imei:
                    await websocket.send_json({ "type": "error", "message": "IMEI is required for subscribe action", })
                    continue

                manager.subscribe(websocket, imei)

                latest_position = await live_tracking_client.get_latest_position(imei)

                await websocket.send_json({ "type": "subscribed", "imei": imei, "latest_position": latest_position, })

            elif action == "unsubscribe":
                if not imei:
                    await websocket.send_json({ "type": "error", "message": "IMEI is required for unsubscribe action", })
                    continue

                manager.unsubscribe(websocket, imei)

                await websocket.send_json({ "type": "unsubscribed", "imei": imei, })

            elif action == "subscribe_all":
                # Προς το παρόν δεν το υλοποιούμε πλήρως.
                # Θα το ενεργοποιήσουμε όταν έχουμε auth/roles και λίστα οχημάτων ανά χρήστη.
                await websocket.send_json({ "type": "error", "message": "subscribe_all is not implemented yet", })

            else:
                await websocket.send_json({ "type": "error", "message": "Unknown action", })

    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.websocket("/ws/notifications")
async def notification_websocket_endpoint(websocket: WebSocket):
    await dashboard_notification_endpoint(websocket)