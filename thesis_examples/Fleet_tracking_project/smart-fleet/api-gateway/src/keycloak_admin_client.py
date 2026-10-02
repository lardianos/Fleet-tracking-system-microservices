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

    def __init__( self, keycloak_url: str, realm: str, client_id: str, client_secret: str, ):
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

    async def create_user( self, username: str, email: str, first_name: str,
                           last_name: str, temporary_password: str | None = None, ) -> str:
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

        # Δημιουργούμε τα βασικά στοιχεία του λογαριασμού.
        # Ο νέος χρήστης θα πρέπει να ορίσει κωδικό
        # πριν χρησιμοποιήσει τον λογαριασμό του.
        user_data = {
            "username": username,
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "enabled": True,
            "emailVerified": False,
            "requiredActions": ["UPDATE_PASSWORD"],
        }

        # Διατηρούμε την υποστήριξη προσωρινού κωδικού
        # για τις υπάρχουσες δοκιμές του Keycloak Admin Client.
        if temporary_password is not None:
            user_data["credentials"] = [
                {
                    "type": "password",
                    "value": temporary_password,
                    "temporary": True,
                }
            ]

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

    async def assign_realm_role( self, keycloak_user_id: str, role_name: str, ) -> None:
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

    async def get_user_by_username( self, username: str, ) -> dict | None:
        """
        Αναζητά έναν χρήστη στο Keycloak με ακριβές username.

        Χρησιμοποιείται πριν από τη δημιουργία λογαριασμού,
        αλλά και για έλεγχο μετά από αβέβαιη έκβαση ενός request.
        """

        access_token = await self.get_access_token()

        # Ζητάμε ακριβή αντιστοίχιση, ώστε να μην επιστρέφονται
        # άλλοι χρήστες με παρόμοιο username.
        # Χρησιμοποιούμε το URL που έχει ήδη οριστεί
        # στον constructor του KeycloakAdminClient.
        url = (
            f"{self.keycloak_url}"
            f"/admin/realms/{self.realm}/users"
        )


        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url,
                headers={ "Authorization": f"Bearer {access_token}", },
                params={ "username": username, "exact": "true", },
            )

        response.raise_for_status()

        for user in response.json():
            if user.get("username") == username:
                return user

        return None

    async def get_user_by_id(self, keycloak_user_id: str, ) -> dict | None:
        """
        Διαβάζει τον χρήστη με το σταθερό Keycloak ID.
        Χρησιμοποιείται πριν από οποιαδήποτε ενημέρωση.
        """
        access_token = await self.get_access_token()

        url = (
            f"{self.keycloak_url}/admin/realms/"
            f"{self.realm}/users/{keycloak_user_id}"
        )

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                },
            )

        if response.status_code == 404:
            return None

        response.raise_for_status()
        return response.json()

    async def update_user( self, keycloak_user_id: str, identity_data: dict, ) -> None:
        """
        Ενημερώνει αποκλειστικά τα επιτρεπόμενα στοιχεία
        ταυτότητας ενός υπάρχοντος Keycloak user.

        Δεν αλλάζει username, roles, password ή enabled.
        """
        allowed_fields = {
            "firstName",
            "lastName",
            "email",
        }

        if not identity_data or (
            set(identity_data) - allowed_fields
        ):
            raise ValueError("Invalid Keycloak identity fields")

        access_token = await self.get_access_token()

        url = (
            f"{self.keycloak_url}/admin/realms/"
            f"{self.realm}/users/{keycloak_user_id}"
        )

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.put(
                url,
                json=identity_data,
                headers={
                    "Authorization": f"Bearer {access_token}",
                },
            )

        response.raise_for_status()

    async def set_user_enabled( self, keycloak_user_id: str, enabled: bool, ) -> None:
        """
        Ενεργοποιεί ή απενεργοποιεί έναν υπάρχοντα
        λογαριασμό στο Keycloak.

        Δεν αλλάζει τα προσωπικά στοιχεία, τους ρόλους
        ή τον κωδικό πρόσβασης του χρήστη.
        """

        access_token = await self.get_access_token()

        user_url = (
            f"{self.keycloak_url}"
            f"/admin/realms/{self.realm}"
            f"/users/{keycloak_user_id}"
        )

        # Αλλάζουμε αποκλειστικά το πεδίο enabled.
        # Η υπάρχουσα update_user() παραμένει ανεπηρέαστη.
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.put(
                user_url,
                json={"enabled": enabled},
                headers={
                    "Authorization": f"Bearer {access_token}",
                },
            )

        response.raise_for_status()

        logger.info(
            "Updated Keycloak user enabled state: "
            "keycloak_user_id=%s enabled=%s",
            keycloak_user_id,
            enabled,
        )

    async def logout_user( self, keycloak_user_id: str, ) -> None:
        """
        Ζητά από το Keycloak να τερματίσει τις ενεργές
        συνεδρίες του συγκεκριμένου χρήστη.
        """

        access_token = await self.get_access_token()

        logout_url = (
            f"{self.keycloak_url}"
            f"/admin/realms/{self.realm}"
            f"/users/{keycloak_user_id}/logout"
        )

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                logout_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                },
            )

        response.raise_for_status()

        logger.info(
            "Logged out Keycloak user: keycloak_user_id=%s",
            keycloak_user_id,
        )

    async def delete_user( self, keycloak_user_id: str, ) -> None:
        """
        Διαγράφει έναν user από το Keycloak.

        Η διαγραφή είναι idempotent:
        - 204 σημαίνει ότι ο user διαγράφηκε τώρα.
        - 404 σημαίνει ότι ο user δεν υπάρχει πλέον, άρα το επιθυμητό
          τελικό state έχει ήδη επιτευχθεί.

        Αυτό είναι σημαντικό για ασφαλή retries σε administrative
        workflows όπως το Hard Delete ενός Driver.
        """

        access_token = await self.get_access_token()

        user_url = (
            f"{self.keycloak_url}"
            f"/admin/realms/{self.realm}"
            f"/users/{keycloak_user_id}"
        )

        async with httpx.AsyncClient() as client:
            response = await client.delete( user_url, headers={ "Authorization": f"Bearer {access_token}", }, timeout=10,)

        # Το 204 σημαίνει ότι ο user διαγράφηκε από αυτό το request.
        if response.status_code == 204:
            logger.info(
                "Deleted Keycloak user: keycloak_user_id=%s",
                keycloak_user_id,
            )
            return

        # Το 404 θεωρείται επίσης επιτυχία.
        # Ο στόχος του delete είναι ο user να μην υπάρχει και αυτό
        # το τελικό state έχει ήδη επιτευχθεί.
        if response.status_code == 404:
            logger.info(
                "Keycloak user already deleted: keycloak_user_id=%s",
                keycloak_user_id,
            )
            return

        # Οποιαδήποτε άλλη απάντηση σημαίνει πραγματική αποτυχία
        # ή κατάσταση που δεν μπορούμε να θεωρήσουμε επιβεβαιωμένη.
        logger.error( "Could not delete Keycloak user: keycloak_user_id=%s status_code=%s",
            keycloak_user_id,
            response.status_code,
        )

        raise RuntimeError("Could not delete Keycloak user")
