export interface DriverProfile {
  id: string;
  driver_id: string;
  keycloak_user_id: string;
  first_name: string;
  last_name: string;
  date_of_birth: string | null;
  identity_card_number: string | null;
  tax_id: string | null;
  phone_number: string | null;
  email: string | null;
  license_number: string | null;
  license_category: string | null;
  license_expiry_date: string | null;
  hire_date: string | null;
  fleet_id: string | null;
  department_id: string | null;
  status: string;
}