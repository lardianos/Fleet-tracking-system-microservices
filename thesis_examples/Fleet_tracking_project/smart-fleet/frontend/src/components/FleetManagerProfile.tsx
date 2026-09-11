import type { FleetManagerProfile as FleetManagerProfileData } from "../types/FleetManagerProfile";

interface FleetManagerProfileProps {
  profile: FleetManagerProfileData;
}

function FleetManagerProfile({
  profile,
}: FleetManagerProfileProps) {
  return (
    <div>
      <h3>My Profile</h3>

      <p>
        Name: {profile.first_name} {profile.last_name}
      </p>

      <p>Email: {profile.email ?? "-"}</p>
      <p>Phone: {profile.phone_number ?? "-"}</p>
      <p>Manager ID: {profile.manager_id}</p>
      <p>Fleet ID: {profile.fleet_id}</p>
      <p>Department ID: {profile.department_id ?? "-"}</p>
      <p>Hire Date: {profile.hire_date ?? "-"}</p>
      <p>Status: {profile.status}</p>
    </div>
  );
}

export default FleetManagerProfile;