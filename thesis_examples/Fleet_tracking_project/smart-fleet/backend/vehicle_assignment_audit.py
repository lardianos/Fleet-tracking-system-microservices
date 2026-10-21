# Πρόσθεσε ολόκληρο το endpoint στο api-gateway/src/main.py.
# Χρησιμοποιεί τα imports και τις βοηθητικές συναρτήσεις του ιστορικού που υπάρχουν ήδη.

@app.get("/api/v1/vehicles/{vehicle_id}/assignment-audit")
async def get_vehicle_assignment_audit(
    vehicle_id: str,
    token_payload: dict = Depends(validate_access_token),
):
    # Ο Driver δεν έχει πρόσβαση στο ιστορικό αναθέσεων.
    role_checker(token_payload, VEHICLE_MANAGEMENT_ROLES)
    user_roles = token_payload.get("realm_access", {}).get("roles", [])
    encoded_vehicle_id = quote(vehicle_id, safe="")

    async with httpx.AsyncClient(timeout=10.0) as client:
        if "admin" not in user_roles:
            manager_fleet_id = await get_authenticated_fleet_manager_fleet_id(token_payload)

            vehicle = await request_position_history_json(
                client,
                f"{FLEET_API_URL}/vehicles/{encoded_vehicle_id}",
                "Fleet API",
            )

            if vehicle.get("fleet_id") != manager_fleet_id:
                raise HTTPException(
                    status_code=403,
                    detail="Fleet Manager can access history only for vehicles in their own fleet.",
                )

        audit_logs = await request_position_history_json(
            client,
            f"{FLEET_API_URL}/audit-logs/VEHICLE/{encoded_vehicle_id}",
            "Fleet API",
        )

        assignment_logs = []

        for audit_log in audit_logs:
            changes = audit_log.get("changes", {})

            # Επιστρέφουμε μόνο όσα χρειάζονται για τον χρονικό εντοπισμό του οδηγού.
            if "driver_id" in changes:
                assignment_logs.append({
                    "id": audit_log["id"],
                    "timestamp": audit_log["timestamp"],
                    "changes": {"driver_id": changes["driver_id"]},
                })

        return assignment_logs
