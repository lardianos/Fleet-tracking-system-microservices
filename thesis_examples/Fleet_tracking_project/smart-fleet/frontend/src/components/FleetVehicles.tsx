import type { Vehicle } from "../types/Vehicle";

interface FleetVehiclesProps {
  vehicles: Vehicle[];
}

function FleetVehicles({ vehicles }: FleetVehiclesProps) {
  return (
    <div>
      <h3>Fleet Vehicles</h3>

      {vehicles.length === 0 ? (
        <p>No vehicles found.</p>
      ) : (
        vehicles.map((vehicle) => (
          <div key={vehicle.id}>
            <p>
              Plate: {vehicle.plate_number}
            </p>

            <p>
              Vehicle: {vehicle.brand} {vehicle.model}
            </p>

            <p>Year: {vehicle.year}</p>
            <p>Status: {vehicle.status}</p>
            <p>Driver ID: {vehicle.driver_id ?? "-"}</p>
            <p>IMEI: {vehicle.device_imei}</p>

            <hr />
          </div>
        ))
      )}
    </div>
  );
}

export default FleetVehicles;