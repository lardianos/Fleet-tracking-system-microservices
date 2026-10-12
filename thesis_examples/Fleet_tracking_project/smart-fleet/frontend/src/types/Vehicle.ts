export interface Vehicle {
  id: string;
  plate_number: string;
  brand: string | null;
  model: string | null;
  year: number | null;
  device_imei: string;
  driver_id: string | null;
  fleet_id: string | null;
  status: string;
}