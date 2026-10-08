from pydantic import BaseModel, ConfigDict, Field


class FleetBaseLocationRequest(BaseModel):
    """
    Περιγράφει τη βασική τοποθεσία ενός Fleet.

    Περιλαμβάνει στοιχεία διεύθυνσης και γεωγραφικές
    συντεταγμένες, όπως απαιτεί το Fleet API.
    """

    name: str
    address: str | None = None
    city: str | None = None
    postal_code: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class FleetCreateRequest(BaseModel):
    """
    Δεδομένα που επιτρέπεται να στείλει ο Admin
    κατά τη δημιουργία ενός Fleet.

    Το fleet_id είναι σταθερό business identifier
    και καθορίζεται μόνο κατά τη δημιουργία.
    """

    model_config = ConfigDict(extra="forbid")

    fleet_id: str
    name: str
    description: str | None = None
    base_location: FleetBaseLocationRequest


class FleetUpdateRequest(BaseModel):
    """
    Δεδομένα που επιτρέπεται να αλλάξουν
    μέσω του PATCH ενός Fleet.

    Το fleet_id δεν επιτρέπεται να αλλάξει.
    Δεν υποστηρίζουμε Fleet status lifecycle.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    base_location: FleetBaseLocationRequest | None = None