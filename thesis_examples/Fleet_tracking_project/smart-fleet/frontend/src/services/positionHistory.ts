import type { HistoricalPosition, PositionHistoryCursor, VehiclePositionHistoryResponse, VehicleAssignmentAudit, PositionHistorySegment } from "../types/PositionHistory";

const apiUrl = "http://localhost:8004/api/v1";

export function getAuditTimestamp(value: string): number {
    // Το υπάρχον audit επιστρέφει κάποιες UTC ώρες χωρίς Z ή offset.
    let timestamp = value;
    if (!/(Z|[+-]\d{2}:\d{2})$/i.test(timestamp)) timestamp += "Z";

    const milliseconds = Date.parse(timestamp);
    if (!Number.isFinite(milliseconds)) throw new Error("Audit contains an invalid timestamp.");
    return milliseconds;
}

export function buildVehicleHistorySegments(
    vehicleId: string,
    plateNumber: string,
    startTime: string,
    endTime: string,
    positions: HistoricalPosition[],
    auditLogs: VehicleAssignmentAudit[],
): PositionHistorySegment[] {
    const start = Date.parse(startTime);
    const end = Date.parse(endTime);
    const segments: PositionHistorySegment[] = [];
    let driverId: string | null = null;
    let assignmentKnown = false;
    let segmentStart = start;

    const orderedLogs = [...auditLogs].sort((first, second) => {
        const difference = getAuditTimestamp(first.timestamp) - getAuditTimestamp(second.timestamp);
        if (difference !== 0) return difference;
        return first.id.localeCompare(second.id);
    });

    function appendSegment(segmentEnd: number) {
        if (segmentStart >= segmentEnd) return;

        segments.push({
            vehicleId, plateNumber, driverId, assignmentKnown,
            startTime: new Date(segmentStart).toISOString(),
            endTime: new Date(segmentEnd).toISOString(),
            positions: positions.filter((position) => position.timestamp_ms >= segmentStart && position.timestamp_ms < segmentEnd),
        });
    }

    for (const audit of orderedLogs) {
        const eventTime = getAuditTimestamp(audit.timestamp);
        if (eventTime >= end) break;

        if (eventTime > start) {
            appendSegment(eventTime);
            segmentStart = eventTime;
        }

        // Χρησιμοποιούμε τις δομημένες αλλαγές και όχι την περιγραφή του audit.
        // Πριν από την πρώτη γνωστή αλλαγή δεν επινοούμε ανάθεση οδηγού.
        driverId = audit.changes.driver_id.to_value;
        assignmentKnown = true;
    }

    appendSegment(end);
    return segments;
}

// Όλα τα αιτήματα περνούν από το Gateway με το υπάρχον access token.
export async function fetchPositionHistoryJson<T>(path: string, token: string, signal: AbortSignal): Promise<T> {
    const response = await fetch(apiUrl + path, {
        headers: { Authorization: `Bearer ${token}` },
        signal,
    });

    if (!response.ok) {
        let message = `History request failed: ${response.status}`;

        if (response.status === 401) message = "Your session has expired. Sign in again.";
        if (response.status === 403) message = "You do not have access to this history.";

        const errorBody = await response.json().catch(() => null);

        if (errorBody !== null && typeof errorBody.detail === "string") {
            message = errorBody.detail;
        }

        throw new Error(message);
    }

    return response.json();
}

export async function loadAllVehiclePositions(
    vehicleId: string,
    startTime: string,
    endTime: string,
    token: string,
    signal: AbortSignal,
    onPageLoaded: (count: number) => void,
): Promise<HistoricalPosition[]> {
    const positions: HistoricalPosition[] = [];
    const usedCursors = new Set<string>();
    let cursor: PositionHistoryCursor | null = null;

    while (true) {
        // Το ίδιο διάστημα διατηρείται σε όλες τις σελίδες της αναζήτησης.
        const params = new URLSearchParams({ start_time: startTime, end_time: endTime, limit: "1000" });

        if (cursor !== null) {
            params.set("after_time", cursor.after_time);
            params.set("after_imei", cursor.after_imei);
        }

        const page: VehiclePositionHistoryResponse = await fetchPositionHistoryJson<VehiclePositionHistoryResponse>(
            `/vehicles/${encodeURIComponent(vehicleId)}/positions?${params.toString()}`, token, signal
        );

        if (!Array.isArray(page.positions) || page.vehicle_id !== vehicleId) {
            throw new Error("Invalid position history response.");
        }

        for (const position of page.positions) {
            if (!Number.isFinite(position.latitude) || !Number.isFinite(position.longitude) ||
                Math.abs(position.latitude) > 90 || Math.abs(position.longitude) > 180 ||
                !Number.isFinite(position.timestamp_ms)) {
                throw new Error("Position history contains invalid coordinates or timestamps.");
            }

            positions.push(position);
        }

        onPageLoaded(positions.length);

        if (!page.has_more) return positions;

        if (page.next_cursor === null || page.positions.length === 0) {
            throw new Error("The server did not provide the next history page.");
        }

        const cursorKey = JSON.stringify(page.next_cursor);

        // Αν το backend επαναλάβει cursor, σταματάμε αντί να ζητάμε ατέρμονα σελίδες.
        if (usedCursors.has(cursorKey)) throw new Error("The server repeated a history cursor.");

        usedCursors.add(cursorKey);
        cursor = page.next_cursor;
    }
}
