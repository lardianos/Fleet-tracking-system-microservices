export interface Position {
  imei: string;
  codec_id: number;
  timestamp_ms: number;
  latitude: number;
  longitude: number;
  speed_kmh: number;
  angle_deg: number;
  altitude_m: number;
  satellites: number;
  priority: number;
  event_io_id: number;
  io_elements: Record<string, unknown>;
  vehicle_id: string;
}