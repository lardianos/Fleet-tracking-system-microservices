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
import jwt

from keycloak_admin_client import KeycloakAdminClient
from admin_driver import AdminDriverCreate, AdminDriverUpdate
from admin_fleet_manager import AdminFleetManagerCreate, AdminFleetManagerUpdate
from admin_vehicle import VehicleCreateRequest, VehicleUpdateRequest
from admin_fleet import FleetCreateRequest, FleetUpdateRequest

from fastapi import FastAPI, Request, Response, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from jwt import PyJWKClient, PyJWTError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Body
from pydantic import BaseModel, ConfigDict, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KEYCLOAK_ISSUER_URL = os.getenv( "KEYCLOAK_ISSUER_URL", "http://localhost:8081/realms/smart-fleet", )

KEYCLOAK_JWKS_URL = os.getenv( "KEYCLOAK_JWKS_URL", "http://keycloak:8080/realms/smart-fleet/protocol/openid-connect/certs",)

KEYCLOAK_CLIENT_ID = os.getenv( "KEYCLOAK_CLIENT_ID", "smart-fleet-frontend", )

# Ρυθμίσεις για machine-to-machine επικοινωνία του API Gateway
# με το Keycloak Admin API.
#
# Αυτές οι ρυθμίσεις είναι διαφορετικές από το KEYCLOAK_CLIENT_ID
# του frontend. Εδώ χρησιμοποιούμε confidential client με service account.

KEYCLOAK_ADMIN_URL = os.getenv( "KEYCLOAK_ADMIN_URL", "http://keycloak:8080",)

KEYCLOAK_ADMIN_REALM = os.getenv( "KEYCLOAK_ADMIN_REALM", "smart-fleet", )

KEYCLOAK_ADMIN_CLIENT_ID = os.getenv( "KEYCLOAK_ADMIN_CLIENT_ID", "smart-fleet-api-gateway",)

KEYCLOAK_ADMIN_CLIENT_SECRET = os.getenv("KEYCLOAK_ADMIN_CLIENT_SECRET", )


if not KEYCLOAK_ADMIN_CLIENT_SECRET:
    raise RuntimeError( "KEYCLOAK_ADMIN_CLIENT_SECRET is not configured" )

# Δημιουργούμε έναν κοινό Keycloak Admin client για τις administrative
# identity operations του API Gateway.
#
# Το instance δεν κρατά service-account access token ως μόνιμο state.
# Κάθε administrative operation ζητά token όταν το χρειάζεται.
keycloak_admin_client = KeycloakAdminClient(
    keycloak_url=KEYCLOAK_ADMIN_URL,
    realm=KEYCLOAK_ADMIN_REALM,
    client_id=KEYCLOAK_ADMIN_CLIENT_ID,
    client_secret=KEYCLOAK_ADMIN_CLIENT_SECRET,
)

jwks_client = PyJWKClient(KEYCLOAK_JWKS_URL)

VEHICLE_MANAGEMENT_ROLES = [ "admin", "fleet_manager", ]

LIVE_TRACKING_ROLES = [ "admin", "fleet_manager", "driver", ]

# Οι ενέργειες δημιουργίας και διαγραφής λογαριασμών
# επιτρέπονται αποκλειστικά στον διαχειριστή.
ADMIN_ROLES = ["admin"]

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

# Δηλώνουμε στο Swagger ότι τα προστατευμένα endpoints
# χρησιμοποιούν Bearer JWT για την αυθεντικοποίηση.
bearer_scheme = HTTPBearer(auto_error=False)

# -------------------------
# Helper Functions
# -------------------------

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

    return Response( content=downstream_response.content, status_code=downstream_response.status_code, media_type=content_type, )

# def validate_access_token(request: Request):
async def validate_access_token( request: Request, _credentials=Depends(bearer_scheme), ):
    """
    Ελέγχει αν το request έχει έγκυρο Keycloak JWT.

    Το API Gateway είναι το πρώτο security boundary.
    Τα εσωτερικά services συνεχίζουν να μένουν απλά και δεν γνωρίζουν Keycloak.
    """

    authorization_header = request.headers.get("authorization")

    if not authorization_header:
        raise HTTPException( status_code=401, detail="Missing Authorization header", )

    if not authorization_header.startswith("Bearer "):
        raise HTTPException( status_code=401, detail="Invalid Authorization header", )

    token = authorization_header.replace("Bearer ", "", 1)

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        payload = jwt.decode( token, signing_key.key,
                              algorithms=["RS256"], issuer=KEYCLOAK_ISSUER_URL, options={ "verify_aud": False, }, )

        # logger.info("========= Decoded JWT payload %s ============\n",payload)

        if payload.get("azp") != KEYCLOAK_CLIENT_ID:
            raise HTTPException( status_code=401, detail="Invalid token client", )


        # Για τους χρήστες με ρόλο driver ελέγχουμε
        # αν ο λογαριασμός παραμένει ενεργός στο Keycloak.
        user_roles = payload.get( "realm_access", {} ).get("roles", [])

        if "driver" in user_roles:
            keycloak_user_id = payload.get("sub")

            if not keycloak_user_id:
                raise HTTPException( status_code=401, detail="Token does not contain user identifier", )

            try:
                keycloak_user = ( await keycloak_admin_client.get_user_by_id( keycloak_user_id ) )
            except Exception:
                logger.exception(
                    "Could not verify Driver account state: "
                    "keycloak_user_id=%s",
                    keycloak_user_id,
                )
                raise HTTPException( status_code=503, detail="Could not verify Driver account state", )

            # Απορρίπτουμε το JWT ακόμη και αν δεν έχει λήξει,
            # όταν ο λογαριασμός δεν υπάρχει ή είναι ανενεργός.
            if ( keycloak_user is None or keycloak_user.get("enabled") is not True ):
                raise HTTPException( status_code=401, detail="Driver account is disabled", )

        # Για τους χρήστες με ρόλο fleet_manager ελέγχουμε
        # αν ο λογαριασμός παραμένει ενεργός στο Keycloak.
        elif "fleet_manager" in user_roles:
            keycloak_user_id = payload.get("sub")

            if not keycloak_user_id:
                raise HTTPException( status_code=401, detail="Token does not contain user identifier", )

            try:
                keycloak_user = ( await keycloak_admin_client.get_user_by_id( keycloak_user_id ) )

            except Exception:
                logger.exception(
                    "Could not verify Fleet Manager account state: "
                    "keycloak_user_id=%s",
                    keycloak_user_id,
                )

                raise HTTPException( status_code=503, detail="Could not verify Fleet Manager account state", )

            # Απορρίπτουμε το JWT ακόμη και αν δεν έχει λήξει,
            # όταν ο Fleet Manager δεν υπάρχει ή είναι ανενεργός.
            if ( keycloak_user is None or keycloak_user.get("enabled") is not True ):
                raise HTTPException( status_code=401, detail="Fleet Manager account is disabled", )

        logger.info(
            "Authenticated user=%s roles=%s",
            payload.get("preferred_username"),
            payload.get("realm_access", {}).get("roles", []),
        )


        return payload

    except PyJWTError:
        raise HTTPException( status_code=401, detail="Invalid or expired token", )

def role_checker(token_payload: dict, allowed_roles: list[str]):
    """
    Ελέγχει αν ο authenticated χρήστης έχει έναν από τους επιτρεπόμενους ρόλους.

    Τα roles έρχονται από το Keycloak JWT μέσα στο realm_access.roles.
    Η συνάρτηση είναι ξεχωριστή για να μένει απλή και ευανάγνωστη η authorization λογική.
    """

    user_roles = token_payload.get("realm_access", {}).get("roles", [])

    has_allowed_role = False

    for role in allowed_roles:
        if role in user_roles:
            has_allowed_role = True
            break

    if not has_allowed_role:
        raise HTTPException(
            status_code=403,
            detail="Access denied",
        )

    logger.info(
        "Authorized user=%s roles=%s allowed_roles=%s",
        token_payload.get("preferred_username"),
        user_roles,
        allowed_roles,
    )

# def require_roles(*allowed_roles: str):
#     """
#     Δημιουργεί dependency που επιτρέπει πρόσβαση μόνο σε συγκεκριμένους ρόλους.
#
#     Τα roles έρχονται από το Keycloak JWT μέσα στο realm_access.roles.
#     Έτσι το API Gateway μπορεί να εφαρμόζει authorization πριν προωθήσει
#     το request στα εσωτερικά services.
#     """
#
#     def role_checker(token_payload: dict = Depends(validate_access_token)):
#         user_roles = token_payload.get("realm_access", {}).get("roles", [])
#
#         has_allowed_role = any(
#             role in user_roles
#             for role in allowed_roles
#         )
#
#         if not has_allowed_role:
#             raise HTTPException(
#                 status_code=403,
#                 detail="Access denied",
#             )
#
#         logger.info(
#             "Authorized user=%s roles=%s allowed_roles=%s",
#             token_payload.get("preferred_username"),
#             user_roles,
#             allowed_roles,
#         )
#
#         return token_payload
#
#     return role_checker

async def check_driver_update_state( driver_id: str, expected_data: dict,) -> bool | None:
    """
    Ελέγχει αν το Fleet API έχει αποθηκεύσει
    όλες τις τιμές που ζητήθηκαν.

    True: οι αλλαγές έχουν αποθηκευτεί.
    False: υπάρχουν διαφορετικές τιμές.
    None: δεν μπορέσαμε να επιβεβαιώσουμε την κατάσταση.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{FLEET_API_URL}/drivers"
            )

        if response.status_code != 200:
            return None

        driver = next(
            (
                item
                for item in response.json()
                if item.get("driver_id") == driver_id
            ),
            None,
        )

        if driver is None:
            return None

        return all(
            driver.get(field) == value
            for field, value in expected_data.items()
        )

    except (httpx.RequestError, ValueError):
        logger.exception(
            "Could not verify Driver update: driver_id=%s",
            driver_id,
        )
        return None

async def check_driver_status( driver_id: str, expected_status: str, ) -> bool | None:
    """
    Ελέγχει αν το Driver Profile βρίσκεται στο αναμενόμενο status.

    True:
    - ο Driver υπάρχει και έχει το αναμενόμενο status.

    False:
    - ο Driver υπάρχει αλλά έχει διαφορετικό status.

    None:
    - δεν μπορέσαμε να επιβεβαιώσουμε την κατάσταση.
    """

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{FLEET_API_URL}/drivers"
            )

        if response.status_code != 200:
            return None

        driver = next(
            (
                item
                for item in response.json()
                if item.get("driver_id") == driver_id
            ),
            None,
        )

        if driver is None:
            return None

        return driver.get("status") == expected_status

    except (httpx.RequestError, ValueError):
        logger.exception(
            "Could not verify Driver status: "
            "driver_id=%s expected_status=%s",
            driver_id,
            expected_status,
        )
        return None

async def check_driver_state( driver_id: str,) -> bool | None:
    """
    Επιβεβαιώνει ότι ο οδηγός είναι ανενεργός
    και δεν έχει πλέον ανατεθειμένα οχήματα.

    True: η απενεργοποίηση ολοκληρώθηκε.
    False: η κατάσταση δεν είναι η αναμενόμενη.
    None: δεν ήταν δυνατή η επιβεβαίωση.
    """

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            drivers_response = await client.get(
                f"{FLEET_API_URL}/drivers"
            )

            vehicles_response = await client.get(
                f"{FLEET_API_URL}/drivers/{driver_id}/vehicles"
            )

        if (
            drivers_response.status_code != 200
            or vehicles_response.status_code != 200
        ):
            return None

        driver = next(
            (
                item
                for item in drivers_response.json()
                if item.get("driver_id") == driver_id
            ),
            None,
        )

        if driver is None:
            return None

        # Δεν αρκεί να είναι INACTIVE.
        # Πρέπει να έχουν αφαιρεθεί και οι αναθέσεις οχημάτων.
        return (
            driver.get("status") == "INACTIVE"
            and len(vehicles_response.json()) == 0
        )

    except (httpx.RequestError, ValueError):
        logger.exception(
            "Could not verify Driver deactivation: driver_id=%s",
            driver_id,
        )
        return None

async def check_driver_deleted_from_fleet( driver_id: str, ) -> bool | None:
    """
    Ελέγχει αν το Driver Profile έχει διαγραφεί από το Fleet API.

    True:
    - ο Driver δεν υπάρχει πλέον.

    False:
    - ο Driver εξακολουθεί να υπάρχει.

    None:
    - δεν μπορέσαμε να επιβεβαιώσουμε την κατάσταση του Fleet API.

    Ο helper χρησιμοποιείται κυρίως μετά από timeout στο Hard Delete,
    ώστε να μη θεωρήσουμε αποτυχία ένα DELETE που μπορεί να ολοκληρώθηκε.
    """

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{FLEET_API_URL}/drivers"
            )

        if response.status_code != 200:
            return None

        driver = next(
            (
                item
                for item in response.json()
                if item.get("driver_id") == driver_id
            ),
            None,
        )

        # Αν δεν υπάρχει πλέον στη λίστα, το Profile έχει διαγραφεί.
        return driver is None

    except (httpx.RequestError, ValueError):
        logger.exception(
            "Could not verify Driver deletion from Fleet API: "
            "driver_id=%s",
            driver_id,
        )
        return None

async def get_deleted_driver_keycloak_user_id( driver_id: str, ) -> str | None:
    """
    Ανακτά το Keycloak user ID ενός Driver που έχει ήδη διαγραφεί
    από το Fleet API.

    Μετά από Hard Delete το Driver Profile δεν υπάρχει πλέον,
    επομένως χρησιμοποιούμε το μόνιμο DELETED audit event για
    recovery σε περίπτωση retry ή μερικής αποτυχίας.

    Επιστρέφει:
    - το keycloak_user_id όταν υπάρχει έγκυρο DELETED audit,
    - None όταν δεν μπορεί να βρεθεί ή να επιβεβαιωθεί.
    """

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get( f"{FLEET_API_URL}/audit-logs/DRIVER/{driver_id}" )

        if response.status_code != 200:
            return None

        audit_logs = response.json()

        # Αναζητούμε το πιο πρόσφατο DELETED event.
        # Το Fleet API επιστρέφει ήδη τα audit events
        # ταξινομημένα από το νεότερο προς το παλαιότερο.
        ######
        deleted_audit = next( ( audit_log for audit_log in audit_logs if audit_log.get("action") == "DELETED"), None, )

        if deleted_audit is None:
            return None

        keycloak_change = (
            deleted_audit
            .get("changes", {})
            .get("keycloak_user_id")
        )

        if not isinstance(keycloak_change, dict):
            return None

        keycloak_user_id = keycloak_change.get("from_value")

        if ( not isinstance(keycloak_user_id, str) or not keycloak_user_id.strip() ):
            return None

        return keycloak_user_id

    except (httpx.RequestError, ValueError):
        logger.exception(
            "Could not recover Keycloak user ID from Driver audit: "
            "driver_id=%s",
            driver_id,
        )
        return None

async def check_fleet_manager_status( manager_id: str, expected_status: str, ) -> bool | None:
    """
    Ελέγχει αν το Fleet Manager Profile βρίσκεται
    στο αναμενόμενο lifecycle status.

    True:
    - ο Fleet Manager υπάρχει και έχει το αναμενόμενο status.

    False:
    - ο Fleet Manager υπάρχει αλλά έχει διαφορετικό status.

    None:
    - δεν μπορέσαμε να επιβεβαιώσουμε την κατάσταση.
    """

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{FLEET_API_URL}/fleet-managers"
            )

        if response.status_code != 200:
            return None

        fleet_manager = next(
            (
                item
                for item in response.json()
                if item.get("manager_id") == manager_id
            ),
            None,
        )

        if fleet_manager is None:
            return None

        return fleet_manager.get("status") == expected_status

    except (httpx.RequestError, ValueError):
        logger.exception(
            "Could not verify Fleet Manager status: "
            "manager_id=%s expected_status=%s",
            manager_id,
            expected_status,
        )
        return None

async def check_fleet_manager_update_state( manager_id: str, expected_data: dict,) -> bool | None:
    """
    Ελέγχει αν το Fleet API έχει αποθηκεύσει όλες τις
    αλλαγές που ζητήθηκαν για έναν Fleet Manager.

    True:
    - όλες οι αναμενόμενες τιμές έχουν αποθηκευτεί.

    False:
    - ο Fleet Manager υπάρχει, αλλά τουλάχιστον μία
      τιμή διαφέρει από την αναμενόμενη.

    None:
    - δεν μπορέσαμε να επιβεβαιώσουμε την κατάσταση.
    """

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{FLEET_API_URL}/fleet-managers"
            )

        if response.status_code != 200:
            return None

        fleet_manager = next(
            (
                item
                for item in response.json()
                if item.get("manager_id") == manager_id
            ),
            None,
        )

        if fleet_manager is None:
            return None

        return all(
            fleet_manager.get(field) == value
            for field, value in expected_data.items()
        )

    except (httpx.RequestError, ValueError):
        logger.exception(
            "Could not verify Fleet Manager update state: "
            "manager_id=%s",
            manager_id,
        )

        return None

async def check_fleet_manager_deleted_from_fleet( manager_id: str,) -> bool | None:
    """
    Ελέγχει αν το Fleet Manager Profile έχει διαγραφεί
    από το Fleet API.

    True:
    - ο Fleet Manager δεν υπάρχει πλέον.

    False:
    - ο Fleet Manager εξακολουθεί να υπάρχει.

    None:
    - δεν μπορέσαμε να επιβεβαιώσουμε την κατάσταση
      του Fleet API.

    Ο helper χρησιμοποιείται κυρίως μετά από timeout
    στο Hard Delete, ώστε να μη θεωρήσουμε αποτυχία
    ένα DELETE που μπορεί να ολοκληρώθηκε.
    """

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{FLEET_API_URL}/fleet-managers"
            )

        if response.status_code != 200:
            return None

        fleet_manager = next(
            (
                item
                for item in response.json()
                if item.get("manager_id") == manager_id
            ),
            None,
        )

        # Αν δεν υπάρχει πλέον στη λίστα,
        # το Fleet Manager Profile έχει διαγραφεί.
        return fleet_manager is None

    except (httpx.RequestError, ValueError):
        logger.exception(
            "Could not verify Fleet Manager deletion from Fleet API: "
            "manager_id=%s",
            manager_id,
        )

        return None

async def get_deleted_fleet_manager_keycloak_user_id( manager_id: str,) -> str | None:
    """
    Ανακτά το Keycloak user ID ενός Fleet Manager που έχει ήδη
    διαγραφεί από το Fleet API.

    Μετά από Hard Delete το Fleet Manager Profile δεν υπάρχει πλέον,
    επομένως χρησιμοποιούμε το μόνιμο DELETED audit event για
    recovery σε περίπτωση retry ή μερικής αποτυχίας.

    Επιστρέφει:
    - το keycloak_user_id όταν υπάρχει έγκυρο DELETED audit,
    - None όταν δεν μπορεί να βρεθεί ή να επιβεβαιωθεί.
    """

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{FLEET_API_URL}/audit-logs/FLEET_MANAGER/{manager_id}"
            )

        if response.status_code != 200:
            return None

        audit_logs = response.json()

        # Αναζητούμε το πιο πρόσφατο DELETED event.
        # Το Fleet API επιστρέφει τα audit events
        # ταξινομημένα από το νεότερο προς το παλαιότερο.
        deleted_audit = next(
            (
                audit_log
                for audit_log in audit_logs
                if audit_log.get("action") == "DELETED"
            ),
            None,
        )

        if deleted_audit is None:
            return None

        keycloak_change = (
            deleted_audit
            .get("changes", {})
            .get("keycloak_user_id")
        )

        if not isinstance(keycloak_change, dict):
            return None

        keycloak_user_id = keycloak_change.get("from_value")

        if (
            not isinstance(keycloak_user_id, str)
            or not keycloak_user_id.strip()
        ):
            return None

        return keycloak_user_id

    except (httpx.RequestError, ValueError):
        logger.exception(
            "Could not recover Keycloak user ID from "
            "Fleet Manager audit: manager_id=%s",
            manager_id,
        )

        return None

async def get_authenticated_fleet_manager_fleet_id( token_payload: dict,) -> str:
    """
    Επιστρέφει το fleet_id του authenticated Fleet Manager.

    Το fleet_id δεν λαμβάνεται ποτέ από τον client.
    Χρησιμοποιούμε το Keycloak user id από το validated JWT
    και ζητάμε το αντίστοιχο Fleet Manager Profile από το Fleet API.
    """

    keycloak_user_id = token_payload.get("sub")

    if not keycloak_user_id:
        raise HTTPException( status_code=401, detail="Token does not contain user identifier", )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get( f"{FLEET_API_URL}/fleet-managers/by-keycloak-user/{keycloak_user_id}"
            )
    except httpx.RequestError:
        logger.exception(
            "Could not retrieve Fleet Manager Profile: "
            "keycloak_user_id=%s",
            keycloak_user_id,
        )
        raise HTTPException( status_code=503, detail="Fleet API unavailable", )

    if response.status_code == 404:
        raise HTTPException( status_code=403, detail="Fleet Manager Profile not found", )

    if response.status_code != 200:
        raise HTTPException( status_code=503, detail="Could not retrieve Fleet Manager Profile", )

    fleet_manager = response.json()
    fleet_id = fleet_manager.get("fleet_id")

    if not fleet_id:
        raise HTTPException( status_code=409, detail="Fleet Manager is not assigned to a fleet", )

    return fleet_id
# -------------------------
# API Endpoints
# -------------------------

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

@app.get("/health/keycloak-admin")
async def keycloak_admin_health_check():
    """
    Ελέγχει ότι το API Gateway μπορεί να αυθεντικοποιηθεί
    στο Keycloak μέσω του service account.

    Το endpoint χρησιμοποιείται προσωρινά κατά την ανάπτυξη
    και δεν επιστρέφει ποτέ το πραγματικό access token.
    """

    try:
        await keycloak_admin_client.get_access_token()

    except Exception as error:
        logger.error(
            "Keycloak Admin authentication check failed: error=%s",
            error,
        )

        raise HTTPException(
            status_code=503,
            detail="Keycloak Admin authentication failed",
        )

    return {
        "status": "ok",
        "service": "api-gateway",
        "keycloak_admin": "authenticated",
    }

@app.post("/development/keycloak-admin/test-user")
async def test_keycloak_admin_user_lifecycle():
    """
    Ελέγχει προσωρινά το πλήρες lifecycle ενός Keycloak user.

    Το endpoint υπάρχει μόνο για development testing και θα αφαιρεθεί
    όταν επιβεβαιώσουμε ότι το Keycloak Admin integration λειτουργεί.

    Η δοκιμή:
    1. δημιουργεί προσωρινό Keycloak user,
    2. του αναθέτει το realm role "driver",
    3. διαγράφει τον ίδιο προσωρινό user.

    Δεν δημιουργεί Driver Profile στο Fleet API ή στη MongoDB.
    """

    test_username = "keycloak-admin-test-user"
    test_email = "keycloak-admin-test@example.com"
    test_password = "Temporary-Test-Password-123!"

    keycloak_user_id = None

    try:
        # Δημιουργούμε προσωρινό identity αποκλειστικά για να ελέγξουμε
        # ότι το service account έχει δικαίωμα δημιουργίας χρηστών.
        keycloak_user_id = await keycloak_admin_client.create_user(
            username=test_username,
            email=test_email,
            first_name="Keycloak",
            last_name="Test",
            temporary_password=test_password,
        )

        # Ελέγχουμε ότι το service account μπορεί να αναθέσει
        # το υπάρχον realm role "driver" στον νέο χρήστη.
        await keycloak_admin_client.assign_realm_role(
            keycloak_user_id=keycloak_user_id,
            role_name="driver",
        )

        # Αφού ολοκληρώθηκαν επιτυχώς τα προηγούμενα βήματα,
        # διαγράφουμε τον προσωρινό χρήστη ώστε να μη μείνει
        # test identity μέσα στο Keycloak.
        await keycloak_admin_client.delete_user(
            keycloak_user_id=keycloak_user_id,
        )

        keycloak_user_id = None

        return {
            "status": "ok",
            "create_user": "passed",
            "assign_role": "passed",
            "delete_user": "passed",
        }

    # except Exception as error:
    #     logger.error(
    #         "Keycloak Admin user lifecycle test failed: error=%s",
    #         error,
    #     )
    except Exception:
        logger.exception( "Keycloak Admin user lifecycle test failed" )

        # Αν ο user δημιουργήθηκε αλλά κάποιο επόμενο βήμα απέτυχε,
        # προσπαθούμε να τον διαγράψουμε ως compensating action.
        #
        # Αυτό είναι ταυτόχρονα μια μικρή δοκιμή της λογικής που
        # αργότερα θα χρησιμοποιήσουμε στο πραγματικό orchestration.
        if keycloak_user_id is not None:
            try:
                await keycloak_admin_client.delete_user(
                    keycloak_user_id=keycloak_user_id,
                )

            except Exception as cleanup_error:
                logger.error(
                    "Could not clean up temporary Keycloak user: "
                    "keycloak_user_id=%s error=%s",
                    keycloak_user_id,
                    cleanup_error,
                )

        raise HTTPException(
            status_code=500,
            detail="Keycloak Admin user lifecycle test failed",
        )

@app.get("/api/v1/admin/drivers")
async def admin_get_all_drivers( request: Request, token_payload: dict = Depends(validate_access_token),):
    """
    Επιτρέπει μόνο στον Admin να δει όλα τα Driver Profiles.

    Το Gateway ελέγχει τα δικαιώματα και προωθεί
    το αίτημα στο Fleet API χωρίς πρόσβαση στη MongoDB.
    """

    role_checker(token_payload, ADMIN_ROLES)

    target_url = f"{FLEET_API_URL}/drivers"

    return await proxy_request(request, target_url)

@app.post("/api/v1/admin/drivers", status_code=201)
async def admin_create_driver( driver: AdminDriverCreate, token_payload: dict = Depends(validate_access_token),):
    """
    Δημιουργεί Keycloak identity και Driver Profile.

    Μόνο ο Admin μπορεί να εκτελέσει αυτή τη λειτουργία.
    Το Fleet API παραμένει υπεύθυνο για τα business δεδομένα.
    """

    role_checker(token_payload, ADMIN_ROLES)

    # Ελέγχουμε πρώτα αν υπάρχει ήδη το username.
    # Δεν δημιουργούμε δεύτερο λογαριασμό με το ίδιο όνομα.
    try:
        existing_user = (
            await keycloak_admin_client.get_user_by_username(
                driver.username
            )
        )
    except (httpx.RequestError, httpx.HTTPStatusError):
        logger.exception("Could not check Keycloak username")
        raise HTTPException(
            status_code=503,
            detail="Could not verify Keycloak username",
        )

    if existing_user is not None:
        raise HTTPException(
            status_code=409,
            detail="Keycloak username already exists",
        )

    # Δημιουργούμε τον χρήστη χωρίς προκαθορισμένο password.
    # Το Keycloak θα απαιτήσει να ορίσει δικό του κωδικό.
    try:
        keycloak_user_id = await keycloak_admin_client.create_user(
            username=driver.username,
            email=str(driver.email),
            first_name=driver.first_name,
            last_name=driver.last_name,
        )
    except httpx.RequestError:
        # Ένα timeout μπορεί να συμβεί αφού το Keycloak
        # έχει ήδη δημιουργήσει τον χρήστη.
        # Δεν επαναλαμβάνουμε αυτόματα τη δημιουργία.
        logger.exception(
            "Uncertain Keycloak user creation: username=%s",
            driver.username,
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Keycloak creation outcome is uncertain. "
                "Check the user before retrying."
            ),
        )
    except Exception:
        logger.exception(
            "Keycloak user creation failed: username=%s",
            driver.username,
        )
        raise HTTPException(
            status_code=502,
            detail="Could not create Keycloak user",
        )

    # Από αυτό το σημείο γνωρίζουμε το ID του νέου χρήστη.
    # Αν αποτύχει η ανάθεση ρόλου, επιχειρούμε αντιστάθμιση.
    try:
        await keycloak_admin_client.assign_realm_role(
            keycloak_user_id=keycloak_user_id,
            role_name="driver",
        )
    except Exception:
        logger.exception(
            "Could not assign driver role: keycloak_user_id=%s",
            keycloak_user_id,
        )

        try:
            await keycloak_admin_client.delete_user(
                keycloak_user_id
            )
        except Exception:
            logger.exception(
                "Manual cleanup required: keycloak_user_id=%s",
                keycloak_user_id,
            )
            raise HTTPException(
                status_code=503,
                detail=(
                    "Role assignment failed and automatic "
                    "cleanup could not be confirmed"
                ),
            )

        raise HTTPException(
            status_code=502,
            detail="Could not assign driver role",
        )

    # Το username αφορά αποκλειστικά το Keycloak.
    # Το Fleet API λαμβάνει μόνο τα business στοιχεία
    # και το Keycloak ID που δημιούργησε το Gateway.
    driver_data = driver.model_dump(
        mode="json",
        exclude={"username"},
    )
    driver_data["keycloak_user_id"] = keycloak_user_id

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            fleet_response = await client.post(
                f"{FLEET_API_URL}/drivers",
                json=driver_data,
            )
        except httpx.RequestError:
            # Δεν γνωρίζουμε αν το Fleet API πρόλαβε
            # να αποθηκεύσει το Driver Profile.
            logger.exception(
                "Uncertain Driver Profile creation: "
                "keycloak_user_id=%s",
                keycloak_user_id,
            )

            try:
                profile_response = await client.get(
                    f"{FLEET_API_URL}/drivers/"
                    f"by-keycloak-user/{keycloak_user_id}"
                )
            except httpx.RequestError:
                logger.exception(
                    "Could not reconcile Driver Profile: "
                    "keycloak_user_id=%s",
                    keycloak_user_id,
                )
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Driver creation outcome is uncertain. "
                        "Manual reconciliation is required."
                    ),
                )

            if profile_response.status_code == 200:
                # Το Profile δημιουργήθηκε παρά το timeout.
                return profile_response.json()

            if profile_response.status_code != 404:
                raise HTTPException(
                    status_code=503,
                    detail="Could not reconcile Driver Profile",
                )

            # Το 404 αμέσως μετά το timeout δεν αποδεικνύει
            # ότι το αρχικό request δεν εκτελείται ακόμη.
            # Διατηρούμε τον χρήστη για ασφαλή επανέλεγχο.
            raise HTTPException(
                status_code=503,
                detail=(
                    "Driver Profile not found after timeout. "
                    "Reconciliation is required before retrying."
                ),
            )

    if fleet_response.status_code == 200:
        logger.info(
            "Created Driver: driver_id=%s keycloak_user_id=%s",
            driver.driver_id,
            keycloak_user_id,
        )
        return fleet_response.json()

    # Εδώ έχουμε λάβει ρητή αποτυχία από το Fleet API.
    # Ελέγχουμε και την περίπτωση σύγκρουσης προτού
    # διαγράψουμε τον νέο χρήστη.
    if fleet_response.status_code >= 500:
        raise HTTPException(
            status_code=503,
            detail=(
                "Fleet API failed. "
                "Reconciliation is required before cleanup."
            ),
        )

    try:
        await keycloak_admin_client.delete_user(
            keycloak_user_id
        )
    except Exception:
        logger.exception(
            "Could not compensate failed Driver creation: "
            "keycloak_user_id=%s",
            keycloak_user_id,
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Driver Profile was rejected, but Keycloak "
                "user cleanup could not be confirmed"
            ),
        )

    # Επιστρέφουμε το σφάλμα validation ή conflict
    # που παρήγαγε το Fleet API.
    raise HTTPException(
        status_code=fleet_response.status_code,
        detail=(
            fleet_response.json().get(
                "detail",
                "Could not create Driver Profile",
            )
        ),
    )

@app.post("/api/v1/admin/drivers/{keycloak_user_id}/recover")
async def recover_admin_driver(keycloak_user_id: str, driver: AdminDriverCreate, token_payload: dict = Depends(validate_access_token),):
    """
    Ολοκληρώνει τη δημιουργία Driver Profile μετά από αβέβαιη
    αποτυχία, χωρίς να δημιουργεί δεύτερο χρήστη στο Keycloak.
    """

    role_checker(token_payload, ADMIN_ROLES)

    # Επιβεβαιώνουμε ότι το συγκεκριμένο Keycloak ID αντιστοιχεί
    # στα στοιχεία του οδηγού που θέλει να ανακτήσει ο Admin.
    try:
        existing_user = await keycloak_admin_client.get_user_by_username(
            driver.username
        )
    except (httpx.RequestError, httpx.HTTPStatusError):
        logger.exception(
            "Could not verify recovery identity: username=%s",
            driver.username,
        )
        raise HTTPException(
            status_code=503,
            detail="Could not verify Keycloak identity",
        )

    if existing_user is None:
        raise HTTPException(
            status_code=404,
            detail="Keycloak user not found",
        )

    if (
        existing_user.get("id") != keycloak_user_id
        or existing_user.get("username") != driver.username
        or (existing_user.get("email") or "").lower()
        != str(driver.email).lower()
        or existing_user.get("firstName") != driver.first_name
        or existing_user.get("lastName") != driver.last_name
    ):
        raise HTTPException(
            status_code=409,
            detail="Keycloak identity does not match recovery request",
        )

    # Το username ανήκει στο Keycloak και δεν αποθηκεύεται
    # ως business πεδίο στο Driver Profile.
    driver_data = driver.model_dump(
        mode="json",
        exclude={"username"},
    )
    driver_data["keycloak_user_id"] = keycloak_user_id

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            profile_response = await client.get(
                f"{FLEET_API_URL}/drivers/"
                f"by-keycloak-user/{keycloak_user_id}"
            )
        except httpx.RequestError:
            logger.exception(
                "Could not check recovery profile: keycloak_user_id=%s",
                keycloak_user_id,
            )
            raise HTTPException(
                status_code=503,
                detail="Could not check existing Driver Profile",
            )

        if profile_response.status_code == 200:
            existing_profile = profile_response.json()

            # Αν υπάρχει ήδη προφίλ, ελέγχουμε ότι αφορά
            # την ίδια αίτηση πριν το επιστρέψουμε.
            if any(
                existing_profile.get(field) != value
                for field, value in driver_data.items()
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Existing Driver Profile has different data",
                )

            logger.info(
                "Recovered existing Driver Profile: "
                "keycloak_user_id=%s",
                keycloak_user_id,
            )
            return existing_profile

        if profile_response.status_code != 404:
            raise HTTPException(
                status_code=503,
                detail="Could not verify Driver Profile state",
            )

        # Το προφίλ λείπει. Το Fleet API διαθέτει ήδη
        # μοναδικούς δείκτες και χειρισμό επαναλαμβανόμενης
        # δημιουργίας για το ίδιο keycloak_user_id.
        try:
            fleet_response = await client.post(
                f"{FLEET_API_URL}/drivers",
                json=driver_data,
            )
        except httpx.RequestError:
            logger.exception(
                "Uncertain Driver recovery: keycloak_user_id=%s",
                keycloak_user_id,
            )
            raise HTTPException(
                status_code=503,
                detail=(
                    "Recovery outcome is uncertain. "
                    "Check the profile before retrying."
                ),
            )

    if fleet_response.status_code == 200:
        logger.info(
            "Recovered Driver Profile: "
            "driver_id=%s keycloak_user_id=%s",
            driver.driver_id,
            keycloak_user_id,
        )
        return fleet_response.json()

    if fleet_response.status_code >= 500:
        raise HTTPException(
            status_code=503,
            detail="Fleet API recovery outcome is uncertain",
        )

    # Επιστρέφουμε το πραγματικό validation/conflict error
    # χωρίς να διαγράψουμε την υπάρχουσα ταυτότητα.
    raise HTTPException(
        status_code=fleet_response.status_code,
        detail=fleet_response.json().get(
            "detail",
            "Could not recover Driver Profile",
        ),
    )

@app.patch("/api/v1/admin/drivers/{driver_id}")
async def admin_update_driver( driver_id: str, driver_update: AdminDriverUpdate,token_payload: dict = Depends(validate_access_token),):
    """
    Ενημερώνει το Driver Profile και, όταν χρειάζεται,
    τα αντίστοιχα προσωπικά στοιχεία στο Keycloak.
    """
    role_checker(token_payload, ADMIN_ROLES)

    update_data = driver_update.model_dump(
        exclude_unset=True,
        mode="json",
    )

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No fields provided for update",
        )

    # Τα βασικά στοιχεία ταυτότητας δεν επιτρέπεται
    # να αντικατασταθούν με null.
    identity_fields = {
        "first_name": "firstName",
        "last_name": "lastName",
        "email": "email",
    }

    if any(
        field in update_data and update_data[field] is None
        for field in identity_fields
    ):
        raise HTTPException(
            status_code=422,
            detail="Identity fields cannot be null",
        )

    # Το Fleet API παραμένει ο ιδιοκτήτης του Driver Profile.
    # Χρησιμοποιούμε το υπάρχον GET /drivers.
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            drivers_response = await client.get(
                f"{FLEET_API_URL}/drivers"
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=503,
                detail="Fleet API unavailable",
            )

    if drivers_response.status_code != 200:
        raise HTTPException(
            status_code=503,
            detail="Could not retrieve Driver Profile",
        )

    existing_driver = next(
        (
            driver
            for driver in drivers_response.json()
            if driver.get("driver_id") == driver_id
        ),
        None,
    )

    if existing_driver is None:
        raise HTTPException(
            status_code=404,
            detail="Driver not found",
        )

    keycloak_user_id = existing_driver.get("keycloak_user_id")

    if not keycloak_user_id:
        raise HTTPException(
            status_code=409,
            detail="Driver has no Keycloak identity",
        )

    # Διαχωρίζουμε τα στοιχεία ταυτότητας από τα
    # υπόλοιπα business fields.
    identity_update = {
        keycloak_field: update_data[field]
        for field, keycloak_field in identity_fields.items()
        if field in update_data
    }

    # Αν το PATCH αφορά μόνο business fields, δεν
    # πραγματοποιούμε περιττές αλλαγές στο Keycloak.
    original_identity = None

    if identity_update:
        try:
            existing_user = (
                await keycloak_admin_client.get_user_by_id(
                    keycloak_user_id
                )
            )
        except (httpx.RequestError, httpx.HTTPStatusError):
            logger.exception(
                "Could not retrieve Keycloak user: user_id=%s",
                keycloak_user_id,
            )
            raise HTTPException(
                status_code=503,
                detail="Could not retrieve Keycloak identity",
            )

        if existing_user is None:
            raise HTTPException(
                status_code=409,
                detail="Keycloak identity not found",
            )

        # Κρατάμε τις προηγούμενες τιμές για πιθανή
        # αντιστάθμιση σε περίπτωση οριστικής αποτυχίας.
        original_identity = {
            field: existing_user.get(field)
            for field in identity_update
        }

        try:
            await keycloak_admin_client.update_user(
                keycloak_user_id,
                identity_update,
            )

        except httpx.RequestError:
            # Ελέγχουμε αν το Keycloak αποθήκευσε τις αλλαγές
            # παρά το σφάλμα επικοινωνίας.
            try:
                current_user = await keycloak_admin_client.get_user_by_id(
                    keycloak_user_id
                )
            except (httpx.RequestError, httpx.HTTPStatusError):
                current_user = None

            identity_confirmed = (
                    current_user is not None
                    and all(
                current_user.get(field) == value
                for field, value in identity_update.items()
            )
            )

            if not identity_confirmed:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Keycloak update could not be confirmed. "
                        "Check identity before retrying."
                    ),
                )

            logger.info(
                "Confirmed Keycloak update after request error: user_id=%s",
                keycloak_user_id,
            )

        except httpx.HTTPStatusError as error:
            logger.warning(
                "Keycloak rejected update: user_id=%s status=%s",
                keycloak_user_id,
                error.response.status_code,
            )
            raise HTTPException(
                status_code=502,
                detail="Keycloak rejected identity update",
            )

    # Στέλνουμε όλα τα πεδία στο Fleet API, επειδή
    # εκεί βρίσκεται το πλήρες Driver Profile.
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            fleet_response = await client.patch(
                f"{FLEET_API_URL}/drivers/{driver_id}",
                json=update_data,
            )

    except httpx.RequestError:
        # Αν χάθηκε η απάντηση, ελέγχουμε αν το
        # Fleet API αποθήκευσε τελικά τις αλλαγές.
        update_confirmed = await check_driver_update_state(
            driver_id,
            update_data,
        )

        if update_confirmed is True:
            # Ανακτούμε το ενημερωμένο προφίλ.
            try:
                async with httpx.AsyncClient(
                        timeout=10.0
                ) as client:
                    response = await client.get(
                        f"{FLEET_API_URL}/drivers"
                    )

                if response.status_code == 200:
                    updated_driver = next(
                        (
                            item
                            for item in response.json()
                            if item.get("driver_id") == driver_id
                        ),
                        None,
                    )

                    if updated_driver is not None:
                        return updated_driver

            except (httpx.RequestError, ValueError):
                logger.exception(
                    "Could not retrieve updated Driver: "
                    "driver_id=%s",
                    driver_id,
                )

        # Αν δεν μπορούμε να επιβεβαιώσουμε την
        # ενημέρωση, δεν κάνουμε τυφλό rollback.
        raise HTTPException(
            status_code=503,
            detail=(
                "Fleet API update could not be confirmed. "
                "Recheck the Driver Profile before retrying."
            ),
        )

    if fleet_response.status_code == 200:
        logger.info(
            "Updated Driver: driver_id=%s",
            driver_id,
        )
        return fleet_response.json()

    # Μόνο για ρητή αποτυχία 4xx του Fleet API
    # επιχειρούμε επαναφορά των αλλαγών ταυτότητας.
    # Για 5xx η κατάσταση μπορεί να είναι αβέβαιη.
    if (
        400 <= fleet_response.status_code < 500
        and original_identity is not None
    ):
        try:
            await keycloak_admin_client.update_user(
                keycloak_user_id,
                original_identity,
            )
        except Exception:
            logger.exception(
                "Identity rollback requires reconciliation: "
                "driver_id=%s user_id=%s",
                driver_id,
                keycloak_user_id,
            )
            raise HTTPException(
                status_code=503,
                detail=(
                    "Fleet API rejected the update, but "
                    "Keycloak rollback could not be confirmed."
                ),
            )

    if fleet_response.status_code >= 500:
        raise HTTPException(
            status_code=503,
            detail=(
                "Fleet API update failed. "
                "Reconciliation may be required."
            ),
        )

    # Επιστρέφουμε το πραγματικό validation ή
    # conflict error του Fleet API.
    try:
        error_detail = fleet_response.json().get(
            "detail",
            "Driver update rejected",
        )
    except ValueError:
        error_detail = "Driver update rejected"

    raise HTTPException(
        status_code=fleet_response.status_code,
        detail=error_detail,
    )

@app.post("/api/v1/admin/drivers/{driver_id}/activate")
async def admin_activate_driver( driver_id: str, token_payload: dict = Depends(validate_access_token),):
    """
    Επανενεργοποιεί τον οδηγό στο Fleet API και στο Keycloak.

    Αν προκύψει αβέβαιη έκβαση, ελέγχουμε την πραγματική
    κατάσταση πριν επιστρέψουμε αποτέλεσμα.
    """
    role_checker(token_payload, ADMIN_ROLES)

    # Βρίσκουμε το Driver Profile και το αντίστοιχο Keycloak ID.
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            drivers_response = await client.get(
                f"{FLEET_API_URL}/drivers"
            )
            drivers_response.raise_for_status()
    except (httpx.RequestError, httpx.HTTPStatusError):
        logger.exception(
            "Could not retrieve Driver Profile: driver_id=%s",
            driver_id,
        )
        raise HTTPException(
            status_code=503,
            detail="Could not retrieve Driver Profile",
        )

    driver = next(
        (
            item for item in drivers_response.json()
            if item.get("driver_id") == driver_id
        ),
        None,
    )

    if driver is None:
        raise HTTPException(
            status_code=404,
            detail="Driver not found",
        )

    keycloak_user_id = driver.get("keycloak_user_id")

    if not keycloak_user_id:
        raise HTTPException(
            status_code=409,
            detail="Driver has no linked Keycloak account",
        )

    # Ελέγχουμε ότι η ταυτότητα υπάρχει πριν αλλάξουμε
    # την κατάσταση του Driver Profile.
    try:
        keycloak_user = await keycloak_admin_client.get_user_by_id( keycloak_user_id )
    except Exception:
        logger.exception(
            "Could not retrieve Keycloak user: driver_id=%s",
            driver_id,
        )
        raise HTTPException(
            status_code=503,
            detail="Could not verify Keycloak account",
        )

    if keycloak_user is None:
        raise HTTPException(
            status_code=409,
            detail="Linked Keycloak account does not exist",
        )

    # Πρώτα ενεργοποιούμε το Driver Profile.
    # Αν το Fleet API απορρίψει το αίτημα, δεν αλλάζουμε
    # την κατάσταση του λογαριασμού στο Keycloak.
    fleet_response = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            fleet_response = await client.post(
                f"{FLEET_API_URL}/drivers/{driver_id}/activate"
            )

    except httpx.RequestError:
        # Η HTTP απάντηση μπορεί να χάθηκε αφού το Fleet API
        # είχε ήδη ενεργοποιήσει το Driver Profile.
        logger.warning(
            "Fleet API activation response lost: driver_id=%s",
            driver_id,
        )

        activation_confirmed = await check_driver_status(
            driver_id,
            "ACTIVE",
        )

        if activation_confirmed is not True:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Driver activation outcome is uncertain. "
                    "Check the Driver Profile before retrying."
                ),
            )

    if fleet_response is not None:
        if fleet_response.status_code >= 500:
            raise HTTPException(
                status_code=503,
                detail="Fleet activation outcome is uncertain",
            )

        if fleet_response.status_code != 200:
            raise HTTPException(
                status_code=fleet_response.status_code,
                detail=fleet_response.json().get(
                    "detail",
                    "Could not activate Driver Profile",
                ),
            )

        updated_driver = fleet_response.json()

    else:
        # Αν χάθηκε η απάντηση αλλά επιβεβαιώσαμε ότι ο Driver
        # έγινε ACTIVE, ανακτούμε το ενημερωμένο Profile.
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                profile_response = await client.get(
                    f"{FLEET_API_URL}/drivers"
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=503,
                detail="Could not retrieve activated Driver Profile",
            )

        if profile_response.status_code != 200:
            raise HTTPException(
                status_code=503,
                detail="Could not retrieve activated Driver Profile",
            )

        updated_driver = next(
            (
                item
                for item in profile_response.json()
                if item.get("driver_id") == driver_id
            ),
            None,
        )

        if updated_driver is None:
            raise HTTPException(
                status_code=503,
                detail="Activated Driver Profile could not be found",
            )

    if updated_driver.get("status") != "ACTIVE":
        raise HTTPException(
            status_code=503,
            detail="Fleet activation could not be confirmed",
        )

    # Ενεργοποιούμε τον λογαριασμό μόνο αν χρειάζεται.
    # Αν η επικοινωνία αποτύχει, ξαναδιαβάζουμε το Keycloak
    # για να διαπιστώσουμε αν η αλλαγή αποθηκεύτηκε.
    if keycloak_user.get("enabled") is not True:
        try:
            await keycloak_admin_client.set_user_enabled( keycloak_user_id,True, )
        except Exception:
            logger.exception(
                "Could not confirm Keycloak activation: "
                "driver_id=%s",
                driver_id,
            )

            try:
                current_user = (
                    await keycloak_admin_client.get_user_by_id(
                        keycloak_user_id
                    )
                )
            except Exception:
                current_user = None

            if ( current_user is None or current_user.get("enabled") is not True ):
                # Το Fleet Profile ενδέχεται να είναι ήδη ACTIVE.
                # Δεν δηλώνουμε επιτυχία όταν τα δύο συστήματα
                # δεν έχουν επιβεβαιωμένα συγχρονιστεί.
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Driver Profile is ACTIVE, but Keycloak "
                        "activation could not be confirmed. "
                        "Check both systems before retrying."
                    ),
                )
    logger.info(
        "Activated Driver in Fleet API and Keycloak: "
        "driver_id=%s",
        driver_id,
    )

    return updated_driver

@app.post("/api/v1/admin/drivers/{driver_id}/deactivate")
async def admin_deactivate_driver( driver_id: str, token_payload: dict = Depends(validate_access_token), ):
    """
    Απενεργοποιεί έναν οδηγό στο Keycloak και στο Fleet API.

    Αν χαθεί κάποια απάντηση, ελέγχουμε την πραγματική
    κατάσταση πριν θεωρήσουμε ότι η ενέργεια απέτυχε.
    """

    role_checker(token_payload, ADMIN_ROLES)

    # Ανακτούμε το Driver Profile από το Fleet API.
    # Το Gateway δεν αποκτά απευθείας πρόσβαση στη MongoDB.
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{FLEET_API_URL}/drivers"
            )
    except httpx.RequestError:
        logger.exception(
            "Could not retrieve Driver Profile: driver_id=%s",
            driver_id,
        )
        raise HTTPException(
            status_code=503,
            detail="Fleet API unavailable",
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=503,
            detail="Could not retrieve Driver Profile",
        )

    existing_driver = next(
        (
            item
            for item in response.json()
            if item.get("driver_id") == driver_id
        ),
        None,
    )

    if existing_driver is None:
        raise HTTPException(
            status_code=404,
            detail="Driver not found",
        )

    keycloak_user_id = existing_driver.get("keycloak_user_id")

    if not keycloak_user_id:
        raise HTTPException(
            status_code=409,
            detail="Driver has no Keycloak identity",
        )

    # Διαβάζουμε την τρέχουσα κατάσταση του λογαριασμού.
    try:
        keycloak_user = await keycloak_admin_client.get_user_by_id(
            keycloak_user_id
        )
    except Exception:
        logger.exception(
            "Could not retrieve Keycloak user: user_id=%s",
            keycloak_user_id,
        )
        raise HTTPException(
            status_code=503,
            detail="Could not retrieve Keycloak identity",
        )

    if keycloak_user is None:
        raise HTTPException(
            status_code=409,
            detail="Keycloak identity not found",
        )

    # Κρατάμε την προηγούμενη κατάσταση για πιθανή
    # αντιστάθμιση σε περίπτωση ρητής αποτυχίας.
    originally_enabled = keycloak_user.get("enabled")

    if not isinstance(originally_enabled, bool):
        raise HTTPException(
            status_code=503,
            detail="Could not determine Keycloak account state",
        )

    # Απενεργοποιούμε πρώτα την ταυτότητα.
    if originally_enabled:
        try:
            await keycloak_admin_client.set_user_enabled(
                keycloak_user_id,
                False,
            )
        except Exception:
            # Ένα timeout δεν αποδεικνύει ότι η αλλαγή απέτυχε.
            # Διαβάζουμε ξανά την κατάσταση του λογαριασμού.
            try:
                current_user = (
                    await keycloak_admin_client.get_user_by_id(
                        keycloak_user_id
                    )
                )
            except Exception:
                current_user = None

            if (
                current_user is None
                or current_user.get("enabled") is not False
            ):
                logger.exception(
                    "Uncertain Keycloak deactivation: user_id=%s",
                    keycloak_user_id,
                )
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Keycloak deactivation could not be confirmed. "
                        "Check the account before retrying."
                    ),
                )

    # Ζητάμε από το Fleet API να απενεργοποιήσει το Profile
    # και να αποδεσμεύσει τα οχήματα του οδηγού.
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            fleet_response = await client.post(
                f"{FLEET_API_URL}/drivers/{driver_id}/deactivate"
            )
    except httpx.RequestError:
        logger.warning(
            "Fleet API deactivation response lost: driver_id=%s",
            driver_id,
        )

        # Ελέγχουμε αν το Fleet API ολοκλήρωσε την αλλαγή.
        # Δεν κάνουμε αυτόματο rollback μετά από timeout.
        confirmed = await check_driver_state(
            driver_id
        )

        if confirmed is not True:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Driver deactivation outcome is uncertain. "
                    "Check the Driver Profile and vehicle assignments "
                    "before retrying."
                ),
            )

        # Το status επιβεβαιώθηκε, αλλά πρέπει να ανακτήσουμε
        # και το τελικό Driver Profile.
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                profile_response = await client.get(
                    f"{FLEET_API_URL}/drivers"
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=503,
                detail="Could not retrieve deactivated Driver Profile",
            )

        if profile_response.status_code != 200:
            raise HTTPException(
                status_code=503,
                detail="Could not retrieve deactivated Driver Profile",
            )

        updated_driver = next(
            (
                item
                for item in profile_response.json()
                if item.get("driver_id") == driver_id
            ),
            None,
        )

        if updated_driver is None:
            raise HTTPException(
                status_code=503,
                detail="Deactivated Driver Profile could not be found",
            )

    else:
        if fleet_response.status_code == 200:
            updated_driver = fleet_response.json()

        elif 400 <= fleet_response.status_code < 500:
            # Μόνο σε ρητή αποτυχία επιχειρούμε αντιστάθμιση.
            # Δεν ενεργοποιούμε λογαριασμό που ήταν ήδη ανενεργός.
            if originally_enabled:
                try:
                    await keycloak_admin_client.set_user_enabled(
                        keycloak_user_id,
                        True,
                    )
                except Exception:
                    logger.exception(
                        "Keycloak rollback requires reconciliation: "
                        "user_id=%s",
                        keycloak_user_id,
                    )
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            "Fleet API rejected deactivation, but "
                            "Keycloak rollback could not be confirmed."
                        ),
                    )

            raise HTTPException(
                status_code=fleet_response.status_code,
                detail="Fleet API rejected Driver deactivation",
            )

        else:
            # Σε 5xx δεν γνωρίζουμε αν έχουν ήδη γίνει εγγραφές.
            raise HTTPException(
                status_code=503,
                detail=(
                    "Fleet API deactivation could not be confirmed. "
                    "Reconciliation is required."
                ),
            )

    # Ελέγχουμε την τελική κατάσταση πριν τερματίσουμε
    # τις συνεδρίες του οδηγού.
    if updated_driver.get("status") != "INACTIVE":
        raise HTTPException(
            status_code=503,
            detail="Driver Profile is not confirmed inactive",
        )
    # Επιβεβαιώνουμε την πλήρη απενεργοποίηση ακόμη
    # και όταν το Fleet API επέστρεψε κανονικά 200.
    deactivation_confirmed = await check_driver_state(
        driver_id
    )

    if deactivation_confirmed is not True:
        raise HTTPException(
            status_code=503,
            detail=(
                "Driver deactivation could not be fully confirmed. "
                "Check Driver status and vehicle assignments."
            ),
        )

    try:
        await keycloak_admin_client.logout_user(
            keycloak_user_id
        )
    except Exception:
        logger.exception(
            "Driver deactivated but Keycloak logout failed: "
            "driver_id=%s user_id=%s",
            driver_id,
            keycloak_user_id,
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Driver was deactivated, but session termination "
                "could not be confirmed."
            ),
        )

    logger.info(
        "Deactivated Driver: driver_id=%s keycloak_user_id=%s",
        driver_id,
        keycloak_user_id,
    )

    return updated_driver

@app.delete("/api/v1/admin/drivers/{driver_id}")
async def admin_delete_driver( driver_id: str, token_payload: dict = Depends(validate_access_token), ):
    """
    Εκτελεί Hard Delete ενός Driver.

    Το Hard Delete:
    - διαγράφει οριστικά το Driver Profile από το Fleet API,
    - διαγράφει το αντίστοιχο Keycloak identity,
    - διατηρεί το audit history,
    - υποστηρίζει retry όταν το Fleet Profile έχει ήδη διαγραφεί.

    Το Fleet API παραμένει υπεύθυνο για τα business δεδομένα.
    Το Keycloak παραμένει υπεύθυνο για το identity.
    """

    role_checker(token_payload, ADMIN_ROLES)

    keycloak_user_id = None
    driver_found = False

    # ---------------------------------------------------------
    # 1. Αναζητούμε πρώτα το υπάρχον Driver Profile.
    # ---------------------------------------------------------
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            drivers_response = await client.get(
                f"{FLEET_API_URL}/drivers"
            )

        drivers_response.raise_for_status()

        existing_driver = next(
            (
                driver
                for driver in drivers_response.json()
                if driver.get("driver_id") == driver_id
            ),
            None,
        )

    except httpx.RequestError:
        logger.exception(
            "Could not connect to Fleet API before Driver hard delete: "
            "driver_id=%s",
            driver_id,
        )
        raise HTTPException(
            status_code=503,
            detail="Fleet API is unavailable",
        )

    except httpx.HTTPStatusError:
        logger.exception(
            "Fleet API rejected Driver lookup before hard delete: "
            "driver_id=%s",
            driver_id,
        )
        raise HTTPException(
            status_code=503,
            detail="Could not verify Driver state",
        )

    if existing_driver is not None:
        driver_found = True
        keycloak_user_id = existing_driver.get("keycloak_user_id")

        if not keycloak_user_id:
            raise HTTPException(
                status_code=500,
                detail="Driver does not have a Keycloak user ID",
            )

        # Hard Delete επιτρέπεται μόνο αφού έχει προηγηθεί
        # το Soft Delete του Driver.
        if existing_driver.get("status") != "INACTIVE":
            raise HTTPException(
                status_code=409,
                detail=(
                    "Driver must be deactivated before hard delete"
                ),
            )

    else:
        # -----------------------------------------------------
        # 2. Το Profile μπορεί να έχει ήδη διαγραφεί από
        #    προηγούμενη μερικώς επιτυχημένη προσπάθεια.
        #
        #    Σε αυτή την περίπτωση ανακτούμε το Keycloak ID
        #    από το μόνιμο DELETED audit.
        # -----------------------------------------------------
        keycloak_user_id = (
            await get_deleted_driver_keycloak_user_id(driver_id)
        )

        if keycloak_user_id is None:
            raise HTTPException(
                status_code=404,
                detail="Driver not found",
            )

    # ---------------------------------------------------------
    # 3. Αν το Driver Profile υπάρχει ακόμη, εκτελούμε το
    #    business Hard Delete στο Fleet API.
    # ---------------------------------------------------------
    if driver_found:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                delete_response = await client.delete(
                    f"{FLEET_API_URL}/drivers/{driver_id}"
                )

            if 400 <= delete_response.status_code < 500:
                raise HTTPException(
                    status_code=delete_response.status_code,
                    detail=delete_response.text,
                )

            if delete_response.status_code >= 500:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Fleet API could not complete Driver hard delete"
                    ),
                )

        except httpx.RequestError:
            # Το request μπορεί να ολοκληρώθηκε στο Fleet API,
            # αλλά να χάθηκε η HTTP απάντηση.
            deletion_confirmed = (
                await check_driver_deleted_from_fleet(driver_id)
            )

            if deletion_confirmed is not True:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Driver hard delete result could not be confirmed"
                    ),
                )

    # ---------------------------------------------------------
    # 4. Πριν πειράξουμε το Keycloak επιβεβαιώνουμε ότι
    #    το Fleet Profile πράγματι δεν υπάρχει πλέον.
    # ---------------------------------------------------------
    deletion_confirmed = await check_driver_deleted_from_fleet(
        driver_id
    )

    if deletion_confirmed is not True:
        raise HTTPException(
            status_code=503,
            detail=(
                "Driver deletion from Fleet API could not be confirmed"
            ),
        )

    # ---------------------------------------------------------
    # 5. Διαγράφουμε το Keycloak identity.
    #
    #    Η delete_user() είναι πλέον idempotent:
    #    204 -> διαγράφηκε τώρα
    #    404 -> είχε ήδη διαγραφεί
    # ---------------------------------------------------------
    try:
        await keycloak_admin_client.delete_user(
            keycloak_user_id
        )

    except httpx.RequestError:
        # Μπορεί το Keycloak να εκτέλεσε το DELETE αλλά να
        # χάθηκε η απάντηση. Κάνουμε read-after-error verification.
        try:
            keycloak_user = (
                await keycloak_admin_client.get_user_by_id(
                    keycloak_user_id
                )
            )

        except (httpx.RequestError, httpx.HTTPStatusError, RuntimeError):
            logger.exception(
                "Could not verify Keycloak user after hard delete error: "
                "driver_id=%s keycloak_user_id=%s",
                driver_id,
                keycloak_user_id,
            )
            raise HTTPException(
                status_code=503,
                detail=(
                    "Driver Profile was deleted, but Keycloak "
                    "deletion could not be confirmed"
                ),
            )

        if keycloak_user is not None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Driver Profile was deleted, but Keycloak "
                    "identity still exists"
                ),
            )

    except RuntimeError:
        # Για οποιαδήποτε επιβεβαιωμένη αποτυχία του Keycloak
        # ελέγχουμε ξανά την πραγματική τελική κατάσταση.
        try:
            keycloak_user = (
                await keycloak_admin_client.get_user_by_id(
                    keycloak_user_id
                )
            )

        except (httpx.RequestError, httpx.HTTPStatusError, RuntimeError):
            logger.exception(
                "Could not verify Keycloak user after hard delete failure: "
                "driver_id=%s keycloak_user_id=%s",
                driver_id,
                keycloak_user_id,
            )
            raise HTTPException(
                status_code=503,
                detail=(
                    "Driver Profile was deleted, but Keycloak "
                    "deletion could not be confirmed"
                ),
            )

        if keycloak_user is not None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Driver Profile was deleted, but Keycloak "
                    "identity could not be deleted"
                ),
            )

    # ---------------------------------------------------------
    # 6. Τελική επιβεβαίωση του Keycloak state.
    # ---------------------------------------------------------
    try:
        remaining_keycloak_user = (
            await keycloak_admin_client.get_user_by_id(
                keycloak_user_id
            )
        )

    except (httpx.RequestError, httpx.HTTPStatusError, RuntimeError):
        logger.exception(
            "Could not perform final Keycloak verification: "
            "driver_id=%s keycloak_user_id=%s",
            driver_id,
            keycloak_user_id,
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Driver Profile was deleted, but final Keycloak "
                "verification failed"
            ),
        )

    if remaining_keycloak_user is not None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Driver Profile was deleted, but Keycloak "
                "identity still exists"
            ),
        )

    logger.info(
        "Hard deleted Driver: driver_id=%s keycloak_user_id=%s",
        driver_id,
        keycloak_user_id,
    )

    return {
        "message": "Driver hard deleted successfully",
        "driver_id": driver_id,
    }

@app.post("/api/v1/admin/fleet-managers", status_code=201)
async def admin_create_fleet_manager( fleet_manager: AdminFleetManagerCreate, token_payload: dict = Depends(validate_access_token),):
    """
    Δημιουργεί Keycloak identity και Fleet Manager Profile.

    Μόνο ο Admin μπορεί να εκτελέσει αυτή τη λειτουργία.
    Το Fleet API παραμένει υπεύθυνο για τα business δεδομένα
    του Fleet Manager.
    """

    role_checker(token_payload, ADMIN_ROLES)
    # Ελέγχουμε πρώτα αν υπάρχει ήδη το username στο Keycloak.
    # Δεν επιτρέπουμε να δημιουργηθεί δεύτερος λογαριασμός
    # με το ίδιο username.
    try:
        existing_user = ( await keycloak_admin_client.get_user_by_username( fleet_manager.username ) )
    except (httpx.RequestError, httpx.HTTPStatusError):
        logger.exception(
            "Could not check Keycloak username"
        )
        raise HTTPException( status_code=503, detail="Could not verify Keycloak username", )

    if existing_user is not None:
        raise HTTPException( status_code=409, detail="Keycloak username already exists", )
    # Δημιουργούμε το identity του Fleet Manager στο Keycloak.
    #
    # Δεν ορίζουμε προκαθορισμένο password εδώ.
    # Το Keycloak θα διαχειριστεί τη διαδικασία ώστε ο χρήστης
    # να ορίσει τον δικό του κωδικό.
    try:
        keycloak_user_id = await keycloak_admin_client.create_user(
            username=fleet_manager.username,
            email=str(fleet_manager.email),
            first_name=fleet_manager.first_name,
            last_name=fleet_manager.last_name,
        )

    except httpx.RequestError:
        # Ένα timeout ή άλλο πρόβλημα επικοινωνίας μπορεί να συμβεί
        # αφού το Keycloak έχει ήδη δημιουργήσει τον χρήστη.
        #
        # Για αυτό δεν επιχειρούμε αυτόματα δεύτερη δημιουργία,
        # γιατί υπάρχει κίνδυνος να δημιουργήσουμε ασυνεπή κατάσταση.
        logger.exception(
            "Uncertain Keycloak Fleet Manager creation: username=%s",
            fleet_manager.username,
        )

        raise HTTPException( status_code=503, detail=( "Keycloak creation outcome is uncertain. Check the user before retrying." ), )

    except Exception:
        logger.exception(
            "Keycloak Fleet Manager creation failed: username=%s",
            fleet_manager.username,
        )

        raise HTTPException( status_code=502, detail="Could not create Keycloak user", )
    # Από τη στιγμή που δημιουργήθηκε επιτυχώς το Keycloak identity,
    # του αναθέτουμε το realm role "fleet_manager".
    #
    # Το role είναι απαραίτητο ώστε το JWT του χρήστη να περιέχει
    # το "fleet_manager" και το API Gateway να μπορεί αργότερα
    # να εφαρμόζει σωστά το authorization.
    #
    # Αν η ανάθεση του role αποτύχει, δεν αφήνουμε ορφανό
    # Keycloak user. Προσπαθούμε να διαγράψουμε το identity
    # που μόλις δημιουργήσαμε.
    try:
        await keycloak_admin_client.assign_realm_role( keycloak_user_id=keycloak_user_id, role_name="fleet_manager", )

    except Exception:
        logger.exception(
            "Could not assign fleet_manager role: "
            "keycloak_user_id=%s",
            keycloak_user_id,
        )

        try:
            await keycloak_admin_client.delete_user( keycloak_user_id )

        except Exception:
            logger.exception(
                "Manual cleanup required after Fleet Manager "
                "role assignment failure: keycloak_user_id=%s",
                keycloak_user_id,
            )

            raise HTTPException( status_code=503, detail=( "Fleet Manager role assignment failed and automatic cleanup could not be confirmed"
                ),
            )

        raise HTTPException( status_code=502, detail="Could not assign fleet_manager role", )
    # Το username αφορά αποκλειστικά το Keycloak και δεν αποτελεί
    # business δεδομένο του Fleet Manager μέσα στο Fleet API.
    #
    # Δημιουργούμε λοιπόν το payload χωρίς το username και
    # προσθέτουμε το πραγματικό Keycloak ID που δημιουργήθηκε
    # από το Gateway.
    fleet_manager_data = fleet_manager.model_dump( mode="json", exclude={"username"}, )

    fleet_manager_data["keycloak_user_id"] = keycloak_user_id

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            fleet_response = await client.post( f"{FLEET_API_URL}/fleet-managers", json=fleet_manager_data, )

        except httpx.RequestError:
            # Δεν γνωρίζουμε αν το Fleet API πρόλαβε να
            # αποθηκεύσει το Fleet Manager Profile πριν
            # παρουσιαστεί το πρόβλημα επικοινωνίας.
            logger.exception(
                "Uncertain Fleet Manager Profile creation: "
                "keycloak_user_id=%s",
                keycloak_user_id,
            )

            # Ελέγχουμε την πραγματική κατάσταση στο Fleet API
            # χρησιμοποιώντας το σταθερό Keycloak user ID.
            try:
                profile_response = await client.get( f"{FLEET_API_URL}/fleet-managers/by-keycloak-user/{keycloak_user_id}" )

            except httpx.RequestError:
                logger.exception(
                    "Could not reconcile Fleet Manager Profile: "
                    "keycloak_user_id=%s",
                    keycloak_user_id,
                )

                raise HTTPException( status_code=503, detail=( "Fleet Manager creation outcome is uncertain. Manual reconciliation is required." ), )

            if profile_response.status_code == 200:
                # Το Profile δημιουργήθηκε κανονικά, παρόλο που
                # το αρχικό request εμφάνισε πρόβλημα επικοινωνίας.
                return profile_response.json()

            if profile_response.status_code != 404:
                raise HTTPException( status_code=503, detail="Could not reconcile Fleet Manager Profile", )

            # Το άμεσο 404 μετά από timeout δεν αποτελεί ασφαλή
            # απόδειξη ότι το αρχικό POST δεν εκτελείται ακόμη.
            # Δεν διαγράφουμε λοιπόν αυτόματα τον Keycloak user.
            raise HTTPException( status_code=503, detail=( "Fleet Manager Profile not found after timeout. Reconciliation is required before retrying." ), )
    # Αν το Fleet API δημιούργησε κανονικά το Profile,
    # η συνολική διαδικασία δημιουργίας ολοκληρώθηκε επιτυχώς.
    if fleet_response.status_code == 200:
        logger.info(
            "Created Fleet Manager: manager_id=%s keycloak_user_id=%s",
            fleet_manager.manager_id,
            keycloak_user_id,
        )

        return fleet_response.json()

    # Σε server error του Fleet API δεν γνωρίζουμε με βεβαιότητα
    # αν κάποια αλλαγή πραγματοποιήθηκε πριν από την αποτυχία.
    # Για αυτό δεν διαγράφουμε αυτόματα το Keycloak identity.
    if fleet_response.status_code >= 500:
        raise HTTPException( status_code=503, detail=( "Fleet API failed. Reconciliation is required before cleanup." ), )

    # Αν το Fleet API επέστρεψε σαφή απόρριψη, όπως validation
    # error ή conflict, το Profile δεν δημιουργήθηκε επιτυχώς.
    # Διαγράφουμε λοιπόν το Keycloak identity που δημιουργήσαμε
    # νωρίτερα, ώστε να μη μείνει ορφανός χρήστης.
    try:
        await keycloak_admin_client.delete_user( keycloak_user_id )

    except Exception:
        logger.exception(
            "Could not compensate failed Fleet Manager creation: "
            "keycloak_user_id=%s",
            keycloak_user_id,
        )

        raise HTTPException( status_code=503,
                             detail=( "Fleet Manager Profile was rejected, but Keycloak user cleanup could not be confirmed" ), )

    # Αφού ολοκληρώθηκε το cleanup στο Keycloak,
    # επιστρέφουμε στον Admin το πραγματικό validation/conflict
    # error που επέστρεψε το Fleet API.
    raise HTTPException( status_code=fleet_response.status_code,
                         detail=(fleet_response.json().get( "detail", "Could not create Fleet Manager Profile", ) ),)


@app.post("/api/v1/admin/fleet-managers/{keycloak_user_id}/recover")
async def recover_admin_fleet_manager( keycloak_user_id: str, fleet_manager: AdminFleetManagerCreate, token_payload: dict = Depends(validate_access_token),):
    """
    Ολοκληρώνει τη δημιουργία Fleet Manager Profile μετά από
    αβέβαιη αποτυχία, χωρίς να δημιουργεί δεύτερο χρήστη
    στο Keycloak.
    """

    role_checker(token_payload, ADMIN_ROLES)

    # Επιβεβαιώνουμε ότι το συγκεκριμένο Keycloak ID αντιστοιχεί
    # στα στοιχεία του Fleet Manager που θέλει να ανακτήσει ο Admin.
    try:
        existing_user = ( await keycloak_admin_client.get_user_by_username( fleet_manager.username )
        )

    except (httpx.RequestError, httpx.HTTPStatusError):
        logger.exception(
            "Could not verify Fleet Manager recovery identity: "
            "username=%s",
            fleet_manager.username,
        )

        raise HTTPException( status_code=503, detail="Could not verify Keycloak identity", )

    if existing_user is None:
        raise HTTPException( status_code=404, detail="Keycloak user not found", )

    # Δεν αρκεί να υπάρχει ένας χρήστης με το συγκεκριμένο username.
    # Επιβεβαιώνουμε ότι το ID και τα βασικά identity στοιχεία
    # αντιστοιχούν στην αίτηση Recovery.
    if ( existing_user.get("id") != keycloak_user_id
        or existing_user.get("username") != fleet_manager.username
        or (existing_user.get("email")  or "").lower() != str(fleet_manager.email).lower()
        or existing_user.get("firstName") != fleet_manager.first_name
        or existing_user.get("lastName") != fleet_manager.last_name
    ):
        raise HTTPException( status_code=409, detail=( "Keycloak identity does not match recovery request" ), )

    # Το username ανήκει αποκλειστικά στο Keycloak.
    # Το Fleet API λαμβάνει τα business δεδομένα μαζί με
    # το ήδη υπάρχον Keycloak user ID.
    fleet_manager_data = fleet_manager.model_dump( mode="json", exclude={"username"}, )

    fleet_manager_data["keycloak_user_id"] = keycloak_user_id

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Πριν επιχειρήσουμε νέα δημιουργία, ελέγχουμε αν
        # το Fleet Manager Profile υπάρχει ήδη.
        try:
            profile_response = await client.get( f"{FLEET_API_URL}/fleet-managers/by-keycloak-user/{keycloak_user_id}" )

        except httpx.RequestError:
            logger.exception(
                "Could not check Fleet Manager recovery profile: "
                "keycloak_user_id=%s",
                keycloak_user_id,
            )

            raise HTTPException(status_code=503, detail=( "Could not check existing Fleet Manager Profile" ), )

        if profile_response.status_code == 200:
            existing_profile = profile_response.json()

            # Αν το Profile υπάρχει ήδη, το Recovery είναι
            # idempotent μόνο όταν τα αποθηκευμένα δεδομένα
            # αντιστοιχούν στην ίδια αίτηση.
            if any(
                existing_profile.get(field) != value
                for field, value in fleet_manager_data.items()
            ):
                raise HTTPException( status_code=409, detail=( "Existing Fleet Manager Profile has different data" ), )

            logger.info(
                "Recovered existing Fleet Manager Profile: "
                "keycloak_user_id=%s",
                keycloak_user_id,
            )

            return existing_profile

        if profile_response.status_code != 404:
            raise HTTPException( status_code=503, detail=( "Could not verify Fleet Manager Profile state" ),)

        # Αν δεν υπάρχει Profile, χρησιμοποιούμε το ήδη υπάρχον
        # Keycloak identity και δημιουργούμε μόνο το business Profile.
        #
        # Δεν δημιουργούμε δεύτερο Keycloak user.
        try:
            fleet_response = await client.post( f"{FLEET_API_URL}/fleet-managers", json=fleet_manager_data, )

        except httpx.RequestError:
            # Δεν γνωρίζουμε αν το Fleet API πρόλαβε να ολοκληρώσει
            # το POST πριν παρουσιαστεί το πρόβλημα επικοινωνίας.
            # Δεν επαναλαμβάνουμε αυτόματα τη δημιουργία.
            logger.exception(
                "Uncertain Fleet Manager recovery: "
                "keycloak_user_id=%s",
                keycloak_user_id,
            )

            raise HTTPException( status_code=503, detail=( "Recovery outcome is uncertain. " "Check the profile before retrying." ), )

    if fleet_response.status_code == 200:
        logger.info(
            "Recovered Fleet Manager Profile: "
            "manager_id=%s keycloak_user_id=%s",
            fleet_manager.manager_id,
            keycloak_user_id,
        )

        return fleet_response.json()

    # Σε server error δεν μπορούμε να γνωρίζουμε με βεβαιότητα
    # αν το Fleet API πραγματοποίησε κάποια αλλαγή.
    if fleet_response.status_code >= 500:
        raise HTTPException( status_code=503, detail=( "Fleet API recovery outcome is uncertain" ), )

    # Σε σαφές validation/conflict error επιστρέφουμε το
    # πραγματικό σφάλμα του Fleet API.
    #
    # Δεν διαγράφουμε τον Keycloak user, επειδή στο Recovery
    # χρησιμοποιούμε identity που προϋπήρχε.
    raise HTTPException( status_code=fleet_response.status_code,
                         detail=fleet_response.json().get( "detail", "Could not recover Fleet Manager Profile", ), )

@app.patch("/api/v1/admin/fleet-managers/{manager_id}")
async def admin_update_fleet_manager( manager_id: str, fleet_manager_update: AdminFleetManagerUpdate, token_payload: dict = Depends(validate_access_token),):
    """
    Ενημερώνει το Fleet Manager Profile και, όταν χρειάζεται,
    τα αντίστοιχα προσωπικά στοιχεία στο Keycloak.

    Το Fleet API παραμένει υπεύθυνο για τα business δεδομένα,
    ενώ το Keycloak παραμένει υπεύθυνο για τα identity δεδομένα.
    """

    role_checker(token_payload, ADMIN_ROLES)

    # Κρατάμε μόνο τα πεδία που έστειλε πραγματικά ο Admin.
    # Έτσι ένα PATCH δεν αντικαθιστά κατά λάθος άλλα πεδία
    # με τις default τιμές του Pydantic model.
    update_data = fleet_manager_update.model_dump(
        exclude_unset=True,
        mode="json",
    )

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No fields provided for update",
        )

    # Τα συγκεκριμένα πεδία υπάρχουν τόσο στο Fleet Manager Profile
    # όσο και στο Keycloak identity.
    #
    # Στο Fleet API χρησιμοποιούμε snake_case,
    # ενώ το Keycloak χρησιμοποιεί τα αντίστοιχα ονόματα
    # firstName, lastName και email.
    identity_fields = {
        "first_name": "firstName",
        "last_name": "lastName",
        "email": "email",
    }

    # Τα βασικά identity fields δεν επιτρέπεται να γίνουν null.
    # Διαφορετικά θα μπορούσαμε να αφήσουμε ασυνεπή στοιχεία
    # μεταξύ Keycloak και Fleet Manager Profile.
    if any(
        field in update_data and update_data[field] is None
        for field in identity_fields
    ):
        raise HTTPException(
            status_code=422,
            detail="Identity fields cannot be null",
        )

    # Ανακτούμε πρώτα το υπάρχον Fleet Manager Profile.
    # Το Fleet API παραμένει ο αποκλειστικός ιδιοκτήτης
    # των business δεδομένων.
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            managers_response = await client.get(
                f"{FLEET_API_URL}/fleet-managers"
            )

    except httpx.RequestError:
        logger.exception(
            "Could not retrieve Fleet Manager Profile: "
            "manager_id=%s",
            manager_id,
        )

        raise HTTPException(
            status_code=503,
            detail="Fleet API unavailable",
        )

    if managers_response.status_code != 200:
        raise HTTPException(
            status_code=503,
            detail="Could not retrieve Fleet Manager Profile",
        )

    existing_fleet_manager = next(
        (
            fleet_manager
            for fleet_manager in managers_response.json()
            if fleet_manager.get("manager_id") == manager_id
        ),
        None,
    )

    if existing_fleet_manager is None:
        raise HTTPException(
            status_code=404,
            detail="Fleet Manager not found",
        )

    keycloak_user_id = existing_fleet_manager.get(
        "keycloak_user_id"
    )

    if not keycloak_user_id:
        raise HTTPException(
            status_code=409,
            detail="Fleet Manager has no Keycloak identity",
        )

    # Δημιουργούμε ξεχωριστό payload μόνο για τα identity fields
    # που πρέπει να ενημερωθούν και στο Keycloak.
    identity_update = {
        keycloak_field: update_data[field]
        for field, keycloak_field in identity_fields.items()
        if field in update_data
    }

    # Αν το PATCH αφορά αποκλειστικά business δεδομένα,
    # δεν υπάρχει λόγος να κάνουμε αλλαγή στο Keycloak.
    original_identity = None

    if identity_update:
        try:
            existing_user = (
                await keycloak_admin_client.get_user_by_id(
                    keycloak_user_id
                )
            )

        except (httpx.RequestError, httpx.HTTPStatusError):
            logger.exception(
                "Could not retrieve Fleet Manager "
                "Keycloak user: user_id=%s",
                keycloak_user_id,
            )

            raise HTTPException(
                status_code=503,
                detail="Could not retrieve Keycloak identity",
            )

        if existing_user is None:
            raise HTTPException(
                status_code=409,
                detail="Keycloak identity not found",
            )

        # Αποθηκεύουμε τις προηγούμενες τιμές μόνο για τα πεδία
        # που πρόκειται να αλλάξουν.
        #
        # Θα χρησιμοποιηθούν για rollback μόνο αν το Fleet API
        # απορρίψει ρητά το PATCH με 4xx.
        original_identity = {
            field: existing_user.get(field)
            for field in identity_update
        }

        try:
            await keycloak_admin_client.update_user(
                keycloak_user_id,
                identity_update,
            )

        except httpx.RequestError:
            # Ένα communication error δεν αποδεικνύει ότι
            # το Keycloak δεν αποθήκευσε την αλλαγή.
            #
            # Διαβάζουμε ξανά το identity και ελέγχουμε
            # την πραγματική κατάσταση.
            try:
                current_user = (
                    await keycloak_admin_client.get_user_by_id(
                        keycloak_user_id
                    )
                )

            except (httpx.RequestError, httpx.HTTPStatusError):
                current_user = None

            identity_confirmed = (
                current_user is not None
                and all(
                    current_user.get(field) == value
                    for field, value in identity_update.items()
                )
            )

            if not identity_confirmed:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Keycloak update could not be confirmed. "
                        "Check identity before retrying."
                    ),
                )

            logger.info(
                "Confirmed Fleet Manager Keycloak update "
                "after request error: user_id=%s",
                keycloak_user_id,
            )

        except httpx.HTTPStatusError as error:
            logger.warning(
                "Keycloak rejected Fleet Manager update: "
                "user_id=%s status=%s",
                keycloak_user_id,
                error.response.status_code,
            )

            raise HTTPException(
                status_code=502,
                detail="Keycloak rejected identity update",
            )

    # Στέλνουμε ολόκληρο το update_data στο Fleet API.
    # Εκεί γίνεται η ενημέρωση του business Profile.
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            fleet_response = await client.patch(
                f"{FLEET_API_URL}/fleet-managers/{manager_id}",
                json=update_data,
            )

    except httpx.RequestError:
        # Αν χάθηκε η HTTP απάντηση, δεν γνωρίζουμε αν το
        # Fleet API πρόλαβε να αποθηκεύσει τις αλλαγές.
        #
        # Χρησιμοποιούμε τον helper που δημιουργήσαμε ώστε
        # να ελέγξουμε την πραγματική κατάσταση.
        update_confirmed = (
            await check_fleet_manager_update_state(
                manager_id,
                update_data,
            )
        )

        if update_confirmed is True:
            # Οι αλλαγές επιβεβαιώθηκαν.
            # Ανακτούμε και επιστρέφουμε το ενημερωμένο Profile.
            try:
                async with httpx.AsyncClient(
                    timeout=10.0
                ) as client:
                    response = await client.get(
                        f"{FLEET_API_URL}/fleet-managers"
                    )

                if response.status_code == 200:
                    updated_fleet_manager = next(
                        (
                            item
                            for item in response.json()
                            if item.get("manager_id") == manager_id
                        ),
                        None,
                    )

                    if updated_fleet_manager is not None:
                        return updated_fleet_manager

            except (httpx.RequestError, ValueError):
                logger.exception(
                    "Could not retrieve updated Fleet Manager: "
                    "manager_id=%s",
                    manager_id,
                )

        # Αν δεν μπορούμε να επιβεβαιώσουμε την κατάσταση,
        # δεν κάνουμε τυφλό rollback.
        #
        # Το Fleet API μπορεί να έχει ήδη εφαρμόσει την αλλαγή.
        raise HTTPException(
            status_code=503,
            detail=(
                "Fleet API update could not be confirmed. "
                "Recheck the Fleet Manager Profile before retrying."
            ),
        )

    # Κανονική επιτυχία.
    if fleet_response.status_code == 200:
        logger.info(
            "Updated Fleet Manager: manager_id=%s",
            manager_id,
        )

        return fleet_response.json()

    # Rollback του Keycloak κάνουμε μόνο όταν έχουμε σαφή
    # απόρριψη 4xx από το Fleet API.
    #
    # Σε αυτή την περίπτωση γνωρίζουμε ότι το business update
    # δεν έγινε αποδεκτό και μπορούμε να επαναφέρουμε με ασφάλεια
    # τα identity fields στις προηγούμενες τιμές τους.
    if (
        400 <= fleet_response.status_code < 500
        and original_identity is not None
    ):
        try:
            await keycloak_admin_client.update_user(
                keycloak_user_id,
                original_identity,
            )

        except Exception:
            logger.exception(
                "Fleet Manager identity rollback requires "
                "reconciliation: manager_id=%s user_id=%s",
                manager_id,
                keycloak_user_id,
            )

            raise HTTPException(
                status_code=503,
                detail=(
                    "Fleet API rejected the update, but "
                    "Keycloak rollback could not be confirmed."
                ),
            )

    # Σε 5xx δεν γνωρίζουμε αν το Fleet API πραγματοποίησε
    # κάποια αλλαγή πριν από την αποτυχία.
    #
    # Δεν κάνουμε rollback επειδή μπορεί να δημιουργήσουμε
    # μεγαλύτερη ασυνέπεια μεταξύ Fleet API και Keycloak.
    if fleet_response.status_code >= 500:
        raise HTTPException(
            status_code=503,
            detail=(
                "Fleet API update failed. "
                "Reconciliation may be required."
            ),
        )

    # Για validation/conflict errors επιστρέφουμε στον Admin
    # το πραγματικό error που έδωσε το Fleet API.
    try:
        error_detail = fleet_response.json().get(
            "detail",
            "Fleet Manager update rejected",
        )

    except ValueError:
        error_detail = "Fleet Manager update rejected"

    raise HTTPException(
        status_code=fleet_response.status_code,
        detail=error_detail,
    )

@app.post("/api/v1/admin/fleet-managers/{manager_id}/activate")
async def admin_activate_fleet_manager( manager_id: str, token_payload: dict = Depends(validate_access_token), ):
    """
    Επανενεργοποιεί τον Fleet Manager στο Fleet API και στο Keycloak.

    Αν προκύψει αβέβαιη έκβαση, ελέγχουμε την πραγματική
    κατάσταση πριν επιστρέψουμε αποτέλεσμα.
    """

    role_checker(token_payload, ADMIN_ROLES)

    # Ανακτούμε το Fleet Manager Profile από το Fleet API.
    # Το API Gateway δεν έχει άμεση πρόσβαση στη MongoDB.
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            managers_response = await client.get( f"{FLEET_API_URL}/fleet-managers" )
            managers_response.raise_for_status()

    except (httpx.RequestError, httpx.HTTPStatusError):
        logger.exception(
            "Could not retrieve Fleet Manager Profile: manager_id=%s",
            manager_id,
        )
        raise HTTPException( status_code=503, detail="Could not retrieve Fleet Manager Profile", )

    fleet_manager = next(
        (
            item
            for item in managers_response.json()
            if item.get("manager_id") == manager_id
        ),
        None,
    )

    if fleet_manager is None:
        raise HTTPException( status_code=404, detail="Fleet Manager not found", )

    keycloak_user_id = fleet_manager.get("keycloak_user_id")

    if not keycloak_user_id:
        raise HTTPException( status_code=409, detail="Fleet Manager has no linked Keycloak account", )
        # Επιβεβαιώνουμε ότι το συνδεδεμένο Keycloak identity
        # υπάρχει πριν αλλάξουμε το Fleet Manager Profile.
    try:
        keycloak_user = await keycloak_admin_client.get_user_by_id( keycloak_user_id )

    except Exception:
        logger.exception(
            "Could not retrieve Keycloak user: manager_id=%s",
            manager_id,
        )
        raise HTTPException( status_code=503, detail="Could not verify Keycloak account", )

    if keycloak_user is None:
        raise HTTPException( status_code=409, detail="Linked Keycloak account does not exist", )
    # Πρώτα ενεργοποιούμε το Fleet Manager Profile.
    # Αν χαθεί η HTTP απάντηση, ελέγχουμε την πραγματική
    # κατάσταση πριν θεωρήσουμε ότι η ενεργοποίηση απέτυχε.
    fleet_response = None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            fleet_response = await client.post( f"{FLEET_API_URL}/fleet-managers/{manager_id}/activate" )

    except httpx.RequestError:
        # Η απάντηση μπορεί να χάθηκε αφού το Fleet API
        # είχε ήδη ενεργοποιήσει το Fleet Manager Profile.
        logger.warning(
            "Fleet API Fleet Manager activation response lost: "
            "manager_id=%s",
            manager_id,
        )

        activation_confirmed = await check_fleet_manager_status( manager_id, "ACTIVE", )

        if activation_confirmed is not True:
            raise HTTPException( status_code=503, detail=( "Fleet Manager activation outcome is uncertain. Check the Fleet Manager Profile before retrying." ), )

    if fleet_response is not None:
        if fleet_response.status_code >= 500:
            raise HTTPException( status_code=503, detail="Fleet Manager activation outcome is uncertain", )

        if fleet_response.status_code != 200:
            raise HTTPException( status_code=fleet_response.status_code, detail=fleet_response.json().get( "detail", "Could not activate Fleet Manager Profile", ), )
        updated_fleet_manager = fleet_response.json()
    else:
        # Αν χάθηκε η απάντηση αλλά επιβεβαιώσαμε ότι ο Fleet Manager
        # έγινε ACTIVE, ανακτούμε το ενημερωμένο Profile.
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                profile_response = await client.get( f"{FLEET_API_URL}/fleet-managers" )

        except httpx.RequestError:
            raise HTTPException( status_code=503, detail="Could not retrieve activated Fleet Manager Profile", )

        if profile_response.status_code != 200:
            raise HTTPException( status_code=503, detail="Could not retrieve activated Fleet Manager Profile", )

        updated_fleet_manager = next(
            (
                item
                for item in profile_response.json()
                if item.get("manager_id") == manager_id
            ),
            None,
        )

        if updated_fleet_manager is None:
            raise HTTPException( status_code=503, detail="Activated Fleet Manager Profile could not be found", )
    # Πριν ενεργοποιήσουμε το Keycloak identity,
    # επιβεβαιώνουμε ότι το business Profile είναι πράγματι ACTIVE.
    if updated_fleet_manager.get("status") != "ACTIVE":
        raise HTTPException(
            status_code=503,
            detail="Fleet Manager activation could not be confirmed",
        )
    # Ενεργοποιούμε το Keycloak account μόνο αν είναι ανενεργό.
    # Αν χαθεί η απάντηση, ξαναδιαβάζουμε την πραγματική
    # κατάσταση του identity πριν θεωρήσουμε ότι απέτυχε.
    if keycloak_user.get("enabled") is not True:
        try:
            await keycloak_admin_client.set_user_enabled( keycloak_user_id, True, )

        except Exception:
            logger.exception(
                "Could not confirm Keycloak activation: "
                "manager_id=%s",
                manager_id,
            )

            try:
                current_user = ( await keycloak_admin_client.get_user_by_id( keycloak_user_id ) )

            except Exception:
                current_user = None

            if ( current_user is None or current_user.get("enabled") is not True ):
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Fleet Manager Profile is ACTIVE, but Keycloak "
                        "activation could not be confirmed. "
                        "Check both systems before retrying."
                    ),
                )
    logger.info( "Activated Fleet Manager in Fleet API and Keycloak: manager_id=%s", manager_id, )

    return updated_fleet_manager

@app.post("/api/v1/admin/fleet-managers/{manager_id}/deactivate")
async def admin_deactivate_fleet_manager( manager_id: str, token_payload: dict = Depends(validate_access_token),):
    """
    Απενεργοποιεί τον Fleet Manager στο Keycloak και στο Fleet API.

    Αν προκύψει αβέβαιη έκβαση, ελέγχουμε την πραγματική
    κατάσταση πριν θεωρήσουμε ότι η ενέργεια απέτυχε.
    """

    role_checker(token_payload, ADMIN_ROLES)

    # Ανακτούμε το Fleet Manager Profile από το Fleet API.
    # Το API Gateway δεν έχει άμεση πρόσβαση στη MongoDB.
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            managers_response = await client.get( f"{FLEET_API_URL}/fleet-managers" )
            managers_response.raise_for_status()

    except (httpx.RequestError, httpx.HTTPStatusError):
        logger.exception(
            "Could not retrieve Fleet Manager Profile: manager_id=%s",
            manager_id,
        )
        raise HTTPException( status_code=503, detail="Could not retrieve Fleet Manager Profile", )
    fleet_manager = next(
        (
            item
            for item in managers_response.json()
            if item.get("manager_id") == manager_id
        ),
        None,
    )

    if fleet_manager is None:
        raise HTTPException( status_code=404, detail="Fleet Manager not found", )

    keycloak_user_id = fleet_manager.get("keycloak_user_id")

    if not keycloak_user_id:
        raise HTTPException( status_code=409, detail="Fleet Manager has no linked Keycloak account", )

    # Διαβάζουμε την τρέχουσα κατάσταση του Keycloak identity
    # πριν κάνουμε οποιαδήποτε αλλαγή.
    try:
        keycloak_user = await keycloak_admin_client.get_user_by_id( keycloak_user_id )

    except Exception:
        logger.exception(
            "Could not retrieve Keycloak user: manager_id=%s",
            manager_id,
        )
        raise HTTPException( status_code=503, detail="Could not verify Keycloak account", )

    if keycloak_user is None:
        raise HTTPException( status_code=409, detail="Linked Keycloak account does not exist", )

    # Κρατάμε την πραγματική προηγούμενη κατάσταση του Keycloak account
    # ώστε να γνωρίζουμε αν χρειάζεται rollback σε περίπτωση αποτυχίας.
    originally_enabled = keycloak_user.get("enabled")

    if not isinstance(originally_enabled, bool):
        raise HTTPException( status_code=503, detail="Could not determine Keycloak account state", )
    # Απενεργοποιούμε πρώτα το Keycloak account ώστε ο Fleet Manager
    # να μην μπορεί να συνεχίσει να χρησιμοποιεί ενεργό identity.
    if originally_enabled:
        try:
            await keycloak_admin_client.set_user_enabled( keycloak_user_id, False, )

        except Exception:
            logger.exception(
                "Could not confirm Keycloak deactivation: "
                "manager_id=%s",
                manager_id,
            )

            # Η απάντηση μπορεί να χάθηκε αφού το Keycloak
            # είχε ήδη απενεργοποιήσει τον χρήστη.
            try:
                current_user = ( await keycloak_admin_client.get_user_by_id( keycloak_user_id ) )

            except Exception:
                current_user = None

            if ( current_user is None or current_user.get("enabled") is not False ):
                raise HTTPException( status_code=503, detail="Could not disable Fleet Manager Keycloak account", )
    # Αφού έχει απενεργοποιηθεί το Keycloak identity,
    # απενεργοποιούμε και το Fleet Manager Profile.
    fleet_response = None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            fleet_response = await client.post( f"{FLEET_API_URL}/fleet-managers/{manager_id}/deactivate" )

    except httpx.RequestError:
        # Η HTTP απάντηση μπορεί να χάθηκε αφού το Fleet API
        # είχε ήδη αλλάξει το Profile σε INACTIVE.
        logger.warning(
            "Fleet API Fleet Manager deactivation response lost: "
            "manager_id=%s",
            manager_id,
        )

        deactivation_confirmed = await check_fleet_manager_status(
            manager_id,
            "INACTIVE",
        )

        if deactivation_confirmed is not True:
            raise HTTPException( status_code=503, detail=( "Fleet Manager deactivation outcome is uncertain. Check the Fleet Manager Profile before retrying." ),)

    if fleet_response is not None:
        if fleet_response.status_code >= 500:
            raise HTTPException( status_code=503, detail="Fleet Manager deactivation outcome is uncertain", )

        if fleet_response.status_code != 200:
            # Το Fleet API απέρριψε οριστικά το deactivate.
            # Επαναφέρουμε το Keycloak μόνο αν ήταν αρχικά enabled.
            if originally_enabled:
                try:
                    await keycloak_admin_client.set_user_enabled( keycloak_user_id, True, )

                except Exception:
                    # Η απάντηση του Keycloak μπορεί να χάθηκε ενώ
                    # το account είχε ήδη επανενεργοποιηθεί.
                    try:
                        current_user = ( await keycloak_admin_client.get_user_by_id( keycloak_user_id ) )

                    except Exception:
                        current_user = None

                    if (current_user is None or current_user.get("enabled") is not True ):
                        logger.exception(
                            "Could not confirm Fleet Manager Keycloak rollback: "
                            "manager_id=%s",
                            manager_id,
                        )
                        raise HTTPException( status_code=503, detail=( "Fleet Manager deactivation failed and Keycloak rollback could not be confirmed" ),)

            raise HTTPException( status_code=fleet_response.status_code, detail=fleet_response.json().get( "detail", "Could not deactivate Fleet Manager Profile",),)

        updated_fleet_manager = fleet_response.json()

    else:
        # Αν χάθηκε η απάντηση αλλά επιβεβαιώσαμε ότι ο Fleet Manager
        # έγινε INACTIVE, ανακτούμε το ενημερωμένο Profile.
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                profile_response = await client.get( f"{FLEET_API_URL}/fleet-managers" )

        except httpx.RequestError:
            raise HTTPException( status_code=503, detail="Could not retrieve deactivated Fleet Manager Profile", )

        if profile_response.status_code != 200:
            raise HTTPException( status_code=503, detail="Could not retrieve deactivated Fleet Manager Profile", )

        updated_fleet_manager = next(
            (
                item
                for item in profile_response.json()
                if item.get("manager_id") == manager_id
            ),
            None,
        )

        if updated_fleet_manager is None:
            raise HTTPException( status_code=503, detail="Deactivated Fleet Manager Profile could not be found", )
    # Επιβεβαιώνουμε ότι το Fleet Manager Profile
    # βρίσκεται πράγματι σε κατάσταση INACTIVE.
    if updated_fleet_manager.get("status") != "INACTIVE":
        raise HTTPException( status_code=503, detail="Fleet Manager deactivation could not be confirmed", )
    # Τερματίζουμε τα υπάρχοντα Keycloak sessions ώστε ο Fleet Manager
    # να μην μπορεί να συνεχίσει να χρησιμοποιεί ήδη ενεργό session.
    try:
        await keycloak_admin_client.logout_user( keycloak_user_id )

    except Exception:
        logger.exception(
            "Could not logout Fleet Manager from Keycloak: "
            "manager_id=%s",
            manager_id,
        )
        raise HTTPException( status_code=503, detail=("Fleet Manager Profile is INACTIVE and Keycloak account is disabled, but logout could not be confirmed" ), )

    logger.info(
        "Deactivated Fleet Manager in Fleet API and Keycloak: "
        "manager_id=%s",
        manager_id,
    )

    return updated_fleet_manager

@app.delete("/api/v1/admin/fleet-managers/{manager_id}")
async def admin_delete_fleet_manager( manager_id: str, token_payload: dict = Depends(validate_access_token),):
    """
    Εκτελεί Hard Delete ενός Fleet Manager.

    Το Hard Delete:
    - διαγράφει οριστικά το Fleet Manager Profile από το Fleet API,
    - διαγράφει το αντίστοιχο Keycloak identity,
    - διατηρεί το audit history,
    - υποστηρίζει retry όταν το Fleet Manager Profile
      έχει ήδη διαγραφεί.

    Το Fleet API παραμένει υπεύθυνο για τα business δεδομένα.
    Το Keycloak παραμένει υπεύθυνο για το identity.
    """

    role_checker(token_payload, ADMIN_ROLES)

    keycloak_user_id = None
    fleet_manager_found = False

    # ---------------------------------------------------------
    # 1. Αναζητούμε πρώτα το υπάρχον Fleet Manager Profile.
    # ---------------------------------------------------------
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            managers_response = await client.get( f"{FLEET_API_URL}/fleet-managers" )

        managers_response.raise_for_status()

        existing_fleet_manager = next(
            (
                fleet_manager
                for fleet_manager in managers_response.json()
                if fleet_manager.get("manager_id") == manager_id
            ),
            None,
        )

    except httpx.RequestError:
        logger.exception(
            "Could not connect to Fleet API before "
            "Fleet Manager hard delete: manager_id=%s",
            manager_id,
        )

        raise HTTPException( status_code=503, detail="Fleet API is unavailable", )

    except httpx.HTTPStatusError:
        logger.exception(
            "Fleet API rejected Fleet Manager lookup before "
            "hard delete: manager_id=%s",
            manager_id,
        )

        raise HTTPException( status_code=503, detail="Could not verify Fleet Manager state", )

    if existing_fleet_manager is not None:
        fleet_manager_found = True

        keycloak_user_id = existing_fleet_manager.get( "keycloak_user_id" )

        if not keycloak_user_id:
            raise HTTPException( status_code=500, detail=( "Fleet Manager does not have a Keycloak user ID" ), )

        # Hard Delete επιτρέπεται μόνο αφού έχει προηγηθεί
        # η απενεργοποίηση του Fleet Manager.
        if existing_fleet_manager.get("status") != "INACTIVE":
            raise HTTPException( status_code=409, detail=( "Fleet Manager must be deactivated before hard delete" ), )

    else:
    # -----------------------------------------------------
    # 2. Το Profile μπορεί να έχει ήδη διαγραφεί από
    #    προηγούμενη μερικώς επιτυχημένη προσπάθεια.
    #
    #    Σε αυτή την περίπτωση ανακτούμε το Keycloak ID
    #    από το μόνιμο DELETED audit.
    # -----------------------------------------------------
        keycloak_user_id = ( await get_deleted_fleet_manager_keycloak_user_id( manager_id ) )

        if keycloak_user_id is None:
            raise HTTPException( status_code=404, detail="Fleet Manager not found", )
    # ---------------------------------------------------------
    # 3. Αν το Fleet Manager Profile υπάρχει ακόμη,
    #    εκτελούμε το business Hard Delete στο Fleet API.
    # ---------------------------------------------------------
    if fleet_manager_found:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                delete_response = await client.delete( f"{FLEET_API_URL}/fleet-managers/{manager_id}" )

            if 400 <= delete_response.status_code < 500:
                raise HTTPException( status_code=delete_response.status_code, detail=delete_response.text, )

            if delete_response.status_code >= 500:
                raise HTTPException( status_code=503, detail=( "Fleet API could not complete Fleet Manager hard delete" ), )

        except httpx.RequestError:
            # Το request μπορεί να ολοκληρώθηκε στο Fleet API,
            # αλλά να χάθηκε η HTTP απάντηση.
            deletion_confirmed = ( await check_fleet_manager_deleted_from_fleet( manager_id ) )

            if deletion_confirmed is not True:
                raise HTTPException( status_code=503, detail=( "Fleet Manager hard delete result could not be confirmed" ), )
    # ---------------------------------------------------------
    # 4. Πριν πειράξουμε το Keycloak επιβεβαιώνουμε ότι
    #    το Fleet Manager Profile πράγματι δεν υπάρχει πλέον.
    # ---------------------------------------------------------
    deletion_confirmed = ( await check_fleet_manager_deleted_from_fleet( manager_id ))

    if deletion_confirmed is not True:
        raise HTTPException( status_code=503, detail=( "Fleet Manager deletion from Fleet API " "could not be confirmed" ), )
    # ---------------------------------------------------------
    # 5. Διαγράφουμε το Keycloak identity.
    #
    #    Η delete_user() είναι idempotent:
    #    204 -> διαγράφηκε τώρα
    #    404 -> είχε ήδη διαγραφεί
    # ---------------------------------------------------------
    try:
        await keycloak_admin_client.delete_user( keycloak_user_id )

    except httpx.RequestError:
        # Μπορεί το Keycloak να εκτέλεσε το DELETE αλλά να
        # χάθηκε η απάντηση. Κάνουμε read-after-error verification.
        try:
            keycloak_user = ( await keycloak_admin_client.get_user_by_id( keycloak_user_id ) )

        except ( httpx.RequestError, httpx.HTTPStatusError, RuntimeError, ):
            logger.exception(
                "Could not verify Keycloak user after "
                "Fleet Manager hard delete error: "
                "manager_id=%s keycloak_user_id=%s",
                manager_id,
                keycloak_user_id,
            )

            raise HTTPException( status_code=503, detail=( "Fleet Manager Profile was deleted, but Keycloak deletion could not be confirmed" ), )

        if keycloak_user is not None:
            raise HTTPException( status_code=503, detail=( "Fleet Manager Profile was deleted, but Keycloak identity still exists" ), )

    except RuntimeError:
        # Για οποιαδήποτε επιβεβαιωμένη αποτυχία του Keycloak
        # ελέγχουμε ξανά την πραγματική τελική κατάσταση.
        try:
            keycloak_user = ( await keycloak_admin_client.get_user_by_id( keycloak_user_id ) )

        except ( httpx.RequestError, httpx.HTTPStatusError, RuntimeError, ):
            logger.exception(
                "Could not verify Keycloak user after "
                "Fleet Manager hard delete failure: "
                "manager_id=%s keycloak_user_id=%s",
                manager_id,
                keycloak_user_id,
            )

            raise HTTPException(status_code=503, detail=( "Fleet Manager Profile was deleted, but Keycloak deletion could not be confirmed" ), )

        if keycloak_user is not None:
            raise HTTPException( status_code=503, detail=( "Fleet Manager Profile was deleted, but Keycloak identity could not be deleted" ), )
    # ---------------------------------------------------------
    # 6. Τελική επιβεβαίωση του Keycloak state.
    # ---------------------------------------------------------
    try:
        remaining_keycloak_user = ( await keycloak_admin_client.get_user_by_id( keycloak_user_id ) )

    except ( httpx.RequestError, httpx.HTTPStatusError, RuntimeError, ):
        logger.exception(
            "Could not perform final Keycloak verification for "
            "Fleet Manager: manager_id=%s keycloak_user_id=%s",
            manager_id,
            keycloak_user_id,
        )

        raise HTTPException( status_code=503, detail=( "Fleet Manager Profile was deleted, but final Keycloak verification failed" ), )

    if remaining_keycloak_user is not None:
        raise HTTPException( status_code=503, detail=( "Fleet Manager Profile was deleted, but Keycloak identity still exists" ), )

    logger.info(
        "Hard deleted Fleet Manager: "
        "manager_id=%s keycloak_user_id=%s",
        manager_id,
        keycloak_user_id,
    )

    return { "message": "Fleet Manager permanently deleted", "manager_id": manager_id, }


@app.get("/api/v1/vehicles")
async def list_vehicles( request: Request, token_payload: dict = Depends(validate_access_token),):
    """
    Επιστρέφει τη λίστα Vehicles.

    Η διαχείριση Vehicles επιτρέπεται σε Admin και Fleet Manager.
    """

    role_checker( token_payload, VEHICLE_MANAGEMENT_ROLES, )

    target_url = f"{FLEET_API_URL}/vehicles"

    return await proxy_request(request, target_url)


@app.post("/api/v1/vehicles")
async def create_vehicle( request: Request,vehicle: VehicleCreateRequest, token_payload: dict = Depends(validate_access_token),):
    """
    Δημιουργεί νέο Vehicle.

    Admin:
    - μπορεί να δημιουργήσει Vehicle σε οποιοδήποτε Fleet.

    Fleet Manager:
    - μπορεί να δημιουργήσει Vehicle μόνο στο Fleet που διαχειρίζεται.
    """

    role_checker( token_payload, VEHICLE_MANAGEMENT_ROLES, )

    # Μετατρέπουμε το validated Pydantic model σε dictionary.
    # Το ίδιο dictionary χρησιμοποιείται τόσο για τους authorization
    # ελέγχους όσο και για την αποστολή στο Fleet API.
    vehicle_data = vehicle.model_dump()

    user_roles = token_payload.get( "realm_access", {}, ).get("roles", [])

    # Ο Admin δεν περιορίζεται σε συγκεκριμένο Fleet.
    if "admin" in user_roles:
        target_url = f"{FLEET_API_URL}/vehicles"
        return await proxy_request(request, target_url)

    # Από εδώ και κάτω ο χρήστης είναι Fleet Manager.
    manager_fleet_id = ( await get_authenticated_fleet_manager_fleet_id( token_payload ) )


    requested_fleet_id = vehicle_data.get("fleet_id")
    requested_driver_id = vehicle_data.get("driver_id")

    # Αν ο Fleet Manager δηλώσει συγκεκριμένο Fleet,
    # πρέπει υποχρεωτικά να είναι το Fleet που διαχειρίζεται.
    if ( requested_fleet_id is not None and requested_fleet_id != manager_fleet_id ):
        raise HTTPException( status_code=403, detail=( "Fleet Manager can create vehicles only in their own fleet"), )

    # Αν δεν υπάρχει Driver, συμπληρώνουμε εμείς το πραγματικό
    # fleet_id του Fleet Manager. Δεν βασιζόμαστε στον client.
    if requested_driver_id is None:
        vehicle_data["fleet_id"] = manager_fleet_id

    # Αν υπάρχει Driver, το Fleet API θα ελέγξει ότι ο Driver
    # υπάρχει και θα ορίσει το fleet_id από το Driver Profile.
    # Μετά όμως πρέπει να είναι πάλι το Fleet του συγκεκριμένου Manager.
    else:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                drivers_response = await client.get(
                    f"{FLEET_API_URL}/drivers"
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=503,
                detail="Fleet API unavailable",
            )

        if drivers_response.status_code != 200:
            raise HTTPException(
                status_code=503,
                detail="Could not retrieve Driver Profile",
            )

        driver = next(
            (
                item
                for item in drivers_response.json()
                if item.get("driver_id") == requested_driver_id
            ),
            None,
        )

        if driver is None:
            raise HTTPException(
                status_code=404,
                detail="Driver not found",
            )

        if driver.get("fleet_id") != manager_fleet_id:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Fleet Manager can assign only drivers "
                    "from their own fleet"
                ),
            )

        vehicle_data["fleet_id"] = manager_fleet_id

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{FLEET_API_URL}/vehicles",
                json=vehicle_data,
            )
    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Fleet API unavailable",
        )

    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=response.headers.get(
            "content-type",
            "application/json",
        ),
    )


@app.get("/api/v1/vehicles/{vehicle_id}")
async def get_vehicle( request: Request, vehicle_id: str, token_payload: dict = Depends(validate_access_token),):
    """
    Επιστρέφει συγκεκριμένο Vehicle.
    """

    role_checker( token_payload, VEHICLE_MANAGEMENT_ROLES, )

    target_url = f"{FLEET_API_URL}/vehicles/{vehicle_id}"

    return await proxy_request(request, target_url)


@app.patch("/api/v1/vehicles/{vehicle_id}")
async def update_vehicle( request: Request, vehicle_id: str,vehicle_update: VehicleUpdateRequest, token_payload: dict = Depends(validate_access_token),):
    """
    Ενημερώνει Vehicle.

    Admin:
    - μπορεί να ενημερώσει οποιοδήποτε Vehicle.

    Fleet Manager:
    - μπορεί να ενημερώσει μόνο Vehicle του δικού του Fleet,
    - δεν μπορεί να μεταφέρει Vehicle σε διαφορετικό Fleet,
    - δεν μπορεί να αναθέσει Driver άλλου Fleet.
    """

    role_checker( token_payload, VEHICLE_MANAGEMENT_ROLES, )
    # Κρατάμε μόνο τα πεδία που έστειλε πραγματικά ο client.
    # Αυτό είναι απαραίτητο για PATCH ώστε ένα πεδίο που δεν στάλθηκε
    # να μην αντιμετωπιστεί σαν να ζητήθηκε να γίνει null.
    update_data = vehicle_update.model_dump(exclude_unset=True)

    user_roles = token_payload.get( "realm_access", {}, ).get("roles", [])

    # Ο Admin προωθεί κανονικά το PATCH στο Fleet API.
    if "admin" in user_roles:
        target_url = f"{FLEET_API_URL}/vehicles/{vehicle_id}"
        return await proxy_request(request, target_url)

    manager_fleet_id = ( await get_authenticated_fleet_manager_fleet_id( token_payload ) )

    # Πρώτα ελέγχουμε σε ποιο Fleet ανήκει πραγματικά
    # το Vehicle που επιχειρεί να αλλάξει ο Fleet Manager.
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            vehicle_response = await client.get( f"{FLEET_API_URL}/vehicles/{vehicle_id}" )
    except httpx.RequestError:
        raise HTTPException( status_code=503, detail="Fleet API unavailable", )

    if vehicle_response.status_code == 404:
        raise HTTPException( status_code=404, detail="Vehicle not found", )

    if vehicle_response.status_code != 200:
        raise HTTPException( status_code=vehicle_response.status_code, detail="Could not retrieve Vehicle", )

    existing_vehicle = vehicle_response.json()

    if existing_vehicle.get("fleet_id") != manager_fleet_id:
        raise HTTPException( status_code=403, detail=( "Fleet Manager can manage vehicles only in their own fleet" ), )

    # Ο Fleet Manager δεν μπορεί να μεταφέρει το Vehicle
    # έξω από το Fleet που διαχειρίζεται.
    if ( "fleet_id" in update_data and update_data["fleet_id"] != manager_fleet_id ):
        raise HTTPException( status_code=403, detail=( "Fleet Manager cannot move a vehicle to another fleet" ), )

    requested_driver_id = update_data.get("driver_id")

    # driver_id=None σημαίνει unassign και επιτρέπεται.
    if ( "driver_id" in update_data and requested_driver_id is not None ):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                drivers_response = await client.get( f"{FLEET_API_URL}/drivers" )
        except httpx.RequestError:
            raise HTTPException( status_code=503, detail="Fleet API unavailable", )

        if drivers_response.status_code != 200:
            raise HTTPException( status_code=503, detail="Could not retrieve Driver Profile", )

        driver = next(
            (
                item
                for item in drivers_response.json()
                if item.get("driver_id") == requested_driver_id ),
            None,
        )

        if driver is None:
            raise HTTPException( status_code=404, detail="Driver not found", )

        if driver.get("fleet_id") != manager_fleet_id:
            raise HTTPException( status_code=403, detail=( "Fleet Manager can assign only drivers from their own fleet" ), )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.patch( f"{FLEET_API_URL}/vehicles/{vehicle_id}", json=update_data, )
    except httpx.RequestError:
        raise HTTPException( status_code=503, detail="Fleet API unavailable", )

    return Response( content=response.content, status_code=response.status_code, media_type=response.headers.get( "content-type", "application/json", ), )

@app.post("/api/v1/vehicles/{vehicle_id}/activate")
async def activate_vehicle( request: Request, vehicle_id: str, token_payload: dict = Depends(validate_access_token),):
    """
    Ενεργοποιεί Vehicle.

    Admin:
    - οποιοδήποτε Vehicle.

    Fleet Manager:
    - μόνο Vehicle του Fleet που διαχειρίζεται.
    """

    role_checker( token_payload, VEHICLE_MANAGEMENT_ROLES, )

    user_roles = token_payload.get( "realm_access", {}, ).get("roles", [])

    if "admin" not in user_roles:
        manager_fleet_id = ( await get_authenticated_fleet_manager_fleet_id( token_payload ) )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                vehicle_response = await client.get( f"{FLEET_API_URL}/vehicles/{vehicle_id}" )
        except httpx.RequestError:
            raise HTTPException( status_code=503, detail="Fleet API unavailable", )

        if vehicle_response.status_code == 404:
            raise HTTPException( status_code=404, detail="Vehicle not found", )

        if vehicle_response.status_code != 200:
            raise HTTPException( status_code=vehicle_response.status_code, detail="Could not retrieve Vehicle", )

        if ( vehicle_response.json().get("fleet_id") != manager_fleet_id ):
            raise HTTPException( status_code=403, detail=( "Fleet Manager can manage vehicles only in their own fleet" ), )

    target_url = ( f"{FLEET_API_URL}/vehicles/{vehicle_id}/activate" )

    return await proxy_request(request, target_url)

@app.post("/api/v1/vehicles/{vehicle_id}/deactivate")
async def deactivate_vehicle( request: Request, vehicle_id: str, token_payload: dict = Depends(validate_access_token),):
    """
    Απενεργοποιεί Vehicle.

    Admin:
    - οποιοδήποτε Vehicle.

    Fleet Manager:
    - μόνο Vehicle του Fleet που διαχειρίζεται.
    """

    role_checker( token_payload, VEHICLE_MANAGEMENT_ROLES, )

    user_roles = token_payload.get( "realm_access", {}, ).get("roles", [])

    if "admin" not in user_roles:
        manager_fleet_id = ( await get_authenticated_fleet_manager_fleet_id( token_payload ) )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                vehicle_response = await client.get( f"{FLEET_API_URL}/vehicles/{vehicle_id}" )
        except httpx.RequestError:
            raise HTTPException( status_code=503,detail="Fleet API unavailable", )

        if vehicle_response.status_code == 404:
            raise HTTPException( status_code=404, detail="Vehicle not found", )

        if vehicle_response.status_code != 200:
            raise HTTPException( status_code=vehicle_response.status_code, detail="Could not retrieve Vehicle", )

        if ( vehicle_response.json().get("fleet_id") != manager_fleet_id ):
            raise HTTPException( status_code=403, detail=( "Fleet Manager can manage vehicles only in their own fleet" ), )

    target_url = ( f"{FLEET_API_URL}/vehicles/{vehicle_id}/deactivate" )

    return await proxy_request(request, target_url)

@app.delete("/api/v1/vehicles/{vehicle_id}")
async def delete_vehicle( request: Request, vehicle_id: str, token_payload: dict = Depends(validate_access_token),):
    """
    Εκτελεί permanent Hard Delete ενός Vehicle.

    Μόνο ο Admin επιτρέπεται να εκτελέσει αυτή την ενέργεια.
    Το Fleet API ελέγχει επιπλέον ότι το Vehicle είναι INACTIVE.
    """

    role_checker( token_payload, ADMIN_ROLES, )

    target_url = f"{FLEET_API_URL}/vehicles/{vehicle_id}"

    return await proxy_request(request, target_url)

# @app.api_route( "/api/v1/vehicles", methods=["GET", "POST"],)
# async def vehicles_collection( request: Request, token_payload: dict = Depends(validate_access_token), ):
#     """
#     Προωθεί requests συλλογής οχημάτων προς το Fleet API.
#
#     GET:
#     - Επιστρέφει τη λίστα οχημάτων.
#
#     POST:
#     - Δημιουργεί νέο όχημα μέσω Fleet API.
#     - Το Fleet API παραμένει owner της MongoDB και των vehicle events.
#     """
#     role_checker( token_payload, VEHICLE_MANAGEMENT_ROLES,)
#
#     logger.info("========= Decoded JWT payload %s ============\n", token_payload)
#
#     target_url = f"{FLEET_API_URL}/vehicles"
#
#     return await proxy_request(request, target_url)
#
# @app.api_route( "/api/v1/vehicles/{vehicle_id}", methods=["GET", "PUT", "PATCH", "DELETE"], )
# async def vehicle_item(request: Request, vehicle_id: str, token_payload: dict = Depends(validate_access_token), ):
#     """
#     Προωθεί requests συγκεκριμένου οχήματος προς το Fleet API.
#
#     Το route μένει generic ώστε να μπορεί να υποστηρίξει και μελλοντικά
#     PUT/PATCH/DELETE όταν προστεθούν στο Fleet API.
#     """
#
#     role_checker( token_payload, VEHICLE_MANAGEMENT_ROLES,)
#
#     target_url = f"{FLEET_API_URL}/vehicles/{vehicle_id}"
#
#     return await proxy_request(request, target_url)

@app.api_route( "/api/v1/vehicles/{imei}/latest-position", methods=["GET"], )
async def get_vehicle_latest_position(request: Request, imei: str, token_payload: dict = Depends(validate_access_token), ):
    """
    Προωθεί request για την τελευταία γνωστή θέση οχήματος
    προς το Live Tracking Service.

    Το API Gateway δεν διαβάζει Redis.
    Η Redis ανήκει αποκλειστικά στο Live Tracking Service.
    """

    role_checker( token_payload, LIVE_TRACKING_ROLES, )

    target_url = ( f"{LIVE_TRACKING_SERVICE_URL}"  f"/vehicles/{imei}/latest-position" )

    return await proxy_request(request, target_url)

@app.get("/api/v1/drivers/me/vehicles")
async def get_my_vehicles(request: Request,token_payload: dict = Depends(validate_access_token), ):
    """
    Επιστρέφει τα οχήματα που ανήκουν στον authenticated driver.

    Το frontend δεν στέλνει ούτε driver_id ούτε Keycloak user id.
    Το API Gateway παίρνει το "sub" απευθείας από το έγκυρο JWT
    και το χρησιμοποιεί για να ζητήσει τα σωστά οχήματα από το Fleet API.
    """

    # Επιτρέπουμε πρόσβαση στους ρόλους που μπορούν
    # να χρησιμοποιούν λειτουργίες live tracking.
    role_checker( token_payload, LIVE_TRACKING_ROLES,)

    # Το "sub" είναι το σταθερό identifier του χρήστη στο Keycloak.
    # Δεν το εμπιστευόμαστε από το frontend αλλά το παίρνουμε
    # αποκλειστικά από το ήδη validated JWT.
    keycloak_user_id = token_payload.get("sub")

    if not keycloak_user_id:
        raise HTTPException( status_code=401, detail="Token does not contain user identifier", )

    # Το Fleet API γνωρίζει τη σχέση:
    # Keycloak user -> Driver Profile -> Vehicles.
    target_url = ( f"{FLEET_API_URL}/drivers/by-keycloak-user/{keycloak_user_id}/vehicles")

    return await proxy_request(request, target_url)

@app.get("/api/v1/drivers/me")
async def get_driver_profile(request: Request,token_payload: dict = Depends(validate_access_token), ):

    role_checker( token_payload, LIVE_TRACKING_ROLES,)
    keycloak_user_id = token_payload.get("sub")
    if not keycloak_user_id:
        raise HTTPException(
            status_code=401,
            detail="Token does not contain user identifier",
        )

    target_url = (
        f"{FLEET_API_URL}"
        f"/drivers/by-keycloak-user/{keycloak_user_id}"
    )

    return await proxy_request(request, target_url)

@app.get("/api/v1/fleet-managers/me")
async def get_fleet_manager_profile( request: Request, token_payload: dict = Depends(validate_access_token), ):
    """
    Επιστρέφει το Fleet Manager Profile του authenticated χρήστη.

    Το frontend δεν χρειάζεται να γνωρίζει ή να στέλνει
    το Keycloak user id. Το API Gateway παίρνει το "sub"
    απευθείας από το ήδη validated JWT.
    """

    # Το endpoint αφορά χρήστες που μπορούν
    # να διαχειρίζονται δεδομένα στόλου.
    role_checker( token_payload, VEHICLE_MANAGEMENT_ROLES, )

    # Παίρνουμε το σταθερό Keycloak user id
    # αποκλειστικά από το validated access token.
    keycloak_user_id = token_payload.get("sub")

    if not keycloak_user_id:
        raise HTTPException( status_code=401, detail="Token does not contain user identifier", )

    # Το Fleet API γνωρίζει τη σχέση:
    # Keycloak user -> Fleet Manager Profile.
    target_url = ( f"{FLEET_API_URL}/fleet-managers/by-keycloak-user/{keycloak_user_id}"
    )

    return await proxy_request(request, target_url)

@app.get("/api/v1/fleet-managers/me/vehicles")
async def get_my_fleet_vehicles( request: Request, token_payload: dict = Depends(validate_access_token), ):
    """
    Επιστρέφει όλα τα vehicles του fleet
    που διαχειρίζεται ο authenticated Fleet Manager.
    """

    role_checker( token_payload, VEHICLE_MANAGEMENT_ROLES, )

    keycloak_user_id = token_payload.get("sub")

    if not keycloak_user_id:
        raise HTTPException( status_code=401, detail="Token does not contain user identifier", )

    target_url = ( f"{FLEET_API_URL}/fleet-managers/by-keycloak-user/{keycloak_user_id}/vehicles" )

    return await proxy_request(request, target_url)

@app.get("/api/v1/fleet-managers/me/drivers")
async def get_my_fleet_drivers( request: Request, token_payload: dict = Depends(validate_access_token), ):
    """
    Επιστρέφει όλους τους drivers του fleet
    που διαχειρίζεται ο authenticated Fleet Manager.
    """

    role_checker( token_payload, VEHICLE_MANAGEMENT_ROLES, )

    keycloak_user_id = token_payload.get("sub")

    if not keycloak_user_id:
        raise HTTPException( status_code=401, detail="Token does not contain user identifier", )

    target_url = ( f"{FLEET_API_URL}/fleet-managers/by-keycloak-user/{keycloak_user_id}/drivers"
    )

    return await proxy_request(request, target_url)



# ---------------------------------------------------------
# Fleet Management - Admin Only
# ---------------------------------------------------------

@app.api_route( "/api/v1/fleets", methods=["GET", "POST"],)
async def fleets_collection( request: Request, token_payload: dict = Depends(validate_access_token),):
    """
    Επιτρέπει στον Admin να δημιουργεί Fleet
    και να βλέπει τη λίστα όλων των Fleets.

    Η αποθήκευση και η business λογική
    παραμένουν αποκλειστικά στο Fleet API.
    """

    # Μόνο ο Admin έχει πρόσβαση στη διαχείριση Fleets.
    role_checker(token_payload, ADMIN_ROLES)

    target_url = f"{FLEET_API_URL}/fleets"

    return await proxy_request(request, target_url)


@app.api_route( "/api/v1/fleets/{fleet_id}", methods=["GET", "PATCH", "DELETE"],)
async def fleet_item( request: Request, fleet_id: str, token_payload: dict = Depends(validate_access_token),):
    """
    Επιτρέπει στον Admin να διαβάζει, να ενημερώνει
    και να διαγράφει ένα συγκεκριμένο Fleet.

    Το fleet_id δεν μπορεί να αλλάξει μέσω PATCH.

    Η διαγραφή απορρίπτεται από το Fleet API όταν
    υπάρχουν συνδεδεμένοι Fleet Managers, Drivers
    ή Vehicles.
    """

    # Ελέγχουμε τον ρόλο πριν προωθήσουμε το request.
    role_checker(token_payload, ADMIN_ROLES)

    target_url = f"{FLEET_API_URL}/fleets/{fleet_id}"

    return await proxy_request(request, target_url)