import { useEffect } from "react";
import {
  MapContainer,
  Marker,
  Popup,
  TileLayer,
  useMap,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";

import type { Position } from "../types/Position";

interface LiveMapProps {
  position: Position;
}

interface MapUpdaterProps {
  latitude: number;
  longitude: number;
}

function MapUpdater({ latitude, longitude }: MapUpdaterProps) {
  const map = useMap();

  useEffect(() => {
    // Κάθε φορά που αλλάζει η θέση του οχήματος,
    // μετακινούμε το κέντρο του χάρτη στη νέα τοποθεσία.
    map.setView([latitude, longitude]);
  }, [latitude, longitude, map]);

  return null;
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

        {/* Ενημερώνει το κέντρο του χάρτη όταν έρχεται νέα θέση. */}
        <MapUpdater
          latitude={position.latitude}
          longitude={position.longitude}
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