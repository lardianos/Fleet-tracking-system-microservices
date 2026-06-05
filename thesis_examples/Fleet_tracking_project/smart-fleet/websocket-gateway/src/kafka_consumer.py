"""
Async Kafka consumer για live processed positions.

Ακούει το topic processed.positions και στέλνει κάθε νέο position
στους WebSocket clients που έχουν κάνει subscribe στο αντίστοιχο IMEI.
"""

import json
import logging
import os

from aiokafka import AIOKafkaConsumer

from connection_manager import ConnectionManager

logger = logging.getLogger(__name__)


async def create_position_consumer():
    topic = os.getenv(
        "KAFKA_TOPIC_PROCESSED_POSITIONS",
        "processed.positions",
    )

    consumer = AIOKafkaConsumer( topic,
        bootstrap_servers=os.getenv( "KAFKA_BOOTSTRAP_SERVERS", "kafka:9092", ),
        group_id="websocket-gateway-group",
        auto_offset_reset="latest",
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
    )

    await consumer.start()

    logger.info("WebSocket Gateway consuming Kafka topic: %s", topic)

    return consumer


async def stream_positions_to_clients(manager: ConnectionManager):
    while True:
        consumer = None

        try:
            consumer = await create_position_consumer()

            async for message in consumer:
                telemetry = message.value
                imei = telemetry.get("imei")

                if not imei:
                    logger.warning("Received position event without IMEI")
                    continue

                await manager.send_to_subscribers( imei=imei, message={ "type": "position.updated", "data": telemetry, }, )

        except Exception as error:
            logger.warning(
                "WebSocket Kafka consumer failed, retrying in 2 seconds. Error: %s",
                error,
            )

            import asyncio
            await asyncio.sleep(2)

        finally:
            if consumer:
                await consumer.stop()