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
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pymongo import MongoClient
from bson import ObjectId
from datetime import date
from pydantic import BaseModel, EmailStr
from datetime import datetime, timezone

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

# Αποθηκεύει τα business profiles των Fleet Managers.
# Το Keycloak παραμένει υπεύθυνο για authentication και roles,
# ενώ εδώ κρατάμε τη σχέση του manager με το fleet που διαχειρίζεται.
fleet_managers_collection = database["fleet_managers"]

# Αποθηκεύει τα business δεδομένα των fleets.
# Κάθε fleet αποτελεί την κεντρική οντότητα που συνδέει
# τους Fleet Managers, τους Drivers και τα Vehicles του ίδιου στόλου.
fleets_collection = database["fleets"]

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
    status: str = "ACTIVE"

class VehicleResponse(VehicleCreate):
    # Το id είναι το MongoDB ObjectId σε μορφή string.
    id: str

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
    status: str | None = None

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

    # Αν έχει δοθεί fleet_id, επιβεβαιώνουμε ότι αντιστοιχεί
    # σε πραγματικό Fleet πριν αποθηκεύσουμε το Vehicle.
    validate_fleet_exists(vehicle.fleet_id)

    result = vehicles_collection.insert_one(document)

    created_vehicle = vehicles_collection.find_one({"_id": result.inserted_id})
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

    update_data = vehicle.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException( status_code=400, detail="No update data provided", )

    # Αν το PATCH περιλαμβάνει αλλαγή του fleet_id,
    # επιβεβαιώνουμε ότι το νέο Fleet υπάρχει πριν ενημερωθεί το Vehicle.
    #
    # Ελέγχουμε την ύπαρξη του πεδίου στο update_data και όχι απλώς
    # την τιμή του, επειδή το fleet_id=None είναι έγκυρη επιλογή
    # για Vehicle και σημαίνει ότι το όχημα δεν ανήκει σε κάποιο fleet.
    if "fleet_id" in update_data:
        validate_fleet_exists(update_data["fleet_id"])
        
    # Ενημερώνουμε μόνο τα πεδία που έστειλε ο client.
    result = vehicles_collection.update_one( {"_id": ObjectId(vehicle_id)}, {"$set": update_data}, )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    updated_vehicle = vehicles_collection.find_one( {"_id": ObjectId(vehicle_id) } )

    return vehicle_document_to_response(updated_vehicle)


@app.delete("/vehicles/{vehicle_id}")
def delete_vehicle(vehicle_id: str):
    # Ελέγχουμε ότι το id είναι έγκυρο MongoDB ObjectId.
    if not ObjectId.is_valid(vehicle_id):
        raise HTTPException(status_code=400, detail="Invalid vehicle id")

    result = vehicles_collection.delete_one(
        {"_id": ObjectId(vehicle_id)}
    )

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    return { "message": "Vehicle deleted successfully", "vehicle_id": vehicle_id, }


"""
    Δημιουργεί νέο Driver Profile στη MongoDB.

    Δεν επιτρέπουμε:
    - δύο drivers με το ίδιο driver_id,
    - δύο drivers να αντιστοιχούν στο ίδιο Keycloak user.
"""
@app.post("/drivers", response_model=DriverResponse)
def create_driver(driver: DriverCreate):
    # Ελέγχουμε αν υπάρχει ήδη το ίδιο business driver_id.
    existing_driver_id = drivers_collection.find_one({"driver_id": driver.driver_id})

    if existing_driver_id:
        raise HTTPException(
            status_code=409,
            detail="Driver with this driver_id already exists",
        )

    # Ελέγχουμε αν το συγκεκριμένο Keycloak identity
    # έχει ήδη συνδεθεί με άλλο Driver Profile.
    existing_keycloak_user = drivers_collection.find_one({
        "keycloak_user_id": driver.keycloak_user_id
    })

    if existing_keycloak_user:
        raise HTTPException(
            status_code=409,
            detail="Driver with this Keycloak user already exists",
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

    result = drivers_collection.insert_one(document)

    # Διαβάζουμε ξανά το document όπως αποθηκεύτηκε
    # ώστε να επιστρέψουμε και το MongoDB ObjectId.
    created_driver = drivers_collection.find_one({
        "_id": result.inserted_id
    })

    return driver_document_to_response(created_driver)

@app.get(
    "/drivers/by-keycloak-user/{keycloak_user_id}",
    response_model=DriverResponse,
)
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

@app.get(
    "/drivers/{driver_id}/vehicles",
    response_model=list[VehicleResponse],
)
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

@app.get(
    "/drivers/by-keycloak-user/{keycloak_user_id}/vehicles",
    response_model=list[VehicleResponse],
)
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

@app.post(
    "/fleet-managers",
    response_model=FleetManagerResponse,
)
def create_fleet_manager(
    fleet_manager: FleetManagerCreate,
):
    """
    Δημιουργεί νέο Fleet Manager Profile.

    Δεν επιτρέπουμε:
    - δύο managers με το ίδιο manager_id,
    - δύο profiles για το ίδιο Keycloak user.
    """

    existing_manager_id = fleet_managers_collection.find_one({
        "manager_id": fleet_manager.manager_id
    })

    if existing_manager_id:
        raise HTTPException(
            status_code=409,
            detail="Fleet manager with this manager_id already exists",
        )

    existing_keycloak_user = fleet_managers_collection.find_one({
        "keycloak_user_id": fleet_manager.keycloak_user_id
    })

    if existing_keycloak_user:
        raise HTTPException(
            status_code=409,
            detail="Fleet manager with this Keycloak user already exists",
        )

    # Μετατρέπουμε σε JSON-compatible dictionary
    # πριν από την αποθήκευση στη MongoDB.
    document = fleet_manager.model_dump(mode="json")

    # Κάθε Fleet Manager πρέπει να ανήκει σε πραγματικό Fleet,
    # επομένως επιβεβαιώνουμε το fleet_id πριν την αποθήκευση.
    validate_fleet_exists(fleet_manager.fleet_id)

    result = fleet_managers_collection.insert_one(document)

    created_manager = fleet_managers_collection.find_one({
        "_id": result.inserted_id
    })

    return fleet_manager_document_to_response(created_manager)

@app.get(
    "/fleet-managers/by-keycloak-user/{keycloak_user_id}",
    response_model=FleetManagerResponse,
)
def get_fleet_manager_by_keycloak_user(
    keycloak_user_id: str,
):
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
@app.get(
    "/fleet-managers/by-keycloak-user/{keycloak_user_id}/vehicles",
    response_model=list[VehicleResponse],
)
def get_fleet_manager_vehicles(
    keycloak_user_id: str,
):
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

@app.get(
    "/fleet-managers/by-keycloak-user/{keycloak_user_id}/drivers",
    response_model=list[DriverResponse],
)
def get_fleet_manager_drivers(
    keycloak_user_id: str,
):
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
    created_fleet = fleets_collection.find_one({
        "_id": result.inserted_id
    })

    if created_fleet is None:
        raise HTTPException(
            status_code=500,
            detail="Fleet was created but could not be retrieved",
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
    update_data = fleet_update.model_dump(
        mode="json",
        exclude_unset=True,
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

    logger.info(
        "Updated fleet: fleet_id=%s",
        effective_fleet_id,
    )

    return fleet_document_to_response(updated_fleet)