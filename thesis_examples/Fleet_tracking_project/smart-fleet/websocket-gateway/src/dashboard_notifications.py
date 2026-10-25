import asyncio
import json
import logging
import os
import time

import jwt

from aiokafka import AIOKafkaConsumer
from fastapi import WebSocket, WebSocketDisconnect
from jwt import PyJWKClient, PyJWTError

logger = logging.getLogger(__name__)

jwks_client = PyJWKClient(
    os.getenv(
        "KEYCLOAK_JWKS_URL",
        "http://keycloak:8080/realms/smart-fleet/protocol/openid-connect/certs",
    )
)

# Κρατάμε μόνο τις ενεργές συνδέσεις και τη λήξη του token τους.
notification_connections: dict[WebSocket, dict] = {}


def validate_notification_token(token: str) -> dict:
    signing_key = jwks_client.get_signing_key_from_jwt(token)

    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=os.getenv(
            "KEYCLOAK_ISSUER_URL",
            "http://localhost:8081/realms/smart-fleet",
        ),
        options={
            "verify_aud": False,
            "require": ["exp", "iss", "sub"],
        },
    )

    # Το frontend client πρέπει να είναι αυτό που εξέδωσε το access token.
    expected_client = os.getenv("KEYCLOAK_CLIENT_ID", "smart-fleet-frontend")

    if payload.get("azp") != expected_client or payload.get("typ") != "Bearer":
        raise ValueError("Invalid access token.")

    if not isinstance(payload["sub"], str) or not payload["sub"]:
        raise ValueError("Missing token subject.")

    return payload


async def dashboard_notification_endpoint(websocket: WebSocket):
    # Επιτρέπουμε συνδέσεις μόνο από το δικό μας frontend.
    expected_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

    if websocket.headers.get("origin") != expected_origin:
        await websocket.close(code=1008)
        return

    await websocket.accept()

    try:
        # Το token έρχεται στο πρώτο μήνυμα, όχι μέσα στο URL.
        message = await asyncio.wait_for(websocket.receive_json(), timeout=10)

        if not isinstance(message, dict) or message.get("action") != "authenticate":
            await websocket.close(code=4401)
            return

        token = message.get("token")

        if not isinstance(token, str) or not token:
            await websocket.close(code=4401)
            return

        payload = await asyncio.to_thread(validate_notification_token, token)

        notification_connections[websocket] = {
            "user_id": payload["sub"],
            "expires_at": payload["exp"],
        }

        await websocket.send_json({"type": "notifications.connected"})

        while True:
            remaining_seconds = payload["exp"] - time.time()

            if remaining_seconds <= 0:
                await websocket.close(code=4401)
                return

            # Κλείνουμε τη σύνδεση όταν λήξει το token.
            await asyncio.wait_for(
                websocket.receive_text(),
                timeout=remaining_seconds,
            )

    except WebSocketDisconnect:
        pass
    except (asyncio.TimeoutError, PyJWTError, ValueError):
        await websocket.close(code=4401)
    except Exception:
        logger.exception("Dashboard notification connection failed.")

        try:
            await websocket.close(code=1011)
        except RuntimeError:
            pass
    finally:
        notification_connections.pop(websocket, None)


async def send_dashboard_notification(websocket: WebSocket, event: dict):
    try:
        await asyncio.wait_for(
            websocket.send_json({
                "type": "notification.created",
                "data": event,
            }),
            timeout=5,
        )
    except Exception:
        # Μια προβληματική σύνδεση δεν σταματά την αποστολή στις υπόλοιπες.
        notification_connections.pop(websocket, None)

        try:
            await websocket.close(code=1011)
        except Exception:
            pass


async def stream_dashboard_notifications():
    # Χωρίς κοινό consumer group, κάθε instance λαμβάνει τα live events
    # και εξυπηρετεί τις δικές του WebSocket συνδέσεις.
    consumer = AIOKafkaConsumer(
        os.getenv(
            "KAFKA_TOPIC_DASHBOARD_NOTIFICATIONS",
            "notifications.dashboard",
        ),
        bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
        group_id=None,
        enable_auto_commit=False,
        auto_offset_reset="latest",
    )

    while True:
        try:
            await consumer.start()

            logger.info("WebSocket Gateway consuming dashboard notifications.")

            async for message in consumer:
                try:
                    event = json.loads(message.value.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    logger.warning("Invalid dashboard notification JSON.")
                    continue

                if not isinstance(event, dict):
                    continue

                if event.get("event_type") != "notification.created":
                    continue

                recipient_user_id = event.get("recipient_user_id")

                if not isinstance(recipient_user_id, str) or not recipient_user_id:
                    continue

                # Ο παραλήπτης συγκρίνεται με το υπογεγραμμένο sub του token.
                # Δεν δεχόμαστε user ID από το frontend.
                connections = [
                    websocket
                    for websocket, connection in list(notification_connections.items())
                    if connection["user_id"] == recipient_user_id
                    and connection["expires_at"] > time.time()
                ]

                if connections:
                    await asyncio.gather(*[
                        send_dashboard_notification(websocket, event)
                        for websocket in connections
                    ])

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Dashboard notification consumer failed. Retrying.")
        finally:
            await consumer.stop()

        await asyncio.sleep(5)

        consumer = AIOKafkaConsumer(
            os.getenv(
                "KAFKA_TOPIC_DASHBOARD_NOTIFICATIONS",
                "notifications.dashboard",
            ),
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
            group_id=None,
            enable_auto_commit=False,
            auto_offset_reset="latest",
        )