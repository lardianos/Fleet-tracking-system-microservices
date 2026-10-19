"""
Position Processor Service.

Αυτή η υπηρεσία καταναλώνει telemetry δεδομένα από το Kafka,
αποθηκεύει την τελευταία γνωστή θέση κάθε οχήματος στη Redis
και αποθηκεύει το ιστορικό θέσεων στην TimescaleDB.

Ροή:
Kafka Topic: telemetry.positions
    ↓
Position Processor
    ├── Redis key: vehicle:latest:{imei}
    └── TimescaleDB table: vehicle_positions
"""
import asyncio
import psycopg2
import logging
from contextlib import asynccontextmanager
from threading import Event, Thread

from datetime import datetime

from fastapi import FastAPI, HTTPException, Query

from position_consumer import consume_positions
from db_repository import PositionRepository

logger = logging.getLogger(__name__)

@asynccontextmanager
async def manage_position_processor(app: FastAPI):
    # Ο consumer εκτελείται σε ξεχωριστό thread για να μην μπλοκάρει το API.
    stop_event = Event()
    position_consumer_thread = Thread( target=consume_positions, args=(stop_event,), name="position-consumer", )

    app.state.position_consumer_thread = position_consumer_thread
    position_consumer_thread.start()

    try:
        # Το API εξυπηρετεί αιτήματα όσο ο consumer επεξεργάζεται θέσεις.
        yield
    finally:
        # Ζητάμε τερματισμό και περιμένουμε να κλείσουν οι συνδέσεις του consumer.
        stop_event.set()
        await asyncio.to_thread(position_consumer_thread.join)


app = FastAPI( title="Position Processor", lifespan=manage_position_processor,)


@app.get("/health")
def get_position_processor_health():
    # Αν σταματήσει απρόσμενα ο consumer, δεν αναφέρουμε την υπηρεσία ως υγιή.
    if not app.state.position_consumer_thread.is_alive():
        raise HTTPException( status_code=503, detail="Position consumer is not running.", )

    return {"status": "running", "position_consumer": "running"}


@app.get("/vehicles/{vehicle_id}/positions")
def get_vehicle_position_history(
    vehicle_id: str,
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    limit: int = Query(1000, ge=1, le=1000),
    after_time: datetime | None = Query(None),
    after_imei: str | None = Query(None, min_length=1, max_length=32),
):
    # Απαιτούμε ζώνη ώρας ώστε το χρονικό διάστημα να είναι σαφές.
    if start_time.utcoffset() is None or end_time.utcoffset() is None:
        raise HTTPException(
            status_code=422,
            detail="start_time and end_time must include a timezone.",
        )

    if start_time >= end_time:
        raise HTTPException(
            status_code=422,
            detail="start_time must be earlier than end_time.",
        )

    # Η συνέχεια μιας σελίδας απαιτεί και την ώρα και το IMEI.
    if (after_time is None) != (after_imei is None):
        raise HTTPException(
            status_code=422,
            detail="after_time and after_imei must be provided together.",
        )

    if after_time is not None:
        if after_time.utcoffset() is None:
            raise HTTPException(
                status_code=422,
                detail="after_time must include a timezone.",
            )

        if after_time < start_time or after_time >= end_time:
            raise HTTPException(
                status_code=422,
                detail="after_time must be within the requested time range.",
            )

    position_repository = None

    try:
        # Κάθε αίτημα ανοίγει δική του σύνδεση.
        # Δεν χρησιμοποιούμε τη σύνδεση του Kafka consumer.
        position_repository = PositionRepository()

        return position_repository.get_vehicle_position_history(
            vehicle_id=vehicle_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            after_time=after_time,
            after_imei=after_imei,
        )
    except psycopg2.Error:
        logger.exception("Failed to retrieve position history for vehicle_id=%s", vehicle_id)

        raise HTTPException(
            status_code=503,
            detail="Position history is temporarily unavailable.",
        )
    finally:
        # Κλείνουμε τη σύνδεση είτε ολοκληρωθεί είτε αποτύχει η αναζήτηση.
        if position_repository is not None:
            position_repository.close()