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
        raise HTTPException(
            status_code=409,
            detail="Vehicle with this device IMEI already exists",
        )

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