"""
Fleet API Service.

Σκοπός:
Η υπηρεσία αυτή διαχειρίζεται τα βασικά δεδομένα του στόλου, όπως οχήματα,
πινακίδες και IMEI συσκευών GPS.

Στην παρούσα φάση υλοποιούμε μόνο CRUD για vehicles.

Ροή:
HTTP Client / API Gateway
    ↓
Fleet API
    ↓
MongoDB collection: vehicles
"""

import os
import logging
import time

from typing import Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pymongo import MongoClient
from bson import ObjectId
from datetime import date
from pydantic import BaseModel, EmailStr
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from kafka_producer import FleetEventProducer


# Ρυθμίζουμε το βασικό logging του Fleet API.
logging.basicConfig(level=logging.INFO)

# Δημιουργούμε logger για την καταγραφή των ενεργειών του service.
logger = logging.getLogger(__name__)

# Δημιουργούμε Kafka producer για fleet events.
# Το Fleet API δεν καλεί άλλα services απευθείας.
# Απλώς δημοσιεύει γεγονότα στο Kafka.
fleet_event_producer = FleetEventProducer()

# Δημιουργούμε FastAPI εφαρμογή.
# Το FastAPI θα μας δώσει αυτόματα και Swagger UI στο /docs.
app = FastAPI(
    title="Fleet API Service",
    description="Service για διαχείριση στόλου οχημάτων.",
    version="0.1.0",
)


# -------------------------
# MongoDB Configuration
# -------------------------

# Διαβάζουμε τις ρυθμίσεις από environment variables.
# Έτσι το service μπορεί να τρέχει εύκολα μέσα από Docker Compose.
MONGO_HOST = os.getenv("MONGO_HOST", "mongodb")
MONGO_PORT = os.getenv("MONGO_PORT", "27017")
MONGO_USER = os.getenv("MONGO_USER", "fleet_admin")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD", "fleet_password")
MONGO_DB = os.getenv("MONGO_DB", "fleet_tracking")

MONGO_URI = (
    f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
    f"@{MONGO_HOST}:{MONGO_PORT}/"
)

mongo_client = MongoClient(MONGO_URI)

# Επιλέγουμε τη βάση και το collection όπου θα αποθηκεύονται τα οχήματα.
database = mongo_client[MONGO_DB]
vehicles_collection = database["vehicles"]

# Το collection drivers αποθηκεύει τα business δεδομένα των οδηγών.
# Το Keycloak παραμένει υπεύθυνο μόνο για authentication και identity.
drivers_collection = database["drivers"]

# Εξασφαλίζουμε ότι κάθε χρήστης του Keycloak αντιστοιχεί
# σε ένα μόνο Driver Profile στη MongoDB.
#
# Ο μοναδικός δείκτης προστατεύει και από ταυτόχρονες αιτήσεις,
# όπου δύο διαδικασίες μπορεί να προσπαθήσουν να δημιουργήσουν
# προφίλ για το ίδιο keycloak_user_id.
#
# Αν ο δείκτης υπάρχει ήδη, η MongoDB δεν τον δημιουργεί ξανά.
drivers_collection.create_index( [("keycloak_user_id", 1)], unique=True, name="uq_drivers_keycloak_user_id",)

# Εξασφαλίζουμε ότι κάθε Driver έχει μοναδικό business identifier.
#
# Ο δείκτης προστατεύει από διπλές εγγραφές ακόμη και όταν
# δύο αιτήσεις δημιουργίας φτάσουν ταυτόχρονα.
# Αν υπάρχει ήδη, η MongoDB δεν τον δημιουργεί ξανά.
drivers_collection.create_index( [("driver_id", 1)], unique=True, name="uq_drivers_driver_id", )

# Αποθηκεύει τα business profiles των Fleet Managers.
# Το Keycloak παραμένει υπεύθυνο για authentication και roles,
# ενώ εδώ κρατάμε τη σχέση του manager με το fleet που διαχειρίζεται.
fleet_managers_collection = database["fleet_managers"]

# Εξασφαλίζουμε ότι κάθε Fleet Manager έχει μοναδικό
# business identifier μέσα στο σύστημα.
fleet_managers_collection.create_index( [("manager_id", 1)], unique=True, name="uq_fleet_managers_manager_id",)

# Κάθε Keycloak identity μπορεί να αντιστοιχεί
# σε ένα μόνο Fleet Manager Profile.
#
# Ο μοναδικός δείκτης προστατεύει και από ταυτόχρονες αιτήσεις
# δημιουργίας που μπορεί να περάσουν τους αρχικούς find_one ελέγχους.
fleet_managers_collection.create_index( [("keycloak_user_id", 1)], unique=True, name="uq_fleet_managers_keycloak_user_id",)


# Αποθηκεύει τα business δεδομένα των fleets.
# Κάθε fleet αποτελεί την κεντρική οντότητα που συνδέει
# τους Fleet Managers, τους Drivers και τα Vehicles του ίδιου στόλου.
fleets_collection = database["fleets"]

# Η συλλογή audit_logs κρατάει μόνιμο ιστορικό των business αλλαγών
# που γίνονται σε Fleets, Vehicles και Drivers.
#
# Οι εγγραφές του audit trail δεν χρησιμοποιούνται ως η τρέχουσα κατάσταση
# μιας οντότητας. Χρησιμοποιούνται για ιστορικό, έλεγχο αλλαγών και
# μελλοντικό trace-back σχέσεων Driver → Vehicle → Fleet.
audit_logs_collection = database["audit_logs"]

# -------------------------
# Data Models
# -------------------------

class VehicleCreate(BaseModel):
    """
    Μοντέλο που χρησιμοποιείται όταν δημιουργείται νέο όχημα.
    Το FastAPI χρησιμοποιεί αυτό το μοντέλο για validation
    των δεδομένων που έρχονται από το API.
    """
    plate_number: str
    brand: str | None = None
    model: str | None = None
    year: int | None = None
    device_imei: str
    driver_id: str | None = None
    fleet_id: str | None = None
   # status: str = "ACTIVE"

class VehicleResponse(VehicleCreate):
    # Το id είναι το MongoDB ObjectId σε μορφή string.
    id: str
    # Το status επιστρέφεται στον client, παρόλο που δεν επιτρέπεται
    # να οριστεί κατά τη δημιουργία του Vehicle.
    status: str

class VehicleUpdate(BaseModel):
    """
    Μοντέλο για μερική ενημέρωση οχήματος.
    Όλα τα πεδία είναι optional, ώστε ο client να αλλάζει μόνο ό,τι χρειάζεται.
    """
    plate_number: str | None = None
    brand: str | None = None
    model: str | None = None
    year: int | None = None
    device_imei: str | None = None
    driver_id: str | None = None
    fleet_id: str | None = None
    #status: str | None = None

class DriverCreate(BaseModel):
    """
    Μοντέλο για τη δημιουργία ενός Driver Profile.

    Το keycloak_user_id αποθηκεύει το "sub" του Keycloak JWT
    και συνδέει τον λογαριασμό του Keycloak με τον business driver.
    """

    # Business identifier του οδηγού μέσα στο Smart Fleet σύστημα.
    driver_id: str

    # Σταθερό identifier του χρήστη στο Keycloak.
    # Αντιστοιχεί στο claim "sub" του JWT.
    keycloak_user_id: str

    # Βασικά προσωπικά στοιχεία.
    first_name: str
    last_name: str
    date_of_birth: date | None = None

    # Αριθμός δελτίου ταυτότητας.
    identity_card_number: str | None = None

    # Αριθμός Φορολογικού Μητρώου (ΑΦΜ).
    tax_id: str | None = None

    # Στοιχεία επικοινωνίας.
    phone_number: str | None = None
    email: EmailStr | None = None

    # Στοιχεία άδειας οδήγησης.
    license_number: str | None = None
    license_category: str | None = None
    license_expiry_date: date | None = None

    # Ημερομηνία πρόσληψης του οδηγού.
    hire_date: date | None = None

    # Συσχέτιση με τον στόλο και το τμήμα.
    fleet_id: str | None = None
    department_id: str | None = None

    # Κατάσταση του οδηγού μέσα στο σύστημα.
    status: str = "ACTIVE"

class DriverResponse(DriverCreate):
    # Το MongoDB ObjectId επιστρέφεται από το API ως string.
    id: str

class DriverUpdate(BaseModel):
    """
    Μοντέλο για μερική ενημέρωση ενός Driver Profile.

    Όλα τα πεδία είναι προαιρετικά, επειδή το PATCH επιτρέπει
    στον client να στείλει μόνο τα στοιχεία που θέλει να αλλάξει.

    Το driver_id και το keycloak_user_id δεν αλλάζουν μέσω PATCH,
    επειδή χρησιμοποιούνται ως σταθερά identifiers του Driver.
    """

    # Βασικά προσωπικά στοιχεία.
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None

    # Αριθμός δελτίου ταυτότητας.
    identity_card_number: str | None = None

    # Αριθμός Φορολογικού Μητρώου (ΑΦΜ).
    tax_id: str | None = None

    # Στοιχεία επικοινωνίας.
    phone_number: str | None = None
    email: EmailStr | None = None

    # Στοιχεία άδειας οδήγησης.
    license_number: str | None = None
    license_category: str | None = None
    license_expiry_date: date | None = None

    # Ημερομηνία πρόσληψης του οδηγού.
    hire_date: date | None = None

    # Συσχέτιση με Fleet και Department.
    #
    # Το fleet_id επιτρέπεται να γίνει None.
    # Σε αυτή την περίπτωση ο Driver αφαιρείται από το Fleet
    # και αποδεσμεύονται όλα τα Vehicles που του έχουν ανατεθεί.
    fleet_id: str | None = None
    department_id: str | None = None

    # Κατάσταση του Driver μέσα στο σύστημα.
    # status: str | None = None

class FleetManagerCreate(BaseModel):
    """
    Business profile για έναν Fleet Manager.

    Το keycloak_user_id αντιστοιχεί στο claim "sub" του Keycloak JWT.
    Το fleet_id καθορίζει ποιο fleet διαχειρίζεται ο συγκεκριμένος manager.
    """

    # Business identifier του Fleet Manager.
    manager_id: str

    # Σταθερό identifier του χρήστη στο Keycloak.
    keycloak_user_id: str

    # Βασικά προσωπικά στοιχεία.
    first_name: str
    last_name: str
    date_of_birth: date | None = None

    # Στοιχεία ταυτοποίησης.
    identity_card_number: str | None = None
    tax_id: str | None = None

    # Στοιχεία επικοινωνίας.
    phone_number: str | None = None
    email: EmailStr | None = None

    # Συσχέτιση με το fleet και το department.
    fleet_id: str
    department_id: str | None = None

    # Στοιχεία απασχόλησης.
    hire_date: date | None = None

    # Κατάσταση του Fleet Manager.
    status: str = "ACTIVE"

class FleetManagerResponse(FleetManagerCreate):
    # Το MongoDB ObjectId επιστρέφεται ως string στο API.
    id: str

class FleetManagerUpdate(BaseModel):
    """
    Μοντέλο για μερική ενημέρωση ενός Fleet Manager Profile.

    Όλα τα πεδία είναι προαιρετικά, επειδή το PATCH επιτρέπει
    στον client να στείλει μόνο τα στοιχεία που θέλει να αλλάξει.

    Το manager_id και το keycloak_user_id δεν αλλάζουν μέσω PATCH,
    επειδή χρησιμοποιούνται ως σταθερά identifiers του Fleet Manager.
    """

    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    identity_card_number: str | None = None
    tax_id: str | None = None
    phone_number: str | None = None
    email: EmailStr | None = None

    fleet_id: str | None = None
    department_id: str | None = None

    hire_date: date | None = None
    #status: str | None = None

class BaseLocation(BaseModel):
    """
    Αντιπροσωπεύει τη βασική τοποθεσία ενός fleet.

    Κρατάμε τόσο τα στοιχεία διεύθυνσης όσο και τις γεωγραφικές
    συντεταγμένες, ώστε η ίδια πληροφορία να μπορεί αργότερα
    να χρησιμοποιηθεί από το frontend, το GIS Service
    και το Route Optimizer.
    """

    # Αναγνωρίσιμο όνομα της βάσης, π.χ. "Athens Depot".
    name: str

    # Ταχυδρομικά στοιχεία της βασικής τοποθεσίας.
    address: str | None = None
    city: str | None = None
    postal_code: str | None = None

    # Γεωγραφικές συντεταγμένες της βάσης.
    # Οι περιορισμοί προστατεύουν από μη έγκυρες τιμές.
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

class FleetCreate(BaseModel):
    """
    Μοντέλο για τη δημιουργία ενός fleet της εταιρείας.

    Το fleet_id είναι το σταθερό business identifier που χρησιμοποιείται
    για τη συσχέτιση του fleet με Fleet Managers, Drivers και Vehicles.
    """

    # Business identifier του fleet, π.χ. "fleet-001".
    fleet_id: str

    # Ανθρώπινα αναγνώσιμο όνομα και προαιρετική περιγραφή.
    name: str
    description: str | None = None

    # Κεντρική βάση λειτουργίας του συγκεκριμένου fleet.
    base_location: BaseLocation

    # Επιτρέπει να απενεργοποιούμε ένα fleet χωρίς να διαγράφουμε
    # το ιστορικό ή τις υπάρχουσες συσχετίσεις του.
    status: str = "ACTIVE"

class FleetUpdate(BaseModel):
    """
    Μοντέλο για μερική ενημέρωση ενός fleet.

    Επιτρέπει και την αλλαγή του fleet_id. Σε αυτή την περίπτωση
    το Fleet API πρέπει να ενημερώσει με ασφαλή τρόπο όλες τις
    σχετικές business οντότητες που χρησιμοποιούν το παλιό fleet_id.
    """

    fleet_id: str | None = None
    name: str | None = None
    description: str | None = None
    base_location: BaseLocation | None = None
    status: str | None = None

class FleetResponse(FleetCreate):
    """
    Μοντέλο που επιστρέφεται από το Fleet API.

    Εκτός από τα business δεδομένα περιλαμβάνει το MongoDB id
    και τα timestamps δημιουργίας και τελευταίας ενημέρωσης.
    """

    # MongoDB ObjectId σε μορφή string.
    id: str

    # Τα timestamps δημιουργούνται από το backend και δεν τα στέλνει ο client.
    created_at: datetime
    updated_at: datetime

class AuditChange(BaseModel):
    """
    Περιγράφει την αλλαγή μιας συγκεκριμένης ιδιότητας.

    Κρατάμε τόσο την προηγούμενη όσο και τη νέα τιμή, ώστε αργότερα
    να μπορούμε να ανακατασκευάσουμε τι ακριβώς άλλαξε.
    """

    from_value: object | None = None
    to_value: object | None = None

class AuditRelatedEntities(BaseModel):
    """
    Κρατάει τις business οντότητες που σχετίζονται με την αλλαγή.

    Τα πεδία είναι προαιρετικά επειδή δεν συμμετέχουν όλες οι οντότητες
    σε κάθε audit event. Για παράδειγμα, ένα Fleet update μπορεί να μην
    αφορά συγκεκριμένο Driver ή Vehicle.
    """

    fleet_id: str | None = None
    vehicle_id: str | None = None
    driver_id: str | None = None
    manager_id: str | None = None
    plate_number: str | None = None

class AuditLogCreate(BaseModel):
    """
    Μοντέλο για τη δημιουργία μιας εγγραφής στο audit trail.

    Το description προορίζεται για γρήγορη ανάγνωση από τον χρήστη,
    ενώ τα changes και related_entities κρατούν δομημένα δεδομένα
    για μελλοντικά queries και historical trace-back.
    """

    entity_type: str
    entity_id: str
    action: str
    description: str
    related_entities: AuditRelatedEntities
    changes: dict[str, AuditChange] = Field(default_factory=dict)
    performed_by: str | None = None

class AuditLogResponse(AuditLogCreate):
    """
    Αναπαριστά μία αποθηκευμένη εγγραφή audit.

    Το timestamp δημιουργείται από το backend τη στιγμή που
    πραγματοποιείται η business αλλαγή.
    """

    id: str
    timestamp: datetime


# -------------------------
# Helper Functions
# -------------------------

def vehicle_document_to_response(document: dict) -> VehicleResponse:
    # Μετατρέπουμε ένα MongoDB document σε API response.
    # Το MongoDB χρησιμοποιεί _id, ενώ στο API θέλουμε απλά id.
    return VehicleResponse(
        id=str(document["_id"]),
        plate_number=document["plate_number"],
        brand=document.get("brand"),
        model=document.get("model"),
        year=document.get("year"),
        device_imei=document["device_imei"],
        driver_id=document.get("driver_id"),
        fleet_id=document.get("fleet_id"),
        status=document.get("status", "ACTIVE"),
    )

def driver_document_to_response(document: dict) -> DriverResponse:
    """
    Μετατρέπει ένα MongoDB driver document σε DriverResponse.

    Το MongoDB χρησιμοποιεί το πεδίο _id,
    ενώ στο API επιστρέφουμε το ίδιο identifier ως id.
    """

    return DriverResponse(
        id=str(document["_id"]),
        driver_id=document["driver_id"],
        keycloak_user_id=document["keycloak_user_id"],
        first_name=document["first_name"],
        last_name=document["last_name"],
        date_of_birth=document.get("date_of_birth"),
        identity_card_number=document.get("identity_card_number"),
        tax_id=document.get("tax_id"),
        phone_number=document.get("phone_number"),
        email=document.get("email"),
        license_number=document.get("license_number"),
        license_category=document.get("license_category"),
        license_expiry_date=document.get("license_expiry_date"),
        hire_date=document.get("hire_date"),
        fleet_id=document.get("fleet_id"),
        department_id=document.get("department_id"),
        status=document.get("status", "ACTIVE"),
    )

def fleet_manager_document_to_response(document: dict, ) -> FleetManagerResponse:
    """
    Μετατρέπει ένα MongoDB Fleet Manager document
    σε FleetManagerResponse.
    """

    return FleetManagerResponse(
        id=str(document["_id"]),
        manager_id=document["manager_id"],
        keycloak_user_id=document["keycloak_user_id"],
        first_name=document["first_name"],
        last_name=document["last_name"],
        date_of_birth=document.get("date_of_birth"),
        identity_card_number=document.get("identity_card_number"),
        tax_id=document.get("tax_id"),
        phone_number=document.get("phone_number"),
        email=document.get("email"),
        fleet_id=document["fleet_id"],
        department_id=document.get("department_id"),
        hire_date=document.get("hire_date"),
        status=document.get("status", "ACTIVE"),
    )

def fleet_document_to_response(document: dict) -> FleetResponse:
    """
    Μετατρέπει ένα MongoDB fleet document στο response model του API.

    Το MongoDB αποθηκεύει το primary key στο πεδίο "_id" ως ObjectId.
    Στο API δεν θέλουμε να εκθέτουμε το "_id" με αυτή τη μορφή,
    επομένως το μετατρέπουμε σε string και το επιστρέφουμε ως "id".
    """

    return FleetResponse(
        id=str(document["_id"]),
        fleet_id=document["fleet_id"],
        name=document["name"],
        description=document.get("description"),
        base_location=document["base_location"],
        status=document["status"],
        created_at=document["created_at"],
        updated_at=document["updated_at"],
    )

def validate_fleet_exists(fleet_id: str | None) -> None:
    """
    Ελέγχει ότι ένα fleet_id αντιστοιχεί σε πραγματικό Fleet.

    Τα Vehicles και Drivers επιτρέπεται να μην έχουν ακόμα ανατεθεί
    σε κάποιο fleet, επομένως το None θεωρείται έγκυρη τιμή.

    Όταν όμως υπάρχει fleet_id, πρέπει να αντιστοιχεί σε Fleet
    που υπάρχει στη συλλογή fleets. Με αυτόν τον τρόπο αποφεύγουμε
    orphan references προς ανύπαρκτα fleets.
    """
    if fleet_id is None:
        return

    fleet_document = fleets_collection.find_one({
        "fleet_id": fleet_id
    })

    if fleet_document is None:
        raise HTTPException(
            status_code=400,
            detail=f"Fleet with fleet_id '{fleet_id}' does not exist",
        )

# def get_driver_for_vehicle_assignment(driver_id: str) -> dict:
#     """
#     Επιστρέφει τον Driver που πρόκειται να ανατεθεί σε Vehicle.
#
#     Για να μπορεί ένας Driver να αναλάβει Vehicle:
#     - πρέπει να υπάρχει,
#     - πρέπει να ανήκει ήδη σε Fleet.
#
#     Το Fleet του Driver καθορίζει το Fleet του Vehicle τη στιγμή
#     που πραγματοποιείται η ανάθεση.
#     """
#
#     driver_document = drivers_collection.find_one({
#         "driver_id": driver_id
#     })
#
#     if driver_document is None:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Driver with driver_id '{driver_id}' does not exist",
#         )
#
#     driver_fleet_id = driver_document.get("fleet_id")
#
#     if driver_fleet_id is None:
#         raise HTTPException(
#             status_code=400,
#             detail=(
#                 f"Driver with driver_id '{driver_id}' cannot be assigned "
#                 "to a vehicle because the driver does not belong to a fleet"
#             ),
#         )
#
#     # Παρόλο που ο Driver κανονικά πρέπει ήδη να δείχνει σε υπαρκτό Fleet,
#     # κάνουμε τον έλεγχο και εδώ ώστε να μη δημιουργηθεί νέα ασυνεπής
#     # ανάθεση αν υπάρχουν παλαιότερα μη έγκυρα δεδομένα στη βάση.
#     validate_fleet_exists(driver_fleet_id)
#
#     return driver_document

def create_audit_log(audit_log: AuditLogCreate) -> AuditLogResponse:
    """
    Δημιουργεί μία νέα εγγραφή στο audit trail.

    Το timestamp δημιουργείται πάντα από το backend και όχι από τον client,
    ώστε ο χρόνος της καταγραφής να ελέγχεται από το σύστημά μας.

    Το audit log είναι append-only ιστορικό. Κάθε business αλλαγή δημιουργεί
    νέα εγγραφή και δεν τροποποιεί προηγούμενες εγγραφές.
    """

    timestamp = datetime.now(timezone.utc)

    document = audit_log.model_dump(mode="json")
    document["timestamp"] = timestamp

    result = audit_logs_collection.insert_one(document)

    logger.info(
        "Created audit log: entity_type=%s entity_id=%s action=%s",
        audit_log.entity_type,
        audit_log.entity_id,
        audit_log.action,
    )

    return AuditLogResponse(
        id=str(result.inserted_id),
        timestamp=timestamp,
        **audit_log.model_dump(),
    )

def audit_log_document_to_response(document: dict) -> AuditLogResponse:
    """
    Μετατρέπει ένα MongoDB audit document στο response model του API.

    Το MongoDB _id μετατρέπεται σε string ώστε να μπορεί να επιστραφεί
    σωστά ως JSON από το FastAPI.
    """

    return AuditLogResponse(
        id=str(document["_id"]),
        entity_type=document["entity_type"],
        entity_id=document["entity_id"],
        action=document["action"],
        description=document["description"],
        related_entities=document["related_entities"],
        changes=document.get("changes", {}),
        performed_by=document.get("performed_by"),
        timestamp=document["timestamp"],
    )

def get_driver_for_vehicle_assignment(driver_id: str) -> dict:
    """
    Επιστρέφει τον Driver που πρόκειται να ανατεθεί σε Vehicle.

    Για να μπορεί ένας Driver να αναλάβει Vehicle:
    - πρέπει να υπάρχει,
    - πρέπει να ανήκει ήδη σε Fleet.

    Το Fleet του Driver καθορίζει το Fleet του Vehicle τη στιγμή
    που πραγματοποιείται η ανάθεση.
    """

    driver_document = drivers_collection.find_one({
        "driver_id": driver_id
    })

    if driver_document is None:
        raise HTTPException(
            status_code=400,
            detail=f"Driver with driver_id '{driver_id}' does not exist",
        )

    driver_fleet_id = driver_document.get("fleet_id")

    if driver_fleet_id is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Driver with driver_id '{driver_id}' cannot be assigned "
                "to a vehicle because the driver does not belong to a fleet"
            ),
        )

    # Δεν επιτρέπουμε ανάθεση οχημάτων σε ανενεργό οδηγό.
    if driver_document.get("status") != "ACTIVE":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Driver with driver_id '{driver_id}' "
                "is not active and cannot be assigned to a vehicle"
            ),
        )

    # Παρόλο που ο Driver κανονικά πρέπει ήδη να δείχνει σε υπαρκτό Fleet,
    # κάνουμε τον έλεγχο και εδώ ώστε να μη δημιουργηθεί νέα ασυνεπής
    # ανάθεση αν υπάρχουν παλαιότερα μη έγκυρα δεδομένα στη βάση.
    validate_fleet_exists(driver_fleet_id)

    return driver_document

# -------------------------
# API Endpoints
# -------------------------

@app.get("/health")
def health_check():
    # Απλό health endpoint για να ελέγχουμε αν το service τρέχει.
    return {"status": "ok", "service": "fleet-api"}

@app.post("/vehicles", response_model=VehicleResponse)
def create_vehicle(vehicle: VehicleCreate):
    # Ελέγχουμε αν υπάρχει ήδη όχημα με το ίδιο IMEI.
    # Στο πραγματικό σύστημα ένα GPS tracker πρέπει να αντιστοιχεί σε ένα όχημα.
    existing_vehicle = vehicles_collection.find_one( {"device_imei": vehicle.device_imei} )

    if existing_vehicle:
        raise HTTPException( status_code=409, detail="Vehicle with this device IMEI already exists", )

    document = vehicle.model_dump()
    # Κάθε νέο Vehicle ξεκινά υποχρεωτικά ως ACTIVE.
    # Το lifecycle status ελέγχεται από το Fleet API και όχι από τον client.
    document["status"] = "ACTIVE"

    # Αν το Vehicle δημιουργείται με ανατεθειμένο Driver,
    # ελέγχουμε ότι ο Driver υπάρχει και ότι ανήκει ήδη σε Fleet.
    #
    # Κατά την ανάθεση Driver, το Vehicle πρέπει να ανήκει
    # στο ίδιο Fleet με τον Driver.
    if vehicle.driver_id is not None:
        driver_document = get_driver_for_vehicle_assignment(
            vehicle.driver_id
        )

        document["fleet_id"] = driver_document["fleet_id"]

    else:
        # Αν δεν υπάρχει ανατεθειμένος Driver, το Vehicle μπορεί
        # είτε να ανήκει σε κάποιο Fleet είτε να έχει fleet_id=None.
        #
        # Αν έχει δοθεί fleet_id, επιβεβαιώνουμε ότι το Fleet υπάρχει.
        validate_fleet_exists(vehicle.fleet_id)


    result = vehicles_collection.insert_one(document)

    created_vehicle = vehicles_collection.find_one({"_id": result.inserted_id})

    # Δημιουργούμε τα changes του audit μόνο για τις τιμές
    # που υπάρχουν πραγματικά κατά τη δημιουργία του Vehicle.
    #
    # Δεν θέλουμε εγγραφές όπως None → None, επειδή αυτές
    # δεν αντιπροσωπεύουν πραγματική αρχική τιμή ή αλλαγή.

    audit_changes = {
        "plate_number": AuditChange(
            from_value=None,
            to_value=created_vehicle["plate_number"],
        ),
    }

    if created_vehicle.get("fleet_id") is not None:
        audit_changes["fleet_id"] = AuditChange(
            from_value=None,
            to_value=created_vehicle["fleet_id"],
        )

    if created_vehicle.get("driver_id") is not None:
        audit_changes["driver_id"] = AuditChange(
            from_value=None,
            to_value=created_vehicle["driver_id"],
        )


    # Καταγράφουμε τη δημιουργία του Vehicle στο audit trail.
    #
    # Κρατάμε τόσο το σταθερό MongoDB id όσο και την πινακίδα,
    # ώστε το ιστορικό να είναι κατάλληλο για trace-back αλλά
    # και εύκολα αναγνώσιμο από τον χρήστη.


    create_audit_log(
        AuditLogCreate(
            entity_type="VEHICLE",
            entity_id=str(created_vehicle["_id"]),
            action="CREATED",
            description=(
                f"Vehicle {created_vehicle['plate_number']} was created"
            ),
            related_entities=AuditRelatedEntities(
                vehicle_id=str(created_vehicle["_id"]),
                plate_number=created_vehicle["plate_number"],
                fleet_id=created_vehicle.get("fleet_id"),
                driver_id=created_vehicle.get("driver_id"),
            ),
            changes=audit_changes,
        )
    )
    # Αφού το όχημα αποθηκευτεί επιτυχώς στη MongoDB,
    # δημοσιεύουμε event στο Kafka για να ενημερωθούν άλλα services.
    fleet_event_producer.publish_vehicle_created(created_vehicle)
    return vehicle_document_to_response(created_vehicle)

@app.get("/vehicles", response_model=List[VehicleResponse])
def list_vehicles():
    # Επιστρέφουμε όλα τα οχήματα που υπάρχουν στο collection.
    vehicles = vehicles_collection.find()
    return [vehicle_document_to_response(vehicle) for vehicle in vehicles]

@app.get("/vehicles/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(vehicle_id: str):
    # Ελέγχουμε ότι το id είναι έγκυρο MongoDB ObjectId.
    if not ObjectId.is_valid(vehicle_id):
        raise HTTPException(status_code=400, detail="Invalid vehicle id")

    vehicle = vehicles_collection.find_one({"_id": ObjectId(vehicle_id)})

    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    return vehicle_document_to_response(vehicle)

@app.patch("/vehicles/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle(vehicle_id: str, vehicle: VehicleUpdate):
    # Ελέγχουμε ότι το id είναι έγκυρο MongoDB ObjectId.
    if not ObjectId.is_valid(vehicle_id):
        raise HTTPException(status_code=400, detail="Invalid vehicle id")

    # Διαβάζουμε την τρέχουσα κατάσταση του Vehicle πριν κάνουμε οποιαδήποτε
    # αλλαγή. Τη χρειαζόμαστε τόσο για τους business κανόνες όσο και για
    # το audit trail, ώστε να γνωρίζουμε τις προηγούμενες τιμές.
    existing_vehicle = vehicles_collection.find_one({
        "_id": ObjectId(vehicle_id)
    })

    if existing_vehicle is None:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found",
        )

    update_data = vehicle.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException( status_code=400, detail="No update data provided", )

    # Αν το PATCH περιλαμβάνει αλλαγή του fleet_id,
    # επιβεβαιώνουμε ότι το νέο Fleet υπάρχει πριν ενημερωθεί το Vehicle.
    #
    # Ελέγχουμε την ύπαρξη του πεδίου στο update_data και όχι απλώς
    # την τιμή του, επειδή το fleet_id=None είναι έγκυρη επιλογή
    # για Vehicle και σημαίνει ότι το όχημα δεν ανήκει σε κάποιο fleet.
    # Αν το PATCH περιλαμβάνει driver_id, σημαίνει ότι γίνεται είτε
    # ανάθεση Driver είτε αφαίρεση του υπάρχοντος Driver.
    if "driver_id" in update_data:

        if update_data["driver_id"] is not None:
            # Driver μπορεί να ανατεθεί μόνο σε ACTIVE Vehicle.
            # Αν το Vehicle είναι INACTIVE, πρέπει πρώτα να ενεργοποιηθεί
            # μέσω του ειδικού lifecycle endpoint.
            if existing_vehicle.get("status") != "ACTIVE":
                raise HTTPException( status_code=409, detail="Vehicle must be ACTIVE before assigning a Driver", )
            # Ο νέος Driver πρέπει να υπάρχει και να ανήκει σε Fleet.
            driver_document = get_driver_for_vehicle_assignment( update_data["driver_id"] )

            driver_fleet_id = driver_document["fleet_id"]

            # Αν ο client έστειλε ταυτόχρονα και fleet_id, δεν επιτρέπουμε
            # να είναι διαφορετικό από το Fleet του Driver.
            if (
                "fleet_id" in update_data
                and update_data["fleet_id"] != driver_fleet_id
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Vehicle fleet_id must match the assigned "
                        "driver's fleet_id"
                    ),
                )

            # Κατά την ανάθεση Driver, το Vehicle τοποθετείται αυτόματα
            # στο ίδιο Fleet με τον Driver.
            update_data["fleet_id"] = driver_fleet_id

        else:
            # driver_id=None σημαίνει ότι αφαιρούμε τον Driver.
            #
            # Δεν αλλάζουμε αυτόματα το fleet_id του Vehicle.
            # Το Vehicle εξακολουθεί να ανήκει στο Fleet που είχε.
            if "fleet_id" in update_data:
                validate_fleet_exists(update_data["fleet_id"])


    elif "fleet_id" in update_data:
        # Αν αλλάζει το Fleet του Vehicle, επιβεβαιώνουμε πρώτα
        # ότι το νέο Fleet υπάρχει. Το None παραμένει έγκυρη τιμή.
        validate_fleet_exists(update_data["fleet_id"])

        existing_driver_id = existing_vehicle.get("driver_id")
        old_fleet_id = existing_vehicle.get("fleet_id")
        new_fleet_id = update_data["fleet_id"]

        # Αν το Vehicle μετακινείται πραγματικά σε διαφορετικό Fleet
        # και έχει ανατεθειμένο Driver, η σχέση Driver ↔ Vehicle λύνεται.
        #
        # Το Vehicle μετακινείται στο νέο Fleet, αλλά ο Driver παραμένει
        # στο δικό του Fleet. Επομένως το Vehicle χάνει τον Driver και,
        # αντίστοιχα, ο Driver δεν έχει πλέον αυτό το Vehicle.
        if (existing_driver_id is not None and old_fleet_id != new_fleet_id ):
            update_data["driver_id"] = None

    # Ενημερώνουμε μόνο τα πεδία που έστειλε ο client.
    result = vehicles_collection.update_one( {"_id": ObjectId(vehicle_id)}, {"$set": update_data}, )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    updated_vehicle = vehicles_collection.find_one( {"_id": ObjectId(vehicle_id) } )

    # Δημιουργούμε structured audit changes μόνο για τα πεδία
    # που άλλαξαν πραγματικά μετά το PATCH.
    audit_changes = {}

    for field in update_data:
        old_value = existing_vehicle.get(field)
        new_value = updated_vehicle.get(field)

        if old_value != new_value:
            audit_changes[field] = AuditChange(
                from_value=old_value,
                to_value=new_value,
            )

    old_driver_id = existing_vehicle.get("driver_id")
    new_driver_id = updated_vehicle.get("driver_id")

    old_fleet_id = existing_vehicle.get("fleet_id")
    new_fleet_id = updated_vehicle.get("fleet_id")

    # Αν άλλαξε το Fleet του Vehicle, αυτή είναι η κύρια business ενέργεια.
    # Αν λόγω αυτής της μετακίνησης αφαιρέθηκε και ο Driver, το αναφέρουμε
    # στην περιγραφή και το driver_id καταγράφεται κανονικά στα changes.
    if old_fleet_id != new_fleet_id:
        audit_action = "FLEET_CHANGED"

        if old_driver_id is not None and new_driver_id is None:
            audit_description = (
                f"Vehicle {updated_vehicle['plate_number']} changed fleet "
                f"from {old_fleet_id} to {new_fleet_id} and driver "
                f"{old_driver_id} was unassigned"
            )
        else:
            audit_description = (
                f"Vehicle {updated_vehicle['plate_number']} changed fleet "
                f"from {old_fleet_id} to {new_fleet_id}"
            )

    elif old_driver_id != new_driver_id:
        if old_driver_id is None and new_driver_id is not None:
            audit_action = "DRIVER_ASSIGNED"
            audit_description = (
                f"Driver {new_driver_id} was assigned to "
                f"vehicle {updated_vehicle['plate_number']}"
            )

        elif old_driver_id is not None and new_driver_id is None:
            audit_action = "DRIVER_UNASSIGNED"
            audit_description = (
                f"Driver {old_driver_id} was unassigned from "
                f"vehicle {updated_vehicle['plate_number']}"
            )

        else:
            audit_action = "DRIVER_CHANGED"
            audit_description = (
                f"Vehicle {updated_vehicle['plate_number']} changed "
                f"driver from {old_driver_id} to {new_driver_id}"
            )

    else:
        audit_action = "UPDATED"
        audit_description = (
            f"Vehicle {updated_vehicle['plate_number']} was updated"
        )

    if audit_changes:
        create_audit_log(
            AuditLogCreate(
                entity_type="VEHICLE",
                entity_id=str(updated_vehicle["_id"]),
                action=audit_action,
                description=audit_description,
                related_entities=AuditRelatedEntities(
                    vehicle_id=str(updated_vehicle["_id"]),
                    plate_number=updated_vehicle["plate_number"],
                    fleet_id=updated_vehicle.get("fleet_id"),
                    driver_id=updated_vehicle.get("driver_id"),
                ),
                changes=audit_changes,
            )
        )

    return vehicle_document_to_response(updated_vehicle)

@app.delete("/vehicles/{vehicle_id}")
def delete_vehicle(vehicle_id: str):
    # Ελέγχουμε ότι το id είναι έγκυρο MongoDB ObjectId.
    if not ObjectId.is_valid(vehicle_id):
        raise HTTPException(status_code=400, detail="Invalid vehicle id")

    # Διαβάζουμε πρώτα το Vehicle πριν το διαγράψουμε.
    #
    # Χρειαζόμαστε τα στοιχεία του για το audit trail, επειδή μετά
    # το delete δεν θα υπάρχει πλέον το document στη συλλογή vehicles.
    existing_vehicle = vehicles_collection.find_one(
        {"_id": ObjectId(vehicle_id)}
    )

    if existing_vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    # Το Hard Delete επιτρέπεται μόνο αφού το Vehicle
    # έχει πρώτα τεθεί σε INACTIVE κατάσταση.
    #
    # Με αυτόν τον τρόπο ένα ενεργό Vehicle δεν μπορεί
    # να διαγραφεί οριστικά κατά λάθος.
    if existing_vehicle.get("status") != "INACTIVE":
        raise HTTPException( status_code=409, detail=( "Vehicle must be INACTIVE before permanent deletion" ), )

    result = vehicles_collection.delete_one( {"_id": ObjectId(vehicle_id)} )

    if result.deleted_count == 0:
        raise HTTPException( status_code=500, detail="Vehicle could not be deleted", )

    # Η εγγραφή του audit παραμένει ακόμα και μετά τη διαγραφή
    # του Vehicle, ώστε να υπάρχει μόνιμο ιστορικό της οντότητας.
    create_audit_log(
        AuditLogCreate(
            entity_type="VEHICLE",
            entity_id=vehicle_id,
            action="DELETED",
            description=(
                f"Vehicle {existing_vehicle['plate_number']} was deleted"
            ),
            related_entities=AuditRelatedEntities(
                vehicle_id=vehicle_id,
                plate_number=existing_vehicle["plate_number"],
                fleet_id=existing_vehicle.get("fleet_id"),
                driver_id=existing_vehicle.get("driver_id"),
            ),
            changes={},
        )
    )

    logger.info(
        "Deleted vehicle: vehicle_id=%s plate_number=%s",
        vehicle_id,
        existing_vehicle["plate_number"],
    )

    return {
        "message": "Vehicle deleted successfully",
        "vehicle_id": vehicle_id,
    }

@app.post("/vehicles/{vehicle_id}/deactivate", response_model=VehicleResponse)
def deactivate_vehicle(vehicle_id: str):
    """
    Θέτει ένα Vehicle σε INACTIVE κατάσταση.

    Κατά το deactivation:
    - το Vehicle παραμένει στο ίδιο Fleet,
    - ο τυχόν ανατεθειμένος Driver αφαιρείται,
    - δεν διαγράφεται κανένα business δεδομένο,
    - η αλλαγή καταγράφεται στο audit history.

    Η λειτουργία είναι idempotent:
    αν το Vehicle είναι ήδη INACTIVE, επιστρέφεται χωρίς νέα αλλαγή.
    """

    if not ObjectId.is_valid(vehicle_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid vehicle id",
        )

    existing_vehicle = vehicles_collection.find_one(
        {"_id": ObjectId(vehicle_id)}
    )

    if existing_vehicle is None:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found",
        )

    # Αν είναι ήδη INACTIVE δεν δημιουργούμε δεύτερο audit event.
    if existing_vehicle.get("status") == "INACTIVE":
        return vehicle_document_to_response(existing_vehicle)

    old_driver_id = existing_vehicle.get("driver_id")

    # Το Vehicle παραμένει στο Fleet του, αλλά δεν πρέπει να παραμένει
    # ανατεθειμένο σε Driver όσο βρίσκεται εκτός λειτουργίας.
    vehicles_collection.update_one(
        {"_id": ObjectId(vehicle_id)},
        {
            "$set": {
                "status": "INACTIVE",
                "driver_id": None,
            }
        },
    )

    updated_vehicle = vehicles_collection.find_one(
        {"_id": ObjectId(vehicle_id)}
    )

    audit_changes = {
        "status": AuditChange(
            from_value=existing_vehicle.get("status"),
            to_value="INACTIVE",
        )
    }

    # Καταγράφουμε και την αφαίρεση του Driver μόνο όταν
    # υπήρχε πραγματικά Driver πριν από το deactivation.
    if old_driver_id is not None:
        audit_changes["driver_id"] = AuditChange(
            from_value=old_driver_id,
            to_value=None,
        )

    create_audit_log(
        AuditLogCreate(
            entity_type="VEHICLE",
            entity_id=vehicle_id,
            action="DEACTIVATED",
            description=(
                f"Vehicle {updated_vehicle['plate_number']} was deactivated"
            ),
            related_entities=AuditRelatedEntities(
                vehicle_id=vehicle_id,
                plate_number=updated_vehicle["plate_number"],
                fleet_id=updated_vehicle.get("fleet_id"),
                driver_id=updated_vehicle.get("driver_id"),
            ),
            changes=audit_changes,
        )
    )

    logger.info(
        "Deactivated vehicle: vehicle_id=%s plate_number=%s",
        vehicle_id,
        updated_vehicle["plate_number"],
    )

    return vehicle_document_to_response(updated_vehicle)

@app.post("/vehicles/{vehicle_id}/activate", response_model=VehicleResponse)
def activate_vehicle(vehicle_id: str):
    """
    Επανενεργοποιεί ένα Vehicle.

    Το προηγούμενο Driver assignment δεν επαναφέρεται αυτόματα.
    Η ανάθεση Driver αποτελεί ξεχωριστή business ενέργεια.

    Η λειτουργία είναι idempotent:
    αν το Vehicle είναι ήδη ACTIVE, επιστρέφεται χωρίς νέα αλλαγή.
    """

    if not ObjectId.is_valid(vehicle_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid vehicle id",
        )

    existing_vehicle = vehicles_collection.find_one(
        {"_id": ObjectId(vehicle_id)}
    )

    if existing_vehicle is None:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found",
        )

    # Αν είναι ήδη ACTIVE δεν δημιουργούμε δεύτερο audit event.
    if existing_vehicle.get("status") == "ACTIVE":
        return vehicle_document_to_response(existing_vehicle)

    vehicles_collection.update_one(
        {"_id": ObjectId(vehicle_id)},
        {
            "$set": {
                "status": "ACTIVE",
            }
        },
    )

    updated_vehicle = vehicles_collection.find_one(
        {"_id": ObjectId(vehicle_id)}
    )

    create_audit_log(
        AuditLogCreate(
            entity_type="VEHICLE",
            entity_id=vehicle_id,
            action="ACTIVATED",
            description=(
                f"Vehicle {updated_vehicle['plate_number']} was activated"
            ),
            related_entities=AuditRelatedEntities(
                vehicle_id=vehicle_id,
                plate_number=updated_vehicle["plate_number"],
                fleet_id=updated_vehicle.get("fleet_id"),
                driver_id=updated_vehicle.get("driver_id"),
            ),
            changes={
                "status": AuditChange(
                    from_value=existing_vehicle.get("status"),
                    to_value="ACTIVE",
                )
            },
        )
    )

    logger.info(
        "Activated vehicle: vehicle_id=%s plate_number=%s",
        vehicle_id,
        updated_vehicle["plate_number"],
    )

    return vehicle_document_to_response(updated_vehicle)

@app.post("/drivers", response_model=DriverResponse)
def create_driver(driver: DriverCreate):
    """
        Δημιουργεί νέο Driver Profile στη MongoDB.

        Δεν επιτρέπουμε:
        - δύο drivers με το ίδιο driver_id,
        - δύο drivers να αντιστοιχούν στο ίδιο Keycloak user.
    """
    # Αναζητούμε πρώτα το Driver Profile που αντιστοιχεί
    # στο συγκεκριμένο Keycloak identity.
    existing_keycloak_user = drivers_collection.find_one({
        "keycloak_user_id": driver.keycloak_user_id
    })

    if existing_keycloak_user:
        # Συγκρίνουμε τα δεδομένα της νέας αίτησης με το
        # ήδη αποθηκευμένο προφίλ, ώστε να αναγνωρίσουμε
        # μια πραγματική επανάληψη της ίδιας αίτησης.
        requested_data = driver.model_dump(mode="json")

        existing_data = {
            field: existing_keycloak_user.get(field)
            for field in requested_data
        }

        if existing_data == requested_data:
            # Επιστρέφουμε το υπάρχον προφίλ χωρίς νέα εγγραφή
            # στη MongoDB και χωρίς δεύτερο audit log.
            logger.info(
                "Existing driver returned for retry: driver_id=%s",
                driver.driver_id,
            )

            return driver_document_to_response(existing_keycloak_user)

        # Το ίδιο Keycloak identity δεν μπορεί να συνδεθεί
        # με διαφορετικό Driver Profile.
        raise HTTPException(
            status_code=409,
            detail="Driver with this Keycloak user already exists",
        )

    # Αν το Keycloak identity δεν έχει ήδη Driver Profile,
    # ελέγχουμε μήπως χρησιμοποιείται το ίδιο business driver_id.
    existing_driver_id = drivers_collection.find_one({
        "driver_id": driver.driver_id
    })

    if existing_driver_id:
        raise HTTPException(
            status_code=409,
            detail="Driver with this driver_id already exists",
        )

    # Μετατρέπουμε το Pydantic model σε dictionary
    # για να μπορεί να αποθηκευτεί στη MongoDB.
    # Μετατρέπουμε τα πεδία όπως date και EmailStr
    # σε JSON-compatible τιμές πριν αποθηκευτούν στη MongoDB.
    # Έτσι οι ημερομηνίες αποθηκεύονται ως ISO strings,
    # π.χ. "1995-04-12", αντί για Python date objects.
    document = driver.model_dump(mode="json")

    # Αν έχει δοθεί fleet_id, επιβεβαιώνουμε ότι αντιστοιχεί
    # σε πραγματικό Fleet πριν αποθηκεύσουμε τον Driver.
    validate_fleet_exists(driver.fleet_id)

    # Οι αρχικοί έλεγχοι find_one δεν αρκούν για να αποτρέψουν
    # τέτοιες περιπτώσεις, γι' αυτό χειριζόμαστε και το σφάλμα
    # που μπορεί να προκύψει κατά την ίδια την εισαγωγή.
    try:
        result = drivers_collection.insert_one(document)

    except DuplicateKeyError:
        # Μια άλλη αίτηση μπορεί να δημιούργησε το ίδιο
        # Driver Profile ακριβώς πριν από τη δική μας εισαγωγή.
        existing_driver = drivers_collection.find_one({
            "keycloak_user_id": driver.keycloak_user_id
        })

        if existing_driver:
            requested_data = driver.model_dump(mode="json")

            existing_data = {
                field: existing_driver.get(field)
                for field in requested_data
            }

            if existing_data == requested_data:
                # Πρόκειται για την ίδια αίτηση. Επιστρέφουμε
                # το προφίλ που δημιουργήθηκε από την άλλη διαδικασία.
                logger.info(
                    "Existing driver returned after concurrent retry: driver_id=%s",
                    driver.driver_id,
                )
                return driver_document_to_response(existing_driver)

        # Αν τα στοιχεία διαφέρουν, πρόκειται για σύγκρουση
        # και όχι για ασφαλή επανάληψη της ίδιας αίτησης.
        logger.warning(
            "Conflicting driver creation: driver_id=%s keycloak_user_id=%s",
            driver.driver_id,
            driver.keycloak_user_id,
        )

        raise HTTPException(
            status_code=409,
            detail="Driver with this Keycloak user already exists",
        )

    # Διαβάζουμε ξανά το document όπως αποθηκεύτηκε
    # ώστε να επιστρέψουμε και το MongoDB ObjectId.
    created_driver = drivers_collection.find_one({
        "_id": result.inserted_id
    })

    audit_changes = {
        "driver_id": AuditChange(
            from_value=None,
            to_value=created_driver["driver_id"],
        ),
    }

    if created_driver.get("fleet_id") is not None:
        audit_changes["fleet_id"] = AuditChange(
            from_value=None,
            to_value=created_driver["fleet_id"],
        )

    # Καταγράφουμε τη δημιουργία του Driver στο μόνιμο audit trail.
    #
    # Το driver_id χρησιμοποιείται ως σταθερό business identifier,
    # ώστε το ιστορικό να παραμένει αναζητήσιμο ακόμη και αν
    # το Driver Profile διαγραφεί αργότερα.
    create_audit_log(
        AuditLogCreate(
            entity_type="DRIVER",
            entity_id=created_driver["driver_id"],
            action="CREATED",
            description=(
                f"Driver {created_driver['driver_id']} was created"
            ),
            related_entities=AuditRelatedEntities(
                driver_id=created_driver["driver_id"],
                fleet_id=created_driver.get("fleet_id"),
            ),
            changes=audit_changes,
        )
    )

    logger.info(
        "Created driver: driver_id=%s fleet_id=%s",
        created_driver["driver_id"],
        created_driver.get("fleet_id"),
    )

    return driver_document_to_response(created_driver)

@app.get( "/drivers/by-keycloak-user/{keycloak_user_id}", response_model=DriverResponse,)
def get_driver_by_keycloak_user(keycloak_user_id: str):
    """
    Επιστρέφει το Driver Profile που αντιστοιχεί
    σε συγκεκριμένο Keycloak user.

    Το keycloak_user_id αντιστοιχεί στο claim "sub"
    του JWT που εκδίδει το Keycloak.
    """

    # Αναζητούμε τον driver με βάση το σταθερό Keycloak user id.
    driver_document = drivers_collection.find_one({
        "keycloak_user_id": keycloak_user_id
    })

    # Αν δεν υπάρχει αντιστοίχιση, επιστρέφουμε 404.
    if not driver_document:
        raise HTTPException(
            status_code=404,
            detail="Driver not found for this Keycloak user",
        )

    # Μετατρέπουμε το MongoDB document
    # στο response model του API.
    return driver_document_to_response(driver_document)

@app.get( "/drivers/{driver_id}/vehicles", response_model=list[VehicleResponse],)
def get_vehicles_by_driver(driver_id: str):
    """
    Επιστρέφει όλα τα οχήματα που είναι ανατεθειμένα
    στον συγκεκριμένο driver.

    Η συσχέτιση γίνεται μέσω του πεδίου driver_id
    που υπάρχει ήδη στα vehicle documents.
    """

    # Αναζητούμε όλα τα vehicles που έχουν
    # το συγκεκριμένο driver_id.
    vehicle_documents = list(
        vehicles_collection.find({
            "driver_id": driver_id
        })
    )

    # Μετατρέπουμε κάθε MongoDB document
    # στο response model που χρησιμοποιεί το API.
    return [
        vehicle_document_to_response(vehicle_document)
        for vehicle_document in vehicle_documents
    ]

@app.get( "/drivers/by-keycloak-user/{keycloak_user_id}/vehicles", response_model=list[VehicleResponse],)
def get_driver_vehicles_by_keycloak_user(keycloak_user_id: str):
    """
    Επιστρέφει τα οχήματα που είναι ανατεθειμένα
    στον driver που αντιστοιχεί σε συγκεκριμένο Keycloak user.

    Το keycloak_user_id είναι το claim "sub" του JWT.
    Πρώτα βρίσκουμε τον business driver και στη συνέχεια
    χρησιμοποιούμε το driver_id για να βρούμε τα οχήματά του.
    """

    # Βρίσκουμε ποιος business driver αντιστοιχεί
    # στον συγκεκριμένο Keycloak user.
    driver_document = drivers_collection.find_one({
        "keycloak_user_id": keycloak_user_id
    })

    if not driver_document:
        raise HTTPException(
            status_code=404,
            detail="Driver not found for this Keycloak user",
        )

    driver_id = driver_document["driver_id"]

    # Αναζητούμε όλα τα οχήματα που είναι
    # ανατεθειμένα στον συγκεκριμένο driver.
    vehicle_documents = vehicles_collection.find({
        "driver_id": driver_id
    })

    return [
        vehicle_document_to_response(vehicle_document)
        for vehicle_document in vehicle_documents
    ]

@app.patch("/drivers/{driver_id}", response_model=DriverResponse)
def update_driver(driver_id: str, driver: DriverUpdate):
    """
    Ενημερώνει μερικώς ένα Driver Profile.

    Αν αλλάξει το Fleet του Driver:
    - ο Driver μετακινείται στο νέο Fleet ή αφαιρείται από Fleet,
    - όλα τα Vehicles που ήταν ανατεθειμένα στον Driver
      χάνουν την ανάθεση,
    - τα Vehicles παραμένουν στα δικά τους Fleets,
    - καταγράφεται audit τόσο για τον Driver όσο και για
      κάθε Vehicle που έχασε τον Driver.
    """

    # Βρίσκουμε πρώτα τον υπάρχοντα Driver ώστε να γνωρίζουμε
    # τις προηγούμενες τιμές πριν εφαρμοστεί οποιαδήποτε αλλαγή.
    existing_driver = drivers_collection.find_one({
        "driver_id": driver_id
    })

    if existing_driver is None:
        raise HTTPException(
            status_code=404,
            detail="Driver not found",
        )

    # Το exclude_unset=True είναι σημαντικό γιατί μας επιτρέπει
    # να ξεχωρίζουμε ένα πεδίο που δεν στάλθηκε καθόλου από ένα
    # πεδίο που στάλθηκε σκόπιμα ως null.
    update_data = driver.model_dump(
        exclude_unset=True,
        mode="json",
    )

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No fields provided for update",
        )

    # Η ενεργοποίηση και η απενεργοποίηση γίνονται αποκλειστικά
    # από τα ειδικά endpoints, ώστε να εφαρμόζονται όλοι
    # οι απαραίτητοι business κανόνες.
    if "status" in update_data:
        raise HTTPException(
            status_code=400,
            detail=(
                "Driver status cannot be changed through PATCH. "
                "Use the dedicated activation or deactivation endpoint."
            ),
        )

    old_fleet_id = existing_driver.get("fleet_id")
    new_fleet_id = update_data.get("fleet_id", old_fleet_id)

    fleet_changed = (
        "fleet_id" in update_data
        and old_fleet_id != new_fleet_id
    )

    # Αν ο client αλλάζει το Fleet, επιβεβαιώνουμε πρώτα
    # ότι το νέο fleet_id αντιστοιχεί σε πραγματικό Fleet.
    #
    # Το None είναι έγκυρο και σημαίνει ότι ο Driver
    # αφαιρείται από το Fleet.
    if fleet_changed:
        validate_fleet_exists(new_fleet_id)

    # Κρατάμε τα Vehicles που θα αποδεσμευτούν πριν κάνουμε
    # οποιαδήποτε αλλαγή, ώστε να έχουμε τα προηγούμενα στοιχεία
    # διαθέσιμα για το audit trail.
    affected_vehicles = []

    if fleet_changed:
        affected_vehicles = list(
            vehicles_collection.find({
                "driver_id": driver_id
            })
        )

        # Ο Driver αλλάζει Fleet, επομένως όλες οι υπάρχουσες
        # αναθέσεις του σε Vehicles παύουν να ισχύουν.
        #
        # Δεν αλλάζουμε το fleet_id των Vehicles.
        vehicles_collection.update_many(
            {"driver_id": driver_id},
            {
                "$set": {
                    "driver_id": None
                }
            },
        )

    # Ενημερώνουμε το Driver Profile μόνο αφού έχουν ολοκληρωθεί
    # οι απαραίτητοι έλεγχοι.
    drivers_collection.update_one(
        {"driver_id": driver_id},
        {
            "$set": update_data
        },
    )

    updated_driver = drivers_collection.find_one({
        "driver_id": driver_id
    })

    # Καταγράφουμε μόνο τα πεδία που άλλαξαν πραγματικά.
    driver_audit_changes = {}

    for field_name in update_data:
        old_value = existing_driver.get(field_name)
        new_value = updated_driver.get(field_name)

        if old_value != new_value:
            driver_audit_changes[field_name] = AuditChange(
                from_value=old_value,
                to_value=new_value,
            )

    # Αν άλλαξε το Fleet, το audit πρέπει να αποτυπώνει
    # ότι η αλλαγή αφορά τη σχέση Driver → Fleet.
    if fleet_changed:
        audit_action = "FLEET_CHANGED"

        if new_fleet_id is None:
            audit_description = (
                f"Driver {driver_id} was removed from fleet "
                f"{old_fleet_id}"
            )
        elif old_fleet_id is None:
            audit_description = (
                f"Driver {driver_id} was assigned to fleet "
                f"{new_fleet_id}"
            )
        else:
            audit_description = (
                f"Driver {driver_id} changed fleet "
                f"from {old_fleet_id} to {new_fleet_id}"
            )
    else:
        audit_action = "UPDATED"
        audit_description = (
            f"Driver {driver_id} was updated"
        )

    if driver_audit_changes:
        create_audit_log(
            AuditLogCreate(
                entity_type="DRIVER",
                entity_id=driver_id,
                action=audit_action,
                description=audit_description,
                related_entities=AuditRelatedEntities(
                    driver_id=driver_id,
                    fleet_id=updated_driver.get("fleet_id"),
                ),
                changes=driver_audit_changes,
            )
        )
    # Για κάθε Vehicle που έχασε τον Driver δημιουργούμε
    # ξεχωριστή εγγραφή audit.
    #
    # Έτσι μπορούμε αργότερα να εξηγήσουμε όχι μόνο ότι
    # το Vehicle έχασε τον Driver, αλλά και γιατί συνέβη.
    for vehicle_document in affected_vehicles:
        vehicle_id = str(vehicle_document["_id"])

        create_audit_log(
            AuditLogCreate(
                entity_type="VEHICLE",
                entity_id=vehicle_id,
                action="DRIVER_UNASSIGNED",
                description=(
                    f"Driver {driver_id} was unassigned from vehicle "
                    f"{vehicle_document['plate_number']} because the "
                    "driver changed fleet"
                ),
                related_entities=AuditRelatedEntities(
                    vehicle_id=vehicle_id,
                    plate_number=vehicle_document["plate_number"],
                    fleet_id=vehicle_document.get("fleet_id"),
                    driver_id=driver_id,
                ),
                changes={
                    "driver_id": AuditChange(
                        from_value=driver_id,
                        to_value=None,
                    )
                },
            )
        )

    logger.info(
        "Updated driver: driver_id=%s fleet_id=%s",
        driver_id,
        updated_driver.get("fleet_id"),
    )
    return driver_document_to_response(updated_driver)

@app.post( "/drivers/{driver_id}/activate", response_model=DriverResponse,)
def activate_driver(driver_id: str):
    """
    Επανενεργοποιεί το Driver Profile.

    Δεν επαναφέρει παλιές αναθέσεις οχημάτων.
    Το Keycloak ενημερώνεται ξεχωριστά από το API Gateway.
    """

    # Βρίσκουμε τον οδηγό από το μοναδικό business ID.
    existing_driver = drivers_collection.find_one({ "driver_id": driver_id, })

    if existing_driver is None:
        raise HTTPException(
            status_code=404,
            detail="Driver not found",
        )

    # Αν είναι ήδη ενεργός, δεν χρειάζεται νέα ενημέρωση
    # ούτε δεύτερη εγγραφή στο ιστορικό.
    if existing_driver.get("status") == "ACTIVE":
        return driver_document_to_response(existing_driver)

    # Αλλάζουμε αποκλειστικά το status.
    # Δεν πειράζουμε τα οχήματα ή το fleet_id.
    drivers_collection.update_one( {"driver_id": driver_id},{"$set": {"status": "ACTIVE"}}, )

    updated_driver = drivers_collection.find_one({ "driver_id": driver_id, })

    # Κρατάμε ιστορικό της αλλαγής κατάστασης.
    create_audit_log(
        AuditLogCreate(
            entity_type="DRIVER",
            entity_id=driver_id,
            action="ACTIVATED",
            description=f"Driver {driver_id} was activated",
            related_entities=AuditRelatedEntities(
                driver_id=driver_id,
                fleet_id=existing_driver.get("fleet_id"),
            ),
            changes={
                "status": AuditChange(
                    from_value=existing_driver.get("status"),
                    to_value="ACTIVE",
                ),
            },
        )
    )

    logger.info(
        "Activated driver: driver_id=%s",
        driver_id,
    )

    return driver_document_to_response(updated_driver)

@app.post("/drivers/{driver_id}/deactivate", response_model=DriverResponse, )
def deactivate_driver(driver_id: str):
    """
    Απενεργοποιεί ένα Driver Profile χωρίς να το διαγράφει.

    Αποδεσμεύει τα οχήματα του οδηγού, διατηρεί τα fleet_id
    τους και καταγράφει τις αλλαγές στο audit trail.
    """

    # Διαβάζουμε τον οδηγό πριν από οποιαδήποτε αλλαγή.
    existing_driver = drivers_collection.find_one({
        "driver_id": driver_id
    })

    if existing_driver is None:
        raise HTTPException(
            status_code=404,
            detail="Driver not found",
        )

    # Αν είναι ήδη ανενεργός, δεν δημιουργούμε δεύτερο audit.
    if existing_driver.get("status") == "INACTIVE":
        return driver_document_to_response(existing_driver)

    # Κρατάμε τα οχήματα πριν αποδεσμευτούν για το audit.
    affected_vehicles = list(
        vehicles_collection.find({
            "driver_id": driver_id
        })
    )

    # Αποδεσμεύουμε τα οχήματα χωρίς να αλλάξουμε τα Fleets τους.
    vehicles_collection.update_many(
        {"driver_id": driver_id},
        {"$set": {"driver_id": None}},
    )

    # Διατηρούμε το Driver Profile και αλλάζουμε μόνο την κατάστασή του.
    drivers_collection.update_one(
        {"driver_id": driver_id},
        {"$set": {"status": "INACTIVE"}},
    )

    updated_driver = drivers_collection.find_one({
        "driver_id": driver_id
    })

    # Καταγράφουμε την απενεργοποίηση του οδηγού.
    create_audit_log(
        AuditLogCreate(
            entity_type="DRIVER",
            entity_id=driver_id,
            action="DEACTIVATED",
            description=f"Driver {driver_id} was deactivated",
            related_entities=AuditRelatedEntities(
                driver_id=driver_id,
                fleet_id=existing_driver.get("fleet_id"),
            ),
            changes={
                "status": AuditChange(
                    from_value=existing_driver.get("status", "ACTIVE"),
                    to_value="INACTIVE",
                )
            },
        )
    )

    # Κάθε όχημα που αποδεσμεύτηκε αποκτά δική του εγγραφή audit.
    for vehicle_document in affected_vehicles:
        vehicle_id = str(vehicle_document["_id"])

        create_audit_log(
            AuditLogCreate(
                entity_type="VEHICLE",
                entity_id=vehicle_id,
                action="DRIVER_UNASSIGNED",
                description=(
                    f"Driver {driver_id} was unassigned from vehicle "
                    f"{vehicle_document['plate_number']} "
                    "because the driver was deactivated"
                ),
                related_entities=AuditRelatedEntities(
                    vehicle_id=vehicle_id,
                    plate_number=vehicle_document["plate_number"],
                    fleet_id=vehicle_document.get("fleet_id"),
                    driver_id=driver_id,
                ),
                changes={
                    "driver_id": AuditChange(
                        from_value=driver_id,
                        to_value=None,
                    )
                },
            )
        )

    logger.info(
        "Deactivated driver: driver_id=%s affected_vehicles=%s",
        driver_id,
        len(affected_vehicles),
    )

    return driver_document_to_response(updated_driver)

@app.delete("/drivers/{driver_id}")
def delete_driver(driver_id: str):
    """
    Διαγράφει ένα Driver Profile από το Fleet API.

    Πριν διαγραφεί ο Driver:
    - βρίσκουμε όλα τα Vehicles που του έχουν ανατεθεί,
    - αφαιρούμε τον Driver από αυτά,
    - τα Vehicles παραμένουν στα Fleets που ήδη ανήκουν,
    - καταγράφουμε audit για κάθε Vehicle που αποδεσμεύτηκε,
    - καταγράφουμε μόνιμο audit για τη διαγραφή του Driver.

    Σε αυτή τη φάση διαγράφεται μόνο το business Driver Profile.
    Το αντίστοιχο Keycloak account δεν διαγράφεται από αυτό το endpoint.
    """

    # Διαβάζουμε πρώτα τον Driver πριν γίνει η διαγραφή.
    # Χρειαζόμαστε τα στοιχεία του τόσο για τους business κανόνες
    # όσο και για το audit trail που πρέπει να παραμείνει μόνιμα.
    existing_driver = drivers_collection.find_one({
        "driver_id": driver_id
    })

    if existing_driver is None:
        raise HTTPException(
            status_code=404,
            detail="Driver not found",
        )

    # Κρατάμε όλα τα Vehicles που είναι ανατεθειμένα στον Driver
    # πριν αφαιρέσουμε τη σχέση, ώστε να γνωρίζουμε ποια Vehicles
    # επηρεάστηκαν και να δημιουργήσουμε σωστό audit για το καθένα.
    affected_vehicles = list(
        vehicles_collection.find({
            "driver_id": driver_id
        })
    )

    # Αποδεσμεύουμε όλα τα Vehicles από τον Driver.
    #
    # Αλλάζουμε αποκλειστικά το driver_id.
    # Το fleet_id κάθε Vehicle παραμένει ακριβώς όπως ήταν.
    vehicles_collection.update_many(
        {"driver_id": driver_id},
        {
            "$set": {
                "driver_id": None
            }
        },
    )

    # Διαγράφουμε το business Driver Profile.
    #
    # Δεν διαγράφουμε εδώ τον Keycloak user.
    # Η διαχείριση του Keycloak account θα γίνει αργότερα
    # από το ολοκληρωμένο Admin create/delete flow.
    result = drivers_collection.delete_one({
        "driver_id": driver_id
    })

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=500,
            detail="Driver could not be deleted",
        )

    # Καταγράφουμε τη διαγραφή του Driver στο μόνιμο audit trail.
    #
    # Επειδή μετά από αυτό το σημείο το Driver Profile δεν υπάρχει πλέον,
    # αποθηκεύουμε στο audit τις βασικές business πληροφορίες που είχε
    # ακριβώς πριν από τη διαγραφή του.
    #
    # Επίσης, κρατάμε το Keycloak user ID στο audit της οριστικής διαγραφής.
    #
    # Το Driver Profile μετά το Hard Delete δεν υπάρχει πλέον.
    # Το συγκεκριμένο identifier επιτρέπει στο API Gateway να
    # ολοκληρώσει ή να επαναλάβει με ασφάλεια τη διαγραφή του
    # αντίστοιχου Keycloak identity αν υπάρξει προσωρινή αποτυχία.
    driver_delete_changes = {
        "driver_id": AuditChange(
            from_value=existing_driver["driver_id"],
            to_value=None,
        ),
        "keycloak_user_id": AuditChange(
            from_value=existing_driver["keycloak_user_id"],
            to_value=None,
        ),
        "first_name": AuditChange(
            from_value=existing_driver.get("first_name"),
            to_value=None,
        ),
        "last_name": AuditChange(
            from_value=existing_driver.get("last_name"),
            to_value=None,
        ),
    }

    if existing_driver.get("fleet_id") is not None:
        driver_delete_changes["fleet_id"] = AuditChange(
            from_value=existing_driver["fleet_id"],
            to_value=None,
        )

    create_audit_log(
        AuditLogCreate(
            entity_type="DRIVER",
            entity_id=driver_id,
            action="DELETED",
            description=(
                f"Driver {driver_id} "
                f"({existing_driver.get('first_name')} "
                f"{existing_driver.get('last_name')}) was deleted"
            ),
            related_entities=AuditRelatedEntities(
                driver_id=driver_id,
                fleet_id=existing_driver.get("fleet_id"),
            ),
            changes=driver_delete_changes,
        )
    )

    # Για κάθε Vehicle που ήταν ανατεθειμένο στον Driver
    # δημιουργούμε ξεχωριστή εγγραφή audit.
    #
    # Έτσι το ιστορικό δείχνει ότι η αποδέσμευση δεν έγινε
    # με απλό Vehicle PATCH αλλά επειδή διαγράφηκε ο Driver.
    for vehicle_document in affected_vehicles:
        vehicle_id = str(vehicle_document["_id"])

        create_audit_log(
            AuditLogCreate(
                entity_type="VEHICLE",
                entity_id=vehicle_id,
                action="DRIVER_UNASSIGNED",
                description=(
                    f"Driver {driver_id} was unassigned from vehicle "
                    f"{vehicle_document['plate_number']} because the "
                    "driver was deleted"
                ),
                related_entities=AuditRelatedEntities(
                    vehicle_id=vehicle_id,
                    plate_number=vehicle_document["plate_number"],
                    fleet_id=vehicle_document.get("fleet_id"),
                    driver_id=driver_id,
                ),
                changes={
                    "driver_id": AuditChange(
                        from_value=driver_id,
                        to_value=None,
                    )
                },
            )
        )

    logger.info(
        "Deleted driver: driver_id=%s affected_vehicles=%s",
        driver_id,
        len(affected_vehicles),
    )

    return {
        "message": "Driver deleted successfully",
        "driver_id": driver_id,
        "unassigned_vehicles": len(affected_vehicles),
    }

@app.get("/drivers", response_model=list[DriverResponse])
def get_all_drivers():
    """
    Επιστρέφει όλα τα Driver Profiles από τη MongoDB.

    Το Fleet API παραμένει ο αποκλειστικός υπεύθυνος
    για την ανάγνωση των business δεδομένων των οδηγών.
    """

    driver_documents = drivers_collection.find().sort("driver_id", 1)

    return [
        driver_document_to_response(document)
        for document in driver_documents
    ]

@app.post( "/fleet-managers", response_model=FleetManagerResponse,)
def create_fleet_manager(    fleet_manager: FleetManagerCreate,):
    """
    Δημιουργεί νέο Fleet Manager Profile.

    Δεν επιτρέπουμε:
    - δύο managers με το ίδιο manager_id,
    - δύο profiles για το ίδιο Keycloak user.
    """

    existing_manager = fleet_managers_collection.find_one({ "manager_id": fleet_manager.manager_id })

    if existing_manager is not None:
        # Αν το ίδιο manager_id είναι ήδη συνδεδεμένο με το ίδιο
        # Keycloak identity, θεωρούμε το request ασφαλές retry.
        #
        # Επιστρέφουμε το υπάρχον Fleet Manager Profile αντί να
        # δημιουργήσουμε duplicate ή να επιστρέψουμε conflict.
        if ( existing_manager.get("keycloak_user_id") == fleet_manager.keycloak_user_id ):
            logger.info(
                "Fleet Manager already exists, returning existing profile: "
                "manager_id=%s keycloak_user_id=%s",
                fleet_manager.manager_id,
                fleet_manager.keycloak_user_id,
            )

            return fleet_manager_document_to_response(existing_manager)

        # Αν το ίδιο business ID αντιστοιχεί σε διαφορετικό Keycloak
        # identity, τότε πρόκειται για πραγματικό conflict.
        raise HTTPException(
            status_code=409,
            detail="Fleet Manager with this manager_id already exists",
        )

    existing_keycloak_user = fleet_managers_collection.find_one({
        "keycloak_user_id": fleet_manager.keycloak_user_id
    })

    if existing_keycloak_user is not None:
        # Αν το ίδιο Keycloak identity είναι ήδη συνδεδεμένο
        # με το ίδιο manager_id, θεωρούμε το request ασφαλές retry.
        if (
                existing_keycloak_user.get("manager_id")
                == fleet_manager.manager_id
        ):
            logger.info(
                "Fleet Manager already exists, returning existing profile: "
                "manager_id=%s keycloak_user_id=%s",
                fleet_manager.manager_id,
                fleet_manager.keycloak_user_id,
            )

            return fleet_manager_document_to_response(
                existing_keycloak_user
            )

        # Αν το ίδιο Keycloak identity είναι ήδη συνδεδεμένο
        # με διαφορετικό Fleet Manager Profile, έχουμε πραγματικό conflict.
        raise HTTPException(
            status_code=409,
            detail="Fleet Manager with this keycloak_user_id already exists",
        )
    # Μετατρέπουμε σε JSON-compatible dictionary
    # πριν από την αποθήκευση στη MongoDB.
    document = fleet_manager.model_dump(mode="json")

    # Κάθε Fleet Manager πρέπει να ανήκει σε πραγματικό Fleet,
    # επομένως επιβεβαιώνουμε το fleet_id πριν την αποθήκευση.
    validate_fleet_exists(fleet_manager.fleet_id)

    try:
        result = fleet_managers_collection.insert_one(document)

    except DuplicateKeyError:
        # Ένα ταυτόχρονο request μπορεί να δημιούργησε το ίδιο
        # Fleet Manager Profile αφού ολοκληρώθηκαν οι αρχικοί έλεγχοι.
        #
        # Ξαναδιαβάζουμε το profile ώστε να ξεχωρίσουμε ένα ασφαλές
        # retry από ένα πραγματικό conflict.
        existing_manager = fleet_managers_collection.find_one({ "manager_id": fleet_manager.manager_id })

        if ( existing_manager is not None and existing_manager.get("keycloak_user_id") == fleet_manager.keycloak_user_id ):
            logger.info(
                "Fleet Manager was created concurrently, "
                "returning existing profile: "
                "manager_id=%s keycloak_user_id=%s",
                fleet_manager.manager_id,
                fleet_manager.keycloak_user_id,
            )

            return fleet_manager_document_to_response(existing_manager)

        raise HTTPException(
            status_code=409,
            detail="Fleet Manager already exists",
        )

    created_manager = fleet_managers_collection.find_one({"_id": result.inserted_id})

    # Δημιουργούμε τα audit changes για τις βασικές business πληροφορίες
    # που αποκτά ο Fleet Manager κατά τη δημιουργία του.
    #
    # Δεν καταγράφουμε τιμές None → None, επειδή δεν αποτελούν
    # πραγματική αρχική κατάσταση που χρειάζεται να εμφανίζεται στο audit.
    audit_changes = {
        "manager_id": AuditChange(
            from_value=None,
            to_value=created_manager["manager_id"],
        ),
    }

    if created_manager.get("fleet_id") is not None:
        audit_changes["fleet_id"] = AuditChange(
            from_value=None,
            to_value=created_manager["fleet_id"],
        )

    # Καταγράφουμε τη δημιουργία του Fleet Manager στο μόνιμο audit trail.
    #
    # Χρησιμοποιούμε το manager_id ως σταθερό business identifier,
    # ώστε το ιστορικό να παραμένει αναζητήσιμο ακόμη και αν
    # το Fleet Manager Profile διαγραφεί αργότερα.
    create_audit_log(
        AuditLogCreate(
            entity_type="FLEET_MANAGER",
            entity_id=created_manager["manager_id"],
            action="CREATED",
            description=(
                f"Fleet Manager {created_manager['manager_id']} was created"
            ),
            related_entities=AuditRelatedEntities(
                manager_id=created_manager["manager_id"],
                fleet_id=created_manager.get("fleet_id"),
            ),
            changes=audit_changes,
        )
    )

    logger.info(
        "Created fleet manager: manager_id=%s fleet_id=%s",
        created_manager["manager_id"],
        created_manager.get("fleet_id"),
    )

    return fleet_manager_document_to_response(created_manager)

@app.get( "/fleet-managers", response_model=list[FleetManagerResponse],)
def get_all_fleet_managers():
    """
    Επιστρέφει όλα τα Fleet Manager Profiles από τη MongoDB.

    Το Fleet API παραμένει ο αποκλειστικός υπεύθυνος
    για την ανάγνωση των business δεδομένων των Fleet Managers.
    """

    fleet_manager_documents = ( fleet_managers_collection.find().sort("manager_id", 1) )

    return [
        fleet_manager_document_to_response(document)
        for document in fleet_manager_documents
    ]

@app.get( "/fleet-managers/by-keycloak-user/{keycloak_user_id}", response_model=FleetManagerResponse, )
def get_fleet_manager_by_keycloak_user(keycloak_user_id: str,):
    """
    Επιστρέφει το Fleet Manager Profile που αντιστοιχεί
    σε συγκεκριμένο Keycloak user.

    Το keycloak_user_id αντιστοιχεί στο claim "sub"
    του JWT που εκδίδει το Keycloak.
    """

    # Αναζητούμε τον Fleet Manager με βάση
    # το σταθερό Keycloak user id.
    fleet_manager_document = fleet_managers_collection.find_one({
        "keycloak_user_id": keycloak_user_id
    })

    if not fleet_manager_document:
        raise HTTPException(
            status_code=404,
            detail="Fleet manager not found for this Keycloak user",
        )

    return fleet_manager_document_to_response(
        fleet_manager_document
    )

@app.get( "/fleet-managers/by-keycloak-user/{keycloak_user_id}/vehicles", response_model=list[VehicleResponse],)
def get_fleet_manager_vehicles(keycloak_user_id: str,):
    """
    Επιστρέφει όλα τα vehicles του fleet που διαχειρίζεται
    ο συγκεκριμένος Fleet Manager.

    Πρώτα βρίσκουμε τον manager από το Keycloak user id
    και στη συνέχεια χρησιμοποιούμε το fleet_id του
    για να βρούμε τα vehicles του συγκεκριμένου fleet.
    """

    # Βρίσκουμε το business profile του Fleet Manager
    # χρησιμοποιώντας το Keycloak "sub".
    fleet_manager_document = fleet_managers_collection.find_one({
        "keycloak_user_id": keycloak_user_id
    })

    if not fleet_manager_document:
        raise HTTPException(
            status_code=404,
            detail="Fleet manager not found for this Keycloak user",
        )

    # Παίρνουμε το fleet_id που έχει ανατεθεί στον manager.
    fleet_id = fleet_manager_document["fleet_id"]

    # Αναζητούμε όλα τα vehicles που ανήκουν
    # στο συγκεκριμένο fleet.
    vehicle_documents = vehicles_collection.find({
        "fleet_id": fleet_id
    })

    return [
        vehicle_document_to_response(vehicle_document)
        for vehicle_document in vehicle_documents
    ]

@app.get( "/fleet-managers/by-keycloak-user/{keycloak_user_id}/drivers", response_model=list[DriverResponse],)
def get_fleet_manager_drivers( keycloak_user_id: str,):
    """
    Επιστρέφει όλους τους drivers του fleet που διαχειρίζεται
    ο συγκεκριμένος Fleet Manager.

    Πρώτα βρίσκουμε τον Fleet Manager μέσω του Keycloak user id
    και μετά χρησιμοποιούμε το fleet_id του για να αναζητήσουμε
    όλους τους drivers που ανήκουν στο συγκεκριμένο fleet.
    """

    # Βρίσκουμε το business profile του Fleet Manager
    # χρησιμοποιώντας το Keycloak "sub".
    fleet_manager_document = fleet_managers_collection.find_one({
        "keycloak_user_id": keycloak_user_id
    })

    if not fleet_manager_document:
        raise HTTPException(
            status_code=404,
            detail="Fleet manager not found for this Keycloak user",
        )

    # Παίρνουμε το fleet_id που διαχειρίζεται ο συγκεκριμένος manager.
    fleet_id = fleet_manager_document["fleet_id"]

    # Βρίσκουμε όλους τους drivers που ανήκουν
    # στο ίδιο fleet.
    driver_documents = drivers_collection.find({
        "fleet_id": fleet_id
    })

    return [
        driver_document_to_response(driver_document)
        for driver_document in driver_documents
    ]

@app.patch( "/fleet-managers/{manager_id}", response_model=FleetManagerResponse,)
def update_fleet_manager( manager_id: str, fleet_manager: FleetManagerUpdate, ):
    """
    Ενημερώνει μερικώς ένα Fleet Manager Profile.

    Το manager_id και το keycloak_user_id δεν μπορούν να αλλάξουν
    μέσω αυτού του endpoint, επειδή αποτελούν σταθερά identifiers.

    Αν αλλάξει το fleet_id του Fleet Manager:
    - ελέγχουμε ότι το νέο Fleet υπάρχει,
    - αλλάζουμε μόνο το Fleet του Manager,
    - δεν αλλάζουμε Drivers ή Vehicles του παλιού ή του νέου Fleet.

    Audit δημιουργείται μόνο όταν υπάρχει πραγματική αλλαγή.
    """

    # Διαβάζουμε την υπάρχουσα κατάσταση πριν από οποιαδήποτε αλλαγή.
    # Τη χρειαζόμαστε για validation και για το audit trail.
    existing_manager = fleet_managers_collection.find_one({
        "manager_id": manager_id
    })

    if existing_manager is None:
        raise HTTPException(
            status_code=404,
            detail="Fleet Manager not found",
        )

    # Παίρνουμε μόνο τα πεδία που έστειλε πραγματικά ο client.
    #
    # Το mode="json" μετατρέπει date και άλλα Pydantic values
    # σε μορφή κατάλληλη για αποθήκευση στη MongoDB.
    update_data = fleet_manager.model_dump(
        exclude_unset=True,
        mode="json",
    )

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No update data provided",
        )
    # Η ενεργοποίηση και η απενεργοποίηση γίνονται αποκλειστικά
    # από τα ειδικά lifecycle endpoints, ώστε να εφαρμόζονται
    # όλοι οι απαραίτητοι business κανόνες.
    if "status" in update_data:
        raise HTTPException(
            status_code=400,
            detail=(
                "Fleet Manager status cannot be changed through PATCH. "
                "Use the dedicated activation or deactivation endpoint."
            ),
        )

    old_fleet_id = existing_manager.get("fleet_id")

    # Αν το PATCH περιλαμβάνει fleet_id, ελέγχουμε ότι το νέο Fleet
    # υπάρχει. Το None επιτρέπεται και σημαίνει ότι ο Manager
    # δεν είναι προσωρινά ανατεθειμένος σε κάποιο Fleet.
    if "fleet_id" in update_data:
        validate_fleet_exists(update_data["fleet_id"])

    new_fleet_id = update_data.get(
        "fleet_id",
        old_fleet_id,
    )

    fleet_changed = old_fleet_id != new_fleet_id

    # Ενημερώνουμε αποκλειστικά τα πεδία που έστειλε ο client.
    #
    # Δεν υπάρχει cascade προς Drivers ή Vehicles.
    # Το fleet_id του Manager καθορίζει ποιο Fleet διαχειρίζεται,
    # όχι την ιδιοκτησία των οντοτήτων του Fleet.
    result = fleet_managers_collection.update_one(
        {"manager_id": manager_id},
        {"$set": update_data},
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=404,
            detail="Fleet Manager not found",
        )

    updated_manager = fleet_managers_collection.find_one({
        "manager_id": manager_id
    })

    # Καταγράφουμε μόνο τα πεδία που άλλαξαν πραγματικά.
    # Αν ο client έστειλε την ίδια τιμή που υπήρχε ήδη,
    # αυτή δεν θεωρείται business αλλαγή.
    audit_changes = {}

    for field_name in update_data:
        old_value = existing_manager.get(field_name)
        new_value = updated_manager.get(field_name)

        if old_value != new_value:
            audit_changes[field_name] = AuditChange(
                from_value=old_value,
                to_value=new_value,
            )

    # Αν άλλαξε πραγματικά το Fleet, χρησιμοποιούμε ειδικό action
    # ώστε το business history να ξεχωρίζει τις μετακινήσεις Manager.
    if fleet_changed:
        audit_action = "FLEET_CHANGED"

        if old_fleet_id is None:
            audit_description = (
                f"Fleet Manager {manager_id} was assigned "
                f"to fleet {new_fleet_id}"
            )

        elif new_fleet_id is None:
            audit_description = (
                f"Fleet Manager {manager_id} was removed "
                f"from fleet {old_fleet_id}"
            )

        else:
            audit_description = (
                f"Fleet Manager {manager_id} changed fleet "
                f"from {old_fleet_id} to {new_fleet_id}"
            )

    else:
        audit_action = "UPDATED"
        audit_description = (
            f"Fleet Manager {manager_id} was updated"
        )

    # Δεν δημιουργούμε audit μόνο και μόνο επειδή έγινε PATCH.
    # Πρέπει να έχει αλλάξει πραγματικά τουλάχιστον ένα πεδίο.
    if audit_changes:
        create_audit_log(
            AuditLogCreate(
                entity_type="FLEET_MANAGER",
                entity_id=manager_id,
                action=audit_action,
                description=audit_description,
                related_entities=AuditRelatedEntities(
                    manager_id=manager_id,
                    fleet_id=updated_manager.get("fleet_id"),
                ),
                changes=audit_changes,
            )
        )

    logger.info(
        "Updated fleet manager: manager_id=%s fleet_id=%s",
        manager_id,
        updated_manager.get("fleet_id"),
    )

    return fleet_manager_document_to_response(updated_manager)

@app.post("/fleet-managers/{manager_id}/activate", response_model=FleetManagerResponse, )
def activate_fleet_manager(manager_id: str):
    """
    Επανενεργοποιεί το Fleet Manager Profile.

    Η ενεργοποίηση αφορά μόνο την business κατάσταση
    του Fleet Manager μέσα στο Fleet API.

    Το αντίστοιχο Keycloak account ενεργοποιείται
    ξεχωριστά από το API Gateway.
    """

    # Βρίσκουμε τον Fleet Manager από το μοναδικό business ID.
    existing_manager = fleet_managers_collection.find_one({
        "manager_id": manager_id
    })

    if existing_manager is None:
        raise HTTPException(
            status_code=404,
            detail="Fleet Manager not found",
        )

    # Αν ο Fleet Manager είναι ήδη ενεργός, η επιθυμητή κατάσταση
    # έχει ήδη επιτευχθεί. Δεν δημιουργούμε δεύτερο audit event.
    if existing_manager.get("status") == "ACTIVE":
        return fleet_manager_document_to_response(existing_manager)

    # Αλλάζουμε αποκλειστικά την business κατάσταση.
    # Δεν αλλάζουμε το Fleet στο οποίο ανήκει ο Manager.
    fleet_managers_collection.update_one(
        {"manager_id": manager_id},
        {"$set": {"status": "ACTIVE"}},
    )

    updated_manager = fleet_managers_collection.find_one({
        "manager_id": manager_id
    })

    # Καταγράφουμε την επανενεργοποίηση στο μόνιμο audit trail.
    create_audit_log(
        AuditLogCreate(
            entity_type="FLEET_MANAGER",
            entity_id=manager_id,
            action="ACTIVATED",
            description=f"Fleet Manager {manager_id} was activated",
            related_entities=AuditRelatedEntities(
                manager_id=manager_id,
                fleet_id=existing_manager.get("fleet_id"),
            ),
            changes={
                "status": AuditChange(
                    from_value=existing_manager.get("status"),
                    to_value="ACTIVE",
                ),
            },
        )
    )

    logger.info(
        "Activated fleet manager: manager_id=%s",
        manager_id,
    )

    return fleet_manager_document_to_response(updated_manager)

@app.post( "/fleet-managers/{manager_id}/deactivate", response_model=FleetManagerResponse,)
def deactivate_fleet_manager(manager_id: str):
    """
    Απενεργοποιεί ένα Fleet Manager Profile χωρίς να το διαγράφει.

    Ο Fleet Manager παραμένει συνδεδεμένος με το Fleet του.
    Δεν επηρεάζονται Drivers, Vehicles ή άλλα business δεδομένα.

    Το αντίστοιχο Keycloak account απενεργοποιείται
    ξεχωριστά από το API Gateway.
    """

    # Διαβάζουμε τον Fleet Manager πριν από οποιαδήποτε αλλαγή.
    existing_manager = fleet_managers_collection.find_one({
        "manager_id": manager_id
    })

    if existing_manager is None:
        raise HTTPException(
            status_code=404,
            detail="Fleet Manager not found",
        )

    # Αν είναι ήδη ανενεργός, η επιθυμητή κατάσταση έχει ήδη επιτευχθεί.
    # Δεν δημιουργούμε δεύτερο audit event.
    if existing_manager.get("status") == "INACTIVE":
        return fleet_manager_document_to_response(existing_manager)

    # Διατηρούμε ολόκληρο το Fleet Manager Profile και αλλάζουμε
    # αποκλειστικά την business κατάστασή του.
    fleet_managers_collection.update_one(
        {"manager_id": manager_id},
        {"$set": {"status": "INACTIVE"}},
    )

    updated_manager = fleet_managers_collection.find_one({
        "manager_id": manager_id
    })

    # Καταγράφουμε την απενεργοποίηση στο μόνιμο audit trail.
    create_audit_log(
        AuditLogCreate(
            entity_type="FLEET_MANAGER",
            entity_id=manager_id,
            action="DEACTIVATED",
            description=f"Fleet Manager {manager_id} was deactivated",
            related_entities=AuditRelatedEntities(
                manager_id=manager_id,
                fleet_id=existing_manager.get("fleet_id"),
            ),
            changes={
                "status": AuditChange(
                    from_value=existing_manager.get("status", "ACTIVE"),
                    to_value="INACTIVE",
                ),
            },
        )
    )

    logger.info(
        "Deactivated fleet manager: manager_id=%s",
        manager_id,
    )

    return fleet_manager_document_to_response(updated_manager)

@app.delete("/fleet-managers/{manager_id}")
def delete_fleet_manager(manager_id: str):
    """
    Διαγράφει ένα Fleet Manager Profile από το Fleet API.

    Η διαγραφή αφορά μόνο το business profile του Fleet Manager.

    Δεν επηρεάζονται:
    - το Fleet που διαχειριζόταν,
    - οι Drivers του Fleet,
    - τα Vehicles του Fleet.

    Σε αυτή τη φάση δεν διαγράφεται το αντίστοιχο Keycloak account.
    Η διαχείριση του Keycloak identity θα ενσωματωθεί αργότερα
    στο ολοκληρωμένο Admin identity lifecycle.
    """

    # Διαβάζουμε πρώτα τον Fleet Manager πριν από τη διαγραφή,
    # επειδή χρειαζόμαστε την τελευταία κατάστασή του για το audit trail.
    existing_manager = fleet_managers_collection.find_one({
        "manager_id": manager_id
    })

    if existing_manager is None:
        raise HTTPException(
            status_code=404,
            detail="Fleet Manager not found",
        )
    # Το Hard Delete επιτρέπεται μόνο αφού ο Fleet Manager
    # έχει πρώτα απενεργοποιηθεί μέσω του lifecycle endpoint.
    #
    # Έτσι διαχωρίζουμε καθαρά το Soft Delete (INACTIVE)
    # από την οριστική διαγραφή του business profile.
    if existing_manager.get("status") != "INACTIVE":
        raise HTTPException(
            status_code=409,
            detail=(
                "Fleet Manager must be deactivated before hard delete"
            ),
        )
    # Διαγράφουμε μόνο το business Fleet Manager Profile.
    #
    # Δεν υπάρχει cascade προς Fleet, Drivers ή Vehicles,
    # επειδή ο Manager διαχειρίζεται το Fleet αλλά δεν είναι
    # ιδιοκτήτης των business entities που ανήκουν σε αυτό.
    result = fleet_managers_collection.delete_one({ "manager_id": manager_id })

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=500,
            detail="Fleet Manager could not be deleted",
        )

    # Κρατάμε στο μόνιμο audit trail τις βασικές business πληροφορίες
    # του Manager που υπήρχαν ακριβώς πριν από τη διαγραφή.
    #
    # Δεν αντιγράφουμε ευαίσθητα προσωπικά δεδομένα όπως tax_id,
    # identity_card_number, email ή phone_number στο audit log.
    manager_delete_changes = {
        "manager_id": AuditChange(
            from_value=existing_manager["manager_id"],
            to_value=None,
        ),

        # Κρατάμε το Keycloak user ID στο audit της οριστικής διαγραφής.
        #
        # Μετά το Hard Delete το Fleet Manager Profile δεν υπάρχει πλέον.
        # Το identifier αυτό επιτρέπει στο API Gateway να ολοκληρώσει
        # ή να επαναλάβει με ασφάλεια τη διαγραφή του αντίστοιχου
        # Keycloak identity αν χαθεί η απάντηση από το Fleet API.
        "keycloak_user_id": AuditChange(
            from_value=existing_manager["keycloak_user_id"],
            to_value=None,
        ),

        "first_name": AuditChange(
            from_value=existing_manager.get("first_name"),
            to_value=None,
        ),
        "last_name": AuditChange(
            from_value=existing_manager.get("last_name"),
            to_value=None,
        ),
    }

    if existing_manager.get("fleet_id") is not None:
        manager_delete_changes["fleet_id"] = AuditChange(
            from_value=existing_manager["fleet_id"],
            to_value=None,
        )

    create_audit_log(
        AuditLogCreate(
            entity_type="FLEET_MANAGER",
            entity_id=manager_id,
            action="DELETED",
            description=(
                f"Fleet Manager {manager_id} "
                f"({existing_manager.get('first_name')} "
                f"{existing_manager.get('last_name')}) was deleted"
            ),
            related_entities=AuditRelatedEntities(
                manager_id=manager_id,
                fleet_id=existing_manager.get("fleet_id"),
            ),
            changes=manager_delete_changes,
        )
    )

    logger.info(
        "Deleted fleet manager: manager_id=%s fleet_id=%s",
        manager_id,
        existing_manager.get("fleet_id"),
    )

    return {
        "message": "Fleet Manager deleted successfully",
        "manager_id": manager_id,
    }

@app.post("/fleets", response_model=FleetResponse, status_code=201)
def create_fleet(fleet: FleetCreate):
    """
    Δημιουργεί ένα νέο fleet της εταιρείας.

    Το fleet_id είναι μοναδικό business identifier και δεν επιτρέπεται
    να χρησιμοποιείται από περισσότερα από ένα fleets.

    Τα created_at και updated_at δημιουργούνται από το backend,
    ώστε ο client να μην μπορεί να καθορίσει ή να αλλοιώσει
    τα timestamps του fleet.
    """

    # Ελέγχουμε αν υπάρχει ήδη fleet με το ίδιο business identifier.
    existing_fleet = fleets_collection.find_one({
        "fleet_id": fleet.fleet_id
    })

    if existing_fleet:
        raise HTTPException(
            status_code=409,
            detail="Fleet with this fleet_id already exists",
        )

    # Χρησιμοποιούμε timezone-aware UTC timestamp.
    # Στη δημιουργία του fleet τα created_at και updated_at
    # έχουν φυσικά την ίδια αρχική τιμή.
    current_time = datetime.now(timezone.utc)

    # Το mode="json" μετατρέπει τα nested Pydantic models,
    # όπως το BaseLocation, σε δεδομένα κατάλληλα για αποθήκευση.
    document = fleet.model_dump(mode="json")

    # Τα timestamps ελέγχονται αποκλειστικά από το backend.
    document["created_at"] = current_time
    document["updated_at"] = current_time

    result = fleets_collection.insert_one(document)

    # Διαβάζουμε ξανά το document από τη MongoDB ώστε το response
    # να δημιουργηθεί από την πραγματική αποθηκευμένη εγγραφή
    # και να περιλαμβάνει το MongoDB _id.
    created_fleet = fleets_collection.find_one({"_id": result.inserted_id})

    if created_fleet is None:
        raise HTTPException(status_code=500, detail="Fleet was created but could not be retrieved",)

    # Καταγράφουμε τη δημιουργία του Fleet στο μόνιμο audit trail.
    #
    # Το fleet_id αποτελεί το business identifier του Fleet και γι' αυτό
    # καταγράφεται ως η βασική αρχική τιμή κατά τη δημιουργία.
    create_audit_log(
        AuditLogCreate(
            entity_type="FLEET",
            entity_id=created_fleet["fleet_id"],
            action="CREATED",
            description=(
                f"Fleet {created_fleet['fleet_id']} was created"
            ),
            related_entities=AuditRelatedEntities(
                fleet_id=created_fleet["fleet_id"],
            ),
            changes={
                "fleet_id": AuditChange(
                    from_value=None,
                    to_value=created_fleet["fleet_id"],
                )
            },
        )
    )

    logger.info(
        "Created fleet: fleet_id=%s name=%s",
        created_fleet["fleet_id"],
        created_fleet["name"],
    )

    return fleet_document_to_response(created_fleet)

@app.get("/fleets", response_model=list[FleetResponse])
def get_fleets():
    """
    Επιστρέφει όλα τα fleets της εταιρείας.

    Το endpoint αυτό θα χρησιμοποιηθεί κυρίως από τον Admin,
    ώστε να μπορεί να βλέπει τη συνολική λίστα των fleets.
    """

    fleet_documents = fleets_collection.find()

    return [
        fleet_document_to_response(document)
        for document in fleet_documents
    ]

@app.get("/fleets/{fleet_id}", response_model=FleetResponse)
def get_fleet(fleet_id: str):
    """
    Επιστρέφει ένα συγκεκριμένο fleet με βάση το business fleet_id.

    Χρησιμοποιούμε το fleet_id και όχι το MongoDB _id,
    επειδή το fleet_id είναι το business identifier που χρησιμοποιείται
    και στις σχέσεις με Fleet Managers, Drivers και Vehicles.
    """

    fleet_document = fleets_collection.find_one({
        "fleet_id": fleet_id
    })

    if fleet_document is None:
        raise HTTPException(
            status_code=404,
            detail="Fleet not found",
        )

    return fleet_document_to_response(fleet_document)

@app.patch("/fleets/{fleet_id}", response_model=FleetResponse)
def update_fleet(fleet_id: str, fleet_update: FleetUpdate):
    """
    Ενημερώνει τα στοιχεία ενός υπάρχοντος fleet.

    Αν αλλάξει το business identifier fleet_id, το Fleet API ενημερώνει
    και όλες τις business οντότητες που ανήκουν στο συγκεκριμένο fleet.

    Η συγκεκριμένη συσχέτιση βρίσκεται εξ ολοκλήρου μέσα στο Fleet API,
    επειδή τα fleets, fleet managers, drivers και vehicles αποτελούν
    business δεδομένα που ανήκουν στο ίδιο service.
    """

    # Βρίσκουμε πρώτα το υπάρχον fleet ώστε να γνωρίζουμε
    # ότι το fleet_id του URL αντιστοιχεί σε πραγματικό fleet.
    existing_fleet = fleets_collection.find_one({
        "fleet_id": fleet_id
    })

    if existing_fleet is None:
        raise HTTPException(
            status_code=404,
            detail="Fleet not found",
        )

    # Κρατάμε μόνο τα πεδία που έστειλε πραγματικά ο client.
    # Έτσι το PATCH μπορεί να αλλάξει ένα μόνο πεδίο χωρίς
    # να αντικαταστήσει τα υπόλοιπα με None.
    update_data = fleet_update.model_dump( mode="json", exclude_unset=True, )

    # Αν ο client δεν έστειλε κανένα πεδίο προς ενημέρωση,
    # δεν υπάρχει πραγματική ενέργεια PATCH που μπορούμε να εκτελέσουμε.
    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No update data provided",
        )

    new_fleet_id = update_data.get("fleet_id")

    # Αν ζητείται πραγματική αλλαγή του fleet_id,
    # πρέπει πρώτα να βεβαιωθούμε ότι το νέο business ID
    # δεν χρησιμοποιείται ήδη από άλλο fleet.
    if new_fleet_id and new_fleet_id != fleet_id:
        fleet_with_new_id = fleets_collection.find_one({
            "fleet_id": new_fleet_id
        })

        if fleet_with_new_id is not None:
            raise HTTPException(
                status_code=409,
                detail="Fleet with this fleet_id already exists",
            )

        # Ενημερώνουμε τα references στις υπόλοιπες business
        # οντότητες που ανήκουν στο συγκεκριμένο fleet.
        fleet_managers_result = fleet_managers_collection.update_many(
            {"fleet_id": fleet_id},
            {"$set": {"fleet_id": new_fleet_id}},
        )

        drivers_result = drivers_collection.update_many(
            {"fleet_id": fleet_id},
            {"$set": {"fleet_id": new_fleet_id}},
        )

        vehicles_result = vehicles_collection.update_many(
            {"fleet_id": fleet_id},
            {"$set": {"fleet_id": new_fleet_id}},
        )

        logger.info(
            (
                "Updated fleet references: old_fleet_id=%s "
                "new_fleet_id=%s fleet_managers=%s drivers=%s vehicles=%s"
            ),
            fleet_id,
            new_fleet_id,
            fleet_managers_result.modified_count,
            drivers_result.modified_count,
            vehicles_result.modified_count,
        )

    # Κάθε αλλαγή στο fleet ενημερώνει το updated_at.
    update_data["updated_at"] = datetime.now(timezone.utc)

    fleets_collection.update_one(
        {"_id": existing_fleet["_id"]},
        {"$set": update_data},
    )

    # Χρησιμοποιούμε το νέο fleet_id αν άλλαξε.
    # Διαφορετικά συνεχίζουμε με το υπάρχον.
    effective_fleet_id = new_fleet_id or fleet_id

    updated_fleet = fleets_collection.find_one({
        "fleet_id": effective_fleet_id
    })

    if updated_fleet is None:
        raise HTTPException(
            status_code=500,
            detail="Fleet was updated but could not be retrieved",
        )

    # Δημιουργούμε audit changes μόνο για τα business πεδία
    # που άλλαξαν πραγματικά μετά το PATCH.
    #
    # Δεν χρησιμοποιούμε το updated_at για να αποφασίσουμε αν υπάρχει
    # business αλλαγή, επειδή είναι τεχνικό timestamp που ενημερώνεται
    # από το backend και όχι πεδίο που άλλαξε ο χρήστης.
    audit_changes = {}

    for field_name in fleet_update.model_dump(
            mode="json",
            exclude_unset=True,
    ):
        old_value = existing_fleet.get(field_name)
        new_value = updated_fleet.get(field_name)

        if old_value != new_value:
            audit_changes[field_name] = AuditChange(
                from_value=old_value,
                to_value=new_value,
            )

    # Αν άλλαξε το business identifier του Fleet, χρησιμοποιούμε
    # ξεχωριστό action ώστε το audit history να δείχνει καθαρά
    # ότι πρόκειται για αλλαγή του fleet_id και όχι για απλό update.
    #
    # Τα references σε Fleet Managers, Drivers και Vehicles έχουν ήδη
    # ενημερωθεί από το υπάρχον cascade παραπάνω.
    if (
            "fleet_id" in audit_changes
            and existing_fleet["fleet_id"] != updated_fleet["fleet_id"]
    ):
        audit_action = "ID_CHANGED"
        audit_description = (
            f"Fleet ID changed from {existing_fleet['fleet_id']} "
            f"to {updated_fleet['fleet_id']}"
        )

    else:
        audit_action = "UPDATED"
        audit_description = (
            f"Fleet {updated_fleet['fleet_id']} was updated"
        )

    # Όπως και στα Vehicle, Driver και Fleet Manager,
    # audit δημιουργείται μόνο όταν υπάρχει πραγματική business αλλαγή.
    #
    # PATCH με την ίδια ακριβώς τιμή δεν δημιουργεί άχρηστη
    # εγγραφή UPDATED στο ιστορικό.
    if audit_changes:
        create_audit_log(
            AuditLogCreate(
                entity_type="FLEET",
                entity_id=updated_fleet["fleet_id"],
                action=audit_action,
                description=audit_description,
                related_entities=AuditRelatedEntities(
                    fleet_id=updated_fleet["fleet_id"],
                ),
                changes=audit_changes,
            )
        )

    logger.info(
        "Updated fleet: fleet_id=%s",
        effective_fleet_id,
    )

    return fleet_document_to_response(updated_fleet)

@app.delete("/fleets/{fleet_id}")
def delete_fleet(fleet_id: str):
    """
    Διαγράφει ένα Fleet μόνο όταν δεν υπάρχουν άλλες business οντότητες
    που εξακολουθούν να αναφέρονται σε αυτό.

    Δεν κάνουμε αυτόματο cascade delete σε Fleet Managers, Drivers ή Vehicles,
    επειδή η διαγραφή ενός Fleet δεν πρέπει να προκαλεί απώλεια των
    σχετικών business δεδομένων.
    """

    # Ελέγχουμε πρώτα ότι το Fleet που ζητήθηκε υπάρχει.
    existing_fleet = fleets_collection.find_one({
        "fleet_id": fleet_id
    })

    if existing_fleet is None:
        raise HTTPException(
            status_code=404,
            detail="Fleet not found",
        )

    # Ελέγχουμε αν υπάρχει Fleet Manager που εξακολουθεί
    # να είναι συνδεδεμένος με αυτό το Fleet.
    fleet_manager = fleet_managers_collection.find_one({
        "fleet_id": fleet_id
    })

    # Ελέγχουμε αν υπάρχει Driver που εξακολουθεί
    # να ανήκει σε αυτό το Fleet.
    driver = drivers_collection.find_one({
        "fleet_id": fleet_id
    })

    # Ελέγχουμε αν υπάρχει Vehicle που εξακολουθεί
    # να ανήκει σε αυτό το Fleet.
    vehicle = vehicles_collection.find_one({
        "fleet_id": fleet_id
    })

    # Αν υπάρχει έστω μία σχετική οντότητα, δεν επιτρέπουμε
    # τη διαγραφή γιατί διαφορετικά θα δημιουργούσαμε orphan references.
    if fleet_manager is not None or driver is not None or vehicle is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Fleet cannot be deleted because Fleet Managers, "
                "Drivers or Vehicles are still assigned to it"
            ),
        )

    # Αφού επιβεβαιώσαμε ότι δεν υπάρχουν references,
    # μπορούμε να διαγράψουμε με ασφάλεια το Fleet.
    result = fleets_collection.delete_one({
        "_id": existing_fleet["_id"]
    })

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=500,
            detail="Fleet could not be deleted",
        )

    # Καταγράφουμε τη διαγραφή του Fleet στο μόνιμο audit trail.
    #
    # Επειδή το Fleet δεν υπάρχει πλέον μετά τη διαγραφή,
    # κρατάμε τις βασικές business πληροφορίες που χρειαζόμαστε
    # για να μπορούμε να αναγνωρίσουμε ιστορικά ποιο Fleet διαγράφηκε.
    fleet_delete_changes = {
        "fleet_id": AuditChange(
            from_value=existing_fleet["fleet_id"],
            to_value=None,
        ),
        "name": AuditChange(
            from_value=existing_fleet.get("name"),
            to_value=None,
        ),
    }

    create_audit_log(
        AuditLogCreate(
            entity_type="FLEET",
            entity_id=existing_fleet["fleet_id"],
            action="DELETED",
            description=(
                f"Fleet {existing_fleet['fleet_id']} "
                f"({existing_fleet.get('name')}) was deleted"
            ),
            related_entities=AuditRelatedEntities(
                fleet_id=existing_fleet["fleet_id"],
            ),
            changes=fleet_delete_changes,
        )
    )

    logger.info("Deleted fleet: fleet_id=%s", fleet_id)

    return {
        "message": "Fleet deleted successfully",
        "fleet_id": fleet_id,
    }

@app.get("/audit-logs", response_model=list[AuditLogResponse])
def get_audit_logs():
    """
    Επιστρέφει το audit history με τις πιο πρόσφατες αλλαγές πρώτες.

    Το endpoint θα χρησιμοποιηθεί αργότερα από το Admin Dashboard
    για την προβολή του συνολικού ιστορικού αλλαγών.
    """

    documents = audit_logs_collection.find().sort("timestamp", -1)

    return [
        audit_log_document_to_response(document)
        for document in documents
    ]

@app.get( "/audit-logs/{entity_type}/{entity_id}", response_model=list[AuditLogResponse],)
def get_entity_audit_logs(entity_type: str, entity_id: str):
    """
    Επιστρέφει το audit history μιας συγκεκριμένης business οντότητας.

    Για παράδειγμα μπορούμε να ζητήσουμε το ιστορικό ενός Vehicle,
    Driver ή Fleet χωρίς να διαβάζουμε ολόκληρο το audit trail.
    """

    documents = audit_logs_collection.find({
        "entity_type": entity_type.upper(),
        "entity_id": entity_id,
    }).sort("timestamp", -1)

    return [
        audit_log_document_to_response(document)
        for document in documents
    ]