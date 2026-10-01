from datetime import date

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class AdminDriverCreate(BaseModel):
    """
    Δεδομένα που υποβάλλει ο Admin για τη δημιουργία οδηγού.

    Το keycloak_user_id δεν παρέχεται από τον Admin.
    Θα συμπληρώνεται από το API Gateway μετά τη δημιουργία
    του αντίστοιχου χρήστη στο Keycloak.
    """

    # Στοιχεία που χρησιμοποιούνται για τη δημιουργία
    # και την ταυτοποίηση του λογαριασμού στο Keycloak.
    username: str = Field(min_length=3)
    email: EmailStr

    # Business identifier και προσωπικά στοιχεία του οδηγού.
    driver_id: str = Field(min_length=1)
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    date_of_birth: date | None = None

    # Πρόσθετα στοιχεία ταυτοποίησης και επικοινωνίας.
    identity_card_number: str | None = None
    tax_id: str | None = None
    phone_number: str | None = None

    # Στοιχεία της άδειας οδήγησης.
    license_number: str | None = None
    license_category: str | None = None
    license_expiry_date: date | None = None

    # Στοιχεία απασχόλησης και συσχέτισης με τον στόλο.
    hire_date: date | None = None
    fleet_id: str | None = None
    department_id: str | None = None
    status: str = "ACTIVE"

class AdminDriverUpdate(BaseModel):
    """
    Πεδία που επιτρέπεται να ενημερώνει ο Admin.

    Τα προσωπικά στοιχεία συγχρονίζονται με το Keycloak.
    Τα υπόλοιπα ανήκουν στο Driver Profile του Fleet API.
    """

    model_config = ConfigDict(extra="forbid")

    # Τα πεδία αυτά υπάρχουν και στο Keycloak.
    first_name: str = Field(min_length=1, default=None)
    last_name: str = Field(min_length=1, default=None)
    email: EmailStr = None

    # Προσωπικά και επαγγελματικά στοιχεία.
    date_of_birth: date | None = None
    identity_card_number: str | None = None
    tax_id: str | None = None
    phone_number: str | None = None

    license_number: str | None = None
    license_category: str | None = None
    license_expiry_date: date | None = None
    hire_date: date | None = None

    fleet_id: str | None = None
    department_id: str | None = None
    status: str | None = None