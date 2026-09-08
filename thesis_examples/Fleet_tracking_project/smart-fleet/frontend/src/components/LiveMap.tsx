import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";

import type { Position } from "../types/Position";

interface LiveMapProps {
  position: Position;
}

function LiveMap({ position }: LiveMapProps) {
  return (
    <div>
      <h3>Vehicle Location</h3>

      <MapContainer
        center={[position.latitude, position.longitude]}
        zoom={15}
        style={{
          height: "400px",
          width: "100%",
        }}
      >
        <TileLayer
          attribution="&copy; OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <Marker position={[position.latitude, position.longitude]}>
          <Popup>
            <div>
              <p>IMEI: {position.imei}</p>
              <p>Speed: {position.speed_kmh} km/h</p>
              <p>Satellites: {position.satellites}</p>
            </div>
          </Popup>
        </Marker>
      </MapContainer>
    </div>
  );
}

export default LiveMap;