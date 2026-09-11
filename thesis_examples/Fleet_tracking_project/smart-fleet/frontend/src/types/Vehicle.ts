export interface Vehicle {
  id: string;
  plate_number: string;
  brand: string;
  model: string;
  year: number;
  device_imei: string;
  driver_id: string | null;
  fleet_id: string | null;
  status: string;
}