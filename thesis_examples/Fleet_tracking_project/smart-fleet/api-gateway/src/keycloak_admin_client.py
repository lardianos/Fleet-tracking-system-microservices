"""
Client για επικοινωνία του API Gateway με το Keycloak Admin API.

Ο συγκεκριμένος client χρησιμοποιείται μόνο για administrative
identity operations που χρειάζεται το Smart Fleet σύστημα.

Δεν περιέχει business λογική για Drivers ή Fleet Managers.
Η ευθύνη του περιορίζεται αποκλειστικά στη διαχείριση identities
και roles μέσα στο Keycloak.
"""

import logging

import httpx


logger = logging.getLogger(__name__)


class KeycloakAdminClient:
    """
    Client για machine-to-machine επικοινωνία με το Keycloak Admin API.

    Το API Gateway αυθεντικοποιείται μέσω confidential client και
    service account χρησιμοποιώντας το Client Credentials Flow.

    Ο client παρέχει τις βασικές λειτουργίες που θα χρειαστεί αργότερα
    το Admin orchestration:
    - δημιουργία Keycloak user,
    - ανάθεση realm role,
    - διαγραφή Keycloak user.
    """

    def __init__(
        self,
        keycloak_url: str,
        realm: str,
        client_id: str,
        client_secret: str,
    ):
        self.keycloak_url = keycloak_url.rstrip("/")
        self.realm = realm
        self.client_id = client_id
        self.client_secret = client_secret

    async def get_access_token(self) -> str:
        """
        Ζητά service-account access token από το Keycloak.

        Χρησιμοποιούμε Client Credentials Flow επειδή εδώ δεν
        αυθεντικοποιείται κάποιος κανονικός χρήστης. Το API Gateway
        αυθεντικοποιείται ως backend service.

        Το token χρησιμοποιείται μόνο για κλήσεις προς το
        Keycloak Admin API και δεν επιστρέφεται ποτέ στο frontend.
        """

        token_url = (
            f"{self.keycloak_url}"
            f"/realms/{self.realm}"
            "/protocol/openid-connect/token"
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                    timeout=10,
                )

        except httpx.RequestError as error:
            logger.error(
                "Could not connect to Keycloak token endpoint: error=%s",
                error,
            )
            raise

        if response.status_code != 200:
            logger.error(
                "Keycloak service-account authentication failed: "
                "status_code=%s",
                response.status_code,
            )
            raise RuntimeError(
                "Could not authenticate API Gateway with Keycloak"
            )

        token_data = response.json()
        access_token = token_data.get("access_token")

        if not access_token:
            raise RuntimeError(
                "Keycloak response does not contain access_token"
            )

        return access_token

    async def create_user(
        self,
        username: str,
        email: str,
        first_name: str,
        last_name: str,
        temporary_password: str,
    ) -> str:
        """
        Δημιουργεί νέο user στο Keycloak και επιστρέφει το σταθερό
        Keycloak user id.

        Το user id είναι αυτό που αργότερα αποθηκεύεται ως
        keycloak_user_id στο Driver ή Fleet Manager Profile.

        Ο προσωρινός κωδικός δημιουργείται ως temporary credential,
        ώστε ο χρήστης να υποχρεωθεί να τον αλλάξει κατά την πρώτη
        κανονική είσοδό του.
        """

        access_token = await self.get_access_token()

        users_url = (
            f"{self.keycloak_url}"
            f"/admin/realms/{self.realm}/users"
        )

        user_data = {
            "username": username,
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "enabled": True,
            "credentials": [
                {
                    "type": "password",
                    "value": temporary_password,
                    "temporary": True,
                }
            ],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                users_url,
                json=user_data,
                headers={
                    "Authorization": f"Bearer {access_token}",
                },
                timeout=10,
            )

        if response.status_code != 201:
            logger.error(
                "Could not create Keycloak user: "
                "username=%s status_code=%s",
                username,
                response.status_code,
            )
            raise RuntimeError("Could not create Keycloak user")

        # Το Keycloak επιστρέφει το URI του νέου user στο Location header.
        # Το τελευταίο τμήμα αυτού του URI είναι το σταθερό user id.
        location = response.headers.get("Location")

        if not location:
            raise RuntimeError(
                "Keycloak did not return Location for created user"
            )

        keycloak_user_id = location.rstrip("/").split("/")[-1]

        logger.info(
            "Created Keycloak user: username=%s keycloak_user_id=%s",
            username,
            keycloak_user_id,
        )

        return keycloak_user_id

    async def assign_realm_role(
        self,
        keycloak_user_id: str,
        role_name: str,
    ) -> None:
        """
        Αναθέτει ένα realm role σε υπάρχοντα Keycloak user.

        Για το Smart Fleet θα χρησιμοποιηθεί αρχικά για:
        - driver
        - fleet_manager

        Δεν δημιουργούμε roles δυναμικά. Τα roles πρέπει να υπάρχουν
        ήδη στο realm και εδώ γίνεται μόνο η ανάθεσή τους.
        """

        access_token = await self.get_access_token()

        role_url = (
            f"{self.keycloak_url}"
            f"/admin/realms/{self.realm}"
            f"/roles/{role_name}"
        )

        async with httpx.AsyncClient() as client:
            role_response = await client.get(
                role_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                },
                timeout=10,
            )

        if role_response.status_code != 200:
            logger.error(
                "Could not find Keycloak realm role: "
                "role=%s status_code=%s",
                role_name,
                role_response.status_code,
            )
            raise RuntimeError(
                f"Keycloak realm role '{role_name}' was not found"
            )

        role_data = role_response.json()

        role_mapping_url = (
            f"{self.keycloak_url}"
            f"/admin/realms/{self.realm}"
            f"/users/{keycloak_user_id}"
            "/role-mappings/realm"
        )

        async with httpx.AsyncClient() as client:
            role_mapping_response = await client.post(
                role_mapping_url,
                json=[role_data],
                headers={
                    "Authorization": f"Bearer {access_token}",
                },
                timeout=10,
            )

        if role_mapping_response.status_code != 204:
            logger.error(
                "Could not assign Keycloak realm role: "
                "keycloak_user_id=%s role=%s status_code=%s",
                keycloak_user_id,
                role_name,
                role_mapping_response.status_code,
            )
            raise RuntimeError(
                f"Could not assign Keycloak role '{role_name}'"
            )

        logger.info(
            "Assigned Keycloak realm role: "
            "keycloak_user_id=%s role=%s",
            keycloak_user_id,
            role_name,
        )

    async def delete_user(
        self,
        keycloak_user_id: str,
    ) -> None:
        """
        Διαγράφει έναν user από το Keycloak.

        Η μέθοδος αυτή θα χρησιμοποιηθεί τόσο στο κανονικό Admin
        delete workflow όσο και ως compensating action όταν έχει
        δημιουργηθεί Keycloak identity αλλά αποτύχει στη συνέχεια
        η δημιουργία του αντίστοιχου business profile.
        """

        access_token = await self.get_access_token()

        user_url = (
            f"{self.keycloak_url}"
            f"/admin/realms/{self.realm}"
            f"/users/{keycloak_user_id}"
        )

        async with httpx.AsyncClient() as client:
            response = await client.delete(
                user_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                },
                timeout=10,
            )

        if response.status_code != 204:
            logger.error(
                "Could not delete Keycloak user: "
                "keycloak_user_id=%s status_code=%s",
                keycloak_user_id,
                response.status_code,
            )
            raise RuntimeError("Could not delete Keycloak user")

        logger.info(
            "Deleted Keycloak user: keycloak_user_id=%s",
            keycloak_user_id,
        )