"""
Live Tracking Service.

Υπεύθυνο για:

1. Κατανάλωση processed telemetry από Kafka
2. Διατήρηση latest position cache στη Redis
3. Παροχή REST API για ανάκτηση τελευταίας θέσης
"""

import logging
import threading

from fastapi import FastAPI
from fastapi import HTTPException

from kafka_consumer import create_consumer
from redis_repository import RedisRepository

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

app = FastAPI()

redis_repository = RedisRepository()


def kafka_worker():
    # Ο Kafka μπορεί να χρειαστεί λίγα δευτερόλεπτα μέχρι να δεχτεί συνδέσεις.
    # Γι' αυτό δεν αφήνουμε το thread να πεθάνει αν αποτύχει η πρώτη σύνδεση.
    while True:
        try:
            consumer = create_consumer()

            logger.info("Kafka consumer for live tracking started")

            for message in consumer:
                telemetry = message.value

                redis_repository.save_latest_position(telemetry)

        except Exception as error:
            logger.warning(
                "Kafka consumer failed, retrying in 5 seconds. Error: %s",
                error,
            )

            import time
            time.sleep(5)

@app.on_event("startup")
def startup_event():

    worker_thread = threading.Thread(
        target=kafka_worker,
        daemon=True,
    )

    worker_thread.start()

    logger.info(
        "Live Tracking Service started"
    )


@app.get("/latest/{imei}")
def get_latest_position(imei: str):

    position = redis_repository.get_latest_position(
        imei
    )

    if not position:
        raise HTTPException(
            status_code=404,
            detail="Vehicle position not found",
        )

    return position