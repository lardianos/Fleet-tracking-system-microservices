import type { DriverProfile as DriverProfileData } from "../types/DriverProfile";

interface DriverProfileProps {
  profile: DriverProfileData;
}

function DriverProfile({ profile }: DriverProfileProps) {
  return (
    <div>
      <h3>My Profile</h3>

      <p>
        Name: {profile.first_name} {profile.last_name}
      </p>

      <p>Email: {profile.email ?? "-"}</p>
      <p>Phone: {profile.phone_number ?? "-"}</p>
      <p>Driver ID: {profile.driver_id}</p>
      <p>License: {profile.license_number ?? "-"}</p>
      <p>License Category: {profile.license_category ?? "-"}</p>
      <p>License Expiry: {profile.license_expiry_date ?? "-"}</p>
      <p>Status: {profile.status}</p>
    </div>
  );
}

export default DriverProfile;