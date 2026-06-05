"""
Live Tracking Service.

Υπεύθυνο για:

1. Κατανάλωση processed telemetry από Kafka
2. Διατήρηση latest position cache στη Redis
3. Παροχή REST API για ανάκτηση τελευταίας θέσης
"""

"""
Live Tracking Service.

Η υπηρεσία αυτή είναι υπεύθυνη για την τελευταία γνωστή θέση κάθε οχήματος.

Ροή:
Kafka topic: processed.positions
    ↓
Live Tracking Service
    ↓
Redis cache

REST API:
GET /vehicles/{imei}/latest-position
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from kafka_consumer import create_consumer
from redis_repository import RedisRepository

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

# Δημιουργούμε repository για Redis.
# Το χρησιμοποιούμε τόσο από τον Kafka consumer όσο και από το REST endpoint.
redis_repository = RedisRepository()


async def position_consumer():
    # Ο Kafka μπορεί να μην είναι έτοιμος όταν ξεκινήσει το service.
    # Γι' αυτό έχουμε retry loop ώστε το service να μη σταματάει.
    while True:
        consumer = None

        try:
            consumer = await create_consumer()

            logger.info("Live Tracking Kafka consumer started")

            # Καταναλώνουμε συνεχώς processed telemetry events.
            # Κάθε event ενημερώνει την τελευταία γνωστή θέση στη Redis.
            async for message in consumer:
                telemetry = message.value

                logger.info(
                    "Received processed position: imei=%s",
                    telemetry.get("imei"),
                )

                redis_repository.save_latest_position(telemetry)

        except Exception as error:
            logger.warning(
                "Kafka consumer failed, retrying in 2 seconds. Error: %s",
                error,
            )

            await asyncio.sleep(2)

        finally:
            # Αν ο consumer είχε ξεκινήσει και μετά έσκασε,
            # τον κλείνουμε καθαρά πριν γίνει νέα προσπάθεια.
            if consumer:
                await consumer.stop()


@asynccontextmanager
async def live_tracking_service(app: FastAPI):
    # Ξεκινάμε τον Kafka consumer ως async background task.
    # Έτσι το FastAPI μπορεί ταυτόχρονα να εξυπηρετεί HTTP requests.
    consumer_task = asyncio.create_task(position_consumer())

    logger.info("Live Tracking Service started")

    yield

    # Όταν σταματήσει το service, ακυρώνουμε το background task.
    consumer_task.cancel()

    try:
        await consumer_task
    except asyncio.CancelledError:
        logger.info("Live Tracking Kafka consumer stopped")


app = FastAPI(
    title="Live Tracking Service",
    description="Service για ανάκτηση τελευταίας γνωστής θέσης οχήματος.",
    version="0.1.0",
    lifespan=live_tracking_service,
)


@app.get("/vehicles/{imei}/latest-position")
async def get_latest_position(imei: str):
    # Το API route παίρνει το IMEI από το URL.
    # Εσωτερικά το service το χρησιμοποιεί για να βρει το Redis key.
    position = redis_repository.get_latest_position(imei)

    if not position:
        raise HTTPException(
            status_code=404,
            detail="Vehicle position not found",
        )

    return position