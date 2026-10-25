import logging
import os
from urllib.parse import quote

logger = logging.getLogger(__name__)


class KeycloakNotificationClient:
    def __init__(self, http_client):
        self.http_client = http_client
        self.base_url = os.getenv("KEYCLOAK_URL", "http://keycloak:8080").rstrip("/")
        self.realm = os.getenv("KEYCLOAK_REALM", "smart-fleet")
        self.client_id = os.getenv("KEYCLOAK_CLIENT_ID", "notification-service")
        self.client_secret = os.environ["KEYCLOAK_CLIENT_SECRET"]

        if not self.client_secret.strip():
            raise ValueError("KEYCLOAK_CLIENT_SECRET must not be empty.")

    def send_account_setup_email(self, event: dict):
        realm = quote(self.realm, safe="")
        user_id = quote(event["keycloak_user_id"], safe="")

        # Το Notification χρησιμοποιεί τον δικό του service account.
        token_response = self.http_client.post(
            f"{self.base_url}/realms/{realm}/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )

        token_response.raise_for_status()
        access_token = token_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        user_url = f"{self.base_url}/admin/realms/{realm}/users/{user_id}"
        user_response = self.http_client.get(user_url, headers=headers)

        # Ο χρήστης μπορεί να διαγράφηκε μέχρι να καταναλωθεί το event.
        if user_response.status_code == 404:
            logger.warning(
                "Account email skipped because user no longer exists: event_id=%s",
                event["event_id"],
            )
            return

        user_response.raise_for_status()
        user = user_response.json()

        if user.get("enabled") is not True:
            logger.warning(
                "Account email skipped because user is disabled: event_id=%s",
                event["event_id"],
            )
            return

        # Αν έχει ήδη ολοκληρώσει τη διαδικασία, δεν ζητάμε νέο ορισμό κωδικού.
        if (
            "UPDATE_PASSWORD" not in user.get("requiredActions", [])
            and user.get("emailVerified") is True
        ):
            logger.info(
                "Account setup already completed: event_id=%s",
                event["event_id"],
            )
            return

        actions = []

        if user.get("emailVerified") is not True:
            actions.append("VERIFY_EMAIL")

        actions.append("UPDATE_PASSWORD")

        # Το Keycloak δημιουργεί τον σύνδεσμο και στέλνει το email στο Mailpit.
        response = self.http_client.put(
            f"{user_url}/execute-actions-email",
            headers=headers,
            params={
                "client_id": os.getenv("KEYCLOAK_FRONTEND_CLIENT_ID", "smart-fleet-frontend"),
                "redirect_uri": os.getenv("FRONTEND_URL", "http://localhost:5173/"),
            },
            json=actions,
        )

        if response.status_code == 404:
            logger.warning(
                "Account disappeared before email request: event_id=%s",
                event["event_id"],
            )
            return

        response.raise_for_status()

        if response.status_code != 204:
            raise RuntimeError("Unexpected Keycloak account-email response.")

        logger.info(
            "Account email requested through Keycloak: event_id=%s user_id=%s",
            event["event_id"],
            event["keycloak_user_id"],
        )
