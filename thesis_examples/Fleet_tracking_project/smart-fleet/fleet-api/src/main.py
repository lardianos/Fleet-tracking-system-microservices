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
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pymongo import MongoClient
from bson import ObjectId
from datetime import date
from pydantic import BaseModel, EmailStr

from kafka_producer import FleetEventProducer

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
