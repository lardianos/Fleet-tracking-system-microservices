import type { DriverProfile } from "../types/DriverProfile";

interface FleetDriversProps {
  drivers: DriverProfile[];
}

function FleetDrivers({ drivers }: FleetDriversProps) {
  return (
    <div>
      <h3>Fleet Drivers</h3>

      {drivers.length === 0 ? (
        <p>No drivers found.</p>
      ) : (
        drivers.map((driver) => (
          <div key={driver.id}>
            <p>
              Name: {driver.first_name} {driver.last_name}
            </p>

            <p>Driver ID: {driver.driver_id}</p>
            <p>Email: {driver.email ?? "-"}</p>
            <p>Phone: {driver.phone_number ?? "-"}</p>
            <p>License: {driver.license_number ?? "-"}</p>
            <p>Status: {driver.status}</p>

            <hr />
          </div>
        ))
      )}
    </div>
  );
}

export default FleetDrivers;