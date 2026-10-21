import { useEffect, useMemo } from "react";
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, useMap } from "react-leaflet";
import type { LatLngExpression } from "leaflet";
import type { HistoricalPosition, PositionHistorySegment } from "../types/PositionHistory";
import "leaflet/dist/leaflet.css";

interface PositionHistoryMapProps {
    segments: PositionHistorySegment[];
    selectedPosition: HistoricalPosition | null;
    getDriverLabel: (driverId: string | null, assignmentKnown: boolean) => string;
}

const routeColors = ["#245780", "#28794d", "#a25a20", "#75469c", "#a43b52"];

function HistoryMapBounds({ coordinates }: { coordinates: LatLngExpression[] }) {
    const map = useMap();

    useEffect(() => {
        if (coordinates.length === 0) return;

        // Προσαρμόζουμε τον χάρτη σε όλο το αποτέλεσμα, όχι μόνο στην πρώτη θέση.
        map.invalidateSize();
        map.fitBounds(coordinates, { padding: [24, 24], maxZoom: 16 });
    }, [coordinates, map]);

    return null;
}

function PositionHistoryMap({ segments, selectedPosition, getDriverLabel }: PositionHistoryMapProps) {
    const coordinates = useMemo<LatLngExpression[]>(() => {
        const result: LatLngExpression[] = [];
        for (const segment of segments) {
            for (const position of segment.positions) result.push([position.latitude, position.longitude]);
        }
        return result;
    }, [segments]);

    const routes = useMemo(() => {
        const result: { key: string; segment: PositionHistorySegment; color: string; positions: HistoricalPosition[] }[] = [];

        segments.forEach((segment, segmentIndex) => {
            let currentRoute: HistoricalPosition[] = [];
            let previousImei = "";
            let routeNumber = 0;

            for (const position of segment.positions) {
                // Δεν ενώνουμε διαφορετικά οχήματα, αναθέσεις ή αλλαγές συσκευής.
                if (currentRoute.length > 0 && position.imei !== previousImei) {
                    result.push({ key: `${segmentIndex}-${routeNumber++}`, segment,
                        color: routeColors[segmentIndex % routeColors.length], positions: currentRoute });
                    currentRoute = [];
                }

                currentRoute.push(position);
                previousImei = position.imei;
            }

            if (currentRoute.length > 0) {
                result.push({ key: `${segmentIndex}-${routeNumber}`, segment,
                    color: routeColors[segmentIndex % routeColors.length], positions: currentRoute });
            }
        });

        return result;
    }, [segments]);

    if (coordinates.length === 0) return null;

    return (
        <MapContainer center={[37.98, 23.73]} zoom={12} className="position-history-map" preferCanvas>
            <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/>
            <HistoryMapBounds coordinates={coordinates}/>

            {routes.map((route) => (
                <Polyline key={route.key} positions={route.positions.map<LatLngExpression>((position) => [position.latitude, position.longitude])}
                          pathOptions={{ color: route.color, weight: 4 }}>
                    <Popup>
                        <p>Vehicle: {route.segment.plateNumber}</p>
                        <p>Assigned driver: {getDriverLabel(route.segment.driverId, route.segment.assignmentKnown)}</p>
                        <p>Recorded positions: {route.positions.length}</p>
                    </Popup>
                </Polyline>
            ))}

            {routes.map((route) => (
                <CircleMarker key={`start-${route.key}`} center={[route.positions[0].latitude, route.positions[0].longitude]}
                              radius={4} pathOptions={{ color: route.color, fillOpacity: 1 }}>
                    <Popup>
                        <p>Vehicle: {route.segment.plateNumber}</p>
                        <p>Assigned driver: {getDriverLabel(route.segment.driverId, route.segment.assignmentKnown)}</p>
                        <p>First recorded point: {new Date(route.positions[0].timestamp_ms).toLocaleString()}</p>
                    </Popup>
                </CircleMarker>
            ))}

            {selectedPosition !== null && (
                <CircleMarker center={[selectedPosition.latitude, selectedPosition.longitude]} radius={8}
                              pathOptions={{ color: "#172f45", fillColor: "#ffffff", fillOpacity: 1, weight: 3 }}>
                    <Popup>
                        <p>Time: {new Date(selectedPosition.timestamp_ms).toLocaleString()}</p>
                        <p>IMEI: {selectedPosition.imei}</p>
                    </Popup>
                </CircleMarker>
            )}
        </MapContainer>
    );
}

export default PositionHistoryMap;
