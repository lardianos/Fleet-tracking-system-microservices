import type { Vehicle } from "../types/Vehicle.ts";

interface MyVehicleProps {
  vehicle: Vehicle;
}

function MyVehicle({ vehicle }: MyVehicleProps) {
  return (
    <div>
      <h3>My Vehicle</h3>

      <p>Plate: {vehicle.plate_number}</p>
      <p>Brand: {vehicle.brand}</p>
      <p>Model: {vehicle.model}</p>
      <p>Year: {vehicle.year}</p>
      <p>Status: {vehicle.status}</p>
      <h3>My Device</h3>
      <p>Device IMEI: {vehicle.device_imei}</p>

    </div>
  );
}

export default MyVehicle;