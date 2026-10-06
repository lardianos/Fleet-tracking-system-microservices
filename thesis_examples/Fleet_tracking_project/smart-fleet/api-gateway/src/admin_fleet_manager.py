from datetime import date

from pydantic import BaseModel, EmailStr


class AdminFleetManagerCreate(BaseModel):
    """
    Δεδομένα που δίνει ο Admin για τη δημιουργία Fleet Manager.

    Το username χρησιμοποιείται μόνο για τη δημιουργία
    του identity στο Keycloak και δεν αποθηκεύεται στο Fleet API.

    Το keycloak_user_id δεν ζητείται από τον Admin.
    Δημιουργείται από το Keycloak και προστίθεται από το API Gateway
    πριν δημιουργηθεί το Fleet Manager Profile.
    """

    username: str

    manager_id: str

    first_name: str
    last_name: str
    date_of_birth: date | None = None

    identity_card_number: str | None = None
    tax_id: str | None = None

    phone_number: str | None = None
    email: EmailStr
    fleet_id: str
    department_id: str | None = None

    hire_date: date | None = None

class AdminFleetManagerUpdate(BaseModel):
    """
    Δεδομένα που μπορεί να αλλάξει ο Admin
    σε έναν υπάρχοντα Fleet Manager.

    Το manager_id και το keycloak_user_id δεν αλλάζουν μέσω PATCH,
    επειδή αποτελούν σταθερά identifiers.

    Το status επίσης δεν αλλάζει μέσω PATCH.
    Για αλλαγή lifecycle χρησιμοποιούνται αποκλειστικά
    τα activate/deactivate endpoints.
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