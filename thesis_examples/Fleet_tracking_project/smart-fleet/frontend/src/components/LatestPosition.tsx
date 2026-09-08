import type { Position } from "../types/Position";

interface LatestPositionProps {
  position: Position;
}

function LatestPosition({ position }: LatestPositionProps) {
  const timestamp = new Date(position.timestamp_ms).toLocaleString();

  return (
    <div>
      <h3>Latest Position</h3>

      <p>Latitude: {position.latitude}</p>
      <p>Longitude: {position.longitude}</p>
      <p>Speed: {position.speed_kmh} km/h</p>
      <p>Direction: {position.angle_deg}°</p>
      <p>Altitude: {position.altitude_m} m</p>
      <p>Satellites: {position.satellites}</p>
      <p>Time: {timestamp}</p>
      <p>Vehicle ID: {position.vehicle_id}</p>
      <p>IMEI: {position.imei}</p>
    </div>
  );
}

export default LatestPosition;