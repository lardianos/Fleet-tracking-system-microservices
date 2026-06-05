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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

manager = ConnectionManager()
live_tracking_client = LiveTrackingClient()


@asynccontextmanager
async def websocket_gateway_service(app: FastAPI):
    # Ξεκινάμε background Kafka consumer.
    # Αυτός ακούει processed.positions και στέλνει updates στους subscribers.
    position_stream_task = asyncio.create_task(
        stream_positions_to_clients(manager)
    )

    logger.info("WebSocket Gateway Service started")

    yield

    position_stream_task.cancel()

    try:
        await position_stream_task
    except asyncio.CancelledError:
        logger.info("WebSocket Gateway Service stopped")


app = FastAPI(
    title="WebSocket Gateway Service",
    description="Service για real-time push ενημερώσεις θέσης οχημάτων.",
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