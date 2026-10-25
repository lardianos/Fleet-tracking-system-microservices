import logging
import os

from datetime import datetime, timezone
from urllib.parse import quote

logger = logging.getLogger(__name__)


def audit_time(value: str) -> datetime:
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    return timestamp


class AlertRecipientResolver:
    def __init__(self, http_client):
        self.http_client = http_client
        self.fleet_url = os.getenv("FLEET_API_URL", "http://fleet-api:8000").rstrip("/")
        self.admin_user_id = os.getenv("ADMIN_KEYCLOAK_USER_ID", "").strip()
        self.admin_email = os.getenv("ADMIN_EMAIL", "").strip()

        if not self.admin_user_id or not self.admin_email:
            raise ValueError("ADMIN_KEYCLOAK_USER_ID and ADMIN_EMAIL must be configured.")

    def read_fleet_data(self, path: str, allow_missing: bool = False):
        response = self.http_client.get(self.fleet_url + path)

        if allow_missing and response.status_code == 404:
            return None

        response.raise_for_status()
        return response.json()

    def resolve_alert_recipients(self, alert: dict) -> dict:
        vehicle_id = quote(alert["vehicle_id"], safe="")
        event_time = datetime.fromtimestamp(alert["timestamp_ms"] / 1000, tz=timezone.utc)

        vehicle = self.read_fleet_data(
            f"/vehicles/{vehicle_id}",
            allow_missing=True,
        )

        audits = self.read_fleet_data(
            f"/audit-logs/VEHICLE/{vehicle_id}"
        )

        assignment = {"driver_id": None, "fleet_id": None}
        known_fields = set()
        deleted = False
        plate_number = alert["vehicle_id"]

        ordered_audits = sorted(
            audits,
            key=lambda item: (audit_time(item["timestamp"]), item["id"]),
        )

        # Βρίσκουμε τις αναθέσεις κατά τη στιγμή του περιστατικού.
        for audit in ordered_audits:
            if audit_time(audit["timestamp"]) > event_time:
                break

            if audit["action"] == "CREATED":
                assignment = {"driver_id": None, "fleet_id": None}
                known_fields.update(assignment.keys())

            changes = audit.get("changes", {})

            for field in assignment:
                change = changes.get(field)

                if isinstance(change, dict) and "to_value" in change:
                    assignment[field] = change["to_value"]
                    known_fields.add(field)

            if "plate_number" in changes:
                plate_number = changes["plate_number"]["to_value"]

            if audit["action"] == "DELETED":
                deleted = True

        # Η σημερινή πινακίδα χρησιμοποιείται μόνο ως ετικέτα εμφάνισης.
        if vehicle is not None:
            plate_number = vehicle["plate_number"]
        # Αν δεν μπορούμε να ταυτοποιήσουμε τον Driver, δεν εμφανίζουμε αυθαίρετο όνομα.
        driver_name = "Unknown"

        if "driver_id" in known_fields and assignment["driver_id"] is None:
            driver_name = "No assigned driver"
        recipients = {}

        def add_recipient(user_id, email, channels):
            if not isinstance(user_id, str) or not user_id.strip():
                logger.warning(
                    "Recipient has no Keycloak ID: alert_id=%s",
                    alert["alert_id"],
                )
                return

            user_id = user_id.strip()

            # Συνδυάζουμε τα κανάλια αν το ίδιο πρόσωπο έχει περισσότερους ρόλους.
            if user_id not in recipients:
                recipients[user_id] = {
                    "user_id": user_id,
                    "email": email,
                    "channels": set(),
                }

            recipients[user_id]["channels"].update(channels)

        # Ο Admin προκύπτει από τις ρυθμίσεις του Notification.
        add_recipient(
            self.admin_user_id,
            self.admin_email,
            ["email", "dashboard"],
        )

        if not deleted and "fleet_id" in known_fields and assignment["fleet_id"] is not None:
            managers = self.read_fleet_data("/fleet-managers")

            # Οι ενεργοί Managers του αντίστοιχου fleet λαμβάνουν και email.
            for manager in managers:
                if manager["status"] == "ACTIVE" and manager.get("fleet_id") == assignment["fleet_id"]:
                    add_recipient(
                        manager.get("keycloak_user_id"),
                        manager.get("email"),
                        ["email", "dashboard"],
                    )

        if not deleted and "driver_id" in known_fields and assignment["driver_id"] is not None:
            drivers = self.read_fleet_data("/drivers")
            driver = next((item for item in drivers if item["driver_id"] == assignment["driver_id"]), None)

            if driver is not None:
                driver_audits = self.read_fleet_data(
                    f"/audit-logs/DRIVER/{quote(driver['driver_id'], safe='')}"
                )

                # Αποφεύγουμε να χρησιμοποιήσουμε άλλο πρόσωπο αν το ίδιο driver_id δημιουργήθηκε ξανά.
                recreated = any(
                    item["action"] == "CREATED" and audit_time(item["timestamp"]) > event_time
                    for item in driver_audits
                )

                if not recreated:
                    first_name = driver.get("first_name") or ""
                    last_name = driver.get("last_name") or ""
                    full_name = f"{first_name} {last_name}".strip()

                    if full_name:
                        driver_name = full_name

                    if driver["status"] == "ACTIVE":
                        add_recipient(driver.get("keycloak_user_id"), None, ["dashboard"])

        for field in assignment:
            if field not in known_fields:
                logger.warning(
                    "Unknown historical assignment: alert_id=%s field=%s",
                    alert["alert_id"],
                    field,
                )

        result = []

        for recipient in recipients.values():
            recipient["channels"] = sorted(recipient["channels"])
            result.append(recipient)

        logger.info(
            "Resolved alert recipients: alert_id=%s users=%s",
            alert["alert_id"],
            len(result),
        )

        return {
            "plate_number": plate_number,
            "fleet_id": assignment["fleet_id"],
            "driver_id": assignment["driver_id"],
            "driver_name": driver_name,
            "recipients": result,
        }