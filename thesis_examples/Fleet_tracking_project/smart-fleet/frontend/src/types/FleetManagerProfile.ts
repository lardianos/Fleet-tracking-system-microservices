export interface FleetManagerProfile {
    id: string;
    manager_id: string;
    keycloak_user_id: string;
    first_name: string;
    last_name: string;
    date_of_birth: string | null;
    identity_card_number: string | null;
    tax_id: string | null;
    phone_number: string | null;
    email: string | null;
    fleet_id: string;
    department_id: string | null;
    hire_date: string | null;
    status: string;
}