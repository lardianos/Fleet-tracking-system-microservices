from pydantic import BaseModel


class VehicleCreateRequest(BaseModel):
    """
    Δεδομένα που επιτρέπεται να στείλει ο client
    κατά τη δημιουργία ενός Vehicle μέσω του API Gateway.

    Το status δεν περιλαμβάνεται σκόπιμα.
    Κάθε νέο Vehicle δημιουργείται από το Fleet API ως ACTIVE.
    """

    plate_number: str
    brand: str | None = None
    model: str | None = None
    year: int | None = None
    device_imei: str
    driver_id: str | None = None
    fleet_id: str | None = None


class VehicleUpdateRequest(BaseModel):
    """
    Δεδομένα που επιτρέπεται να αλλάξουν μέσω του γενικού
    PATCH ενός Vehicle.

    Το status δεν αλλάζει μέσω PATCH.
    Για αλλαγή lifecycle χρησιμοποιούνται αποκλειστικά
    τα activate/deactivate endpoints.
    """

    plate_number: str | None = None
    brand: str | None = None
    model: str | None = None
    year: int | None = None
    device_imei: str | None = None
    driver_id: str | None = None
    fleet_id: str | None = None