"""
API Gateway Service.

Ρόλος:
- Παρέχει ενιαίο REST entrypoint προς τον client/frontend.
- Προωθεί HTTP requests προς τα εσωτερικά REST services.
- Δεν χειρίζεται WebSocket traffic.
- Δεν έχει δική του βάση δεδομένων.
- Δεν μιλάει με Kafka.

Αρχικά προωθεί requests προς:
- Fleet API
- Live Tracking Service
"""

import os
import logging

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="API Gateway Service",
    description="REST Gateway για το Smart Fleet Tracking System.",
    version="0.1.0",
)

# Επιτρέπουμε στο μελλοντικό React frontend να καλεί το API Gateway.
# Προς το παρόν κρατάμε ανοιχτά origins για development.
# Σε production θα μπουν συγκεκριμένα frontend domains.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FLEET_API_URL = os.getenv( "FLEET_API_URL", "http://fleet-api:8000",)

LIVE_TRACKING_SERVICE_URL = os.getenv( "LIVE_TRACKING_SERVICE_URL", "http://live-tracking-service:8002",)


async def proxy_request(request: Request, target_url: str) -> Response:
    """
    Προωθεί ένα HTTP request σε εσωτερικό service.

    Το helper υπάρχει ώστε το API Gateway να μη γράφει ξεχωριστή
    copy-paste λογική για κάθε endpoint.

    Κρατάμε:
    - HTTP method
    - request body
    - query parameters
    - headers, εκτός από το Host
    - status code από το downstream service
    - response content
    - response content-type

    Έτσι το gateway συμπεριφέρεται σαν λεπτό REST entrypoint
    και όχι σαν service που ξαναγράφει τη business λογική.
    """

    request_body = await request.body()

    # Αντιγράφουμε τα headers του αρχικού request.
    # Το Host δεν πρέπει να προωθηθεί, γιατί αφορά το API Gateway
    # και όχι το εσωτερικό service που θα δεχτεί το request.

    # Παίρνουμε τα headers του αρχικού request.
    # Αφαιρούμε το Host γιατί αφορά το gateway και όχι το εσωτερικό service.

    """
    Προωθεί ένα HTTP request σε εσωτερικό REST service.

    Το API Gateway δεν περιέχει business logic.
    Κρατάει method, body, query params και headers,
    ώστε το request να φτάνει όσο πιο καθαρά γίνεται στο σωστό service.
    """

    forwarded_headers = dict(request.headers)
    forwarded_headers.pop("host", None)

    logger.info(
        "Forwarding request method=%s target_url=%s",
        request.method,
        target_url,
    )

    try:
        async with httpx.AsyncClient() as client:
            downstream_response = await client.request(
                method=request.method,
                url=target_url,
                params=request.query_params,
                content=request_body,
                headers=forwarded_headers,
                timeout=10,
            )

    except httpx.RequestError as error:
        logger.warning(
            "Downstream service unavailable target_url=%s error=%s",
            target_url,
            error,
        )

        return Response(
            content='{"detail":"Downstream service unavailable"}',
            status_code=503,
            media_type="application/json",
        )

    # Κρατάμε κυρίως το content-type.
    # Δεν επιστρέφουμε όλα τα headers τυφλά, γιατί κάποια είναι hop-by-hop
    # και αφορούν την εσωτερική HTTP σύνδεση.
    content_type = downstream_response.headers.get("content-type")

    logger.info(
        "Downstream response target_url=%s status_code=%s",
        target_url,
        downstream_response.status_code,
    )

    return Response(
        content=downstream_response.content,
        status_code=downstream_response.status_code,
        media_type=content_type,
    )


@app.get("/health")
async def health_check():
    """
    Health endpoint για το API Gateway.

    Δεν ελέγχει εδώ την υγεία όλων των downstream services.
    Απλώς δείχνει ότι το gateway τρέχει.
    """
    return {
        "status": "ok",
        "service": "api-gateway",
    }


@app.api_route(
    "/api/v1/vehicles/{imei}/latest-position",
    methods=["GET"],
)
async def get_vehicle_latest_position(request: Request, imei: str):
    """
    Προωθεί request για την τελευταία γνωστή θέση οχήματος
    προς το Live Tracking Service.

    Το API Gateway δεν διαβάζει Redis.
    Η Redis ανήκει αποκλειστικά στο Live Tracking Service.
    """
    target_url = (
        f"{LIVE_TRACKING_SERVICE_URL}"
        f"/vehicles/{imei}/latest-position"
    )

    return await proxy_request(request, target_url)


@app.api_route(
    "/api/v1/vehicles",
    methods=["GET", "POST"],
)
async def vehicles_collection(request: Request):
    """
    Προωθεί requests συλλογής οχημάτων προς το Fleet API.

    GET:
    - Επιστρέφει τη λίστα οχημάτων.

    POST:
    - Δημιουργεί νέο όχημα μέσω Fleet API.
    - Το Fleet API παραμένει owner της MongoDB και των vehicle events.
    """
    target_url = f"{FLEET_API_URL}/vehicles"

    return await proxy_request(request, target_url)


@app.api_route(
    "/api/v1/vehicles/{vehicle_id}",
    methods=["GET", "PUT", "PATCH", "DELETE"],
)
async def vehicle_item(request: Request, vehicle_id: str):
    """
    Προωθεί requests συγκεκριμένου οχήματος προς το Fleet API.

    Το route μένει generic ώστε να μπορεί να υποστηρίξει και μελλοντικά
    PUT/PATCH/DELETE όταν προστεθούν στο Fleet API.
    """
    target_url = f"{FLEET_API_URL}/vehicles/{vehicle_id}"

    return await proxy_request(request, target_url)