import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useAuth } from "../auth/AuthContext";
import type { DriverAssignmentPeriodsResponse, HistoricalPosition, PositionHistorySegment, VehicleAssignmentAudit } from "../types/PositionHistory";
import { buildVehicleHistorySegments, fetchPositionHistoryJson, loadAllVehiclePositions } from "../services/positionHistory";
import PositionHistoryMap from "./PositionHistoryMap";
import { authenticatedFetch } from "../auth/session";

interface PositionHistoryProps {
    vehicles: { id: string; plate_number: string }[];
    drivers: { driver_id: string; first_name: string; last_name: string }[];
}

function getLocalDateTime(date: Date): string {
    // Τα datetime-local πεδία χρειάζονται τοπική ώρα, χωρίς μετατροπή σε UTC εδώ.
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    const hour = String(date.getHours()).padStart(2, "0");
    const minute = String(date.getMinutes()).padStart(2, "0");
    return `${year}-${month}-${day}T${hour}:${minute}`;
}

function PositionHistory({ vehicles, drivers }: PositionHistoryProps) {
    const { token, hasRole } = useAuth();
    const inputId = useId();
    const requestController = useRef<AbortController | null>(null);
    const [searchType, setSearchType] = useState("vehicle");
    const [selectedId, setSelectedId] = useState("");
    const [startTime, setStartTime] = useState(() => getLocalDateTime(new Date(Date.now() - 8 * 60 * 60 * 1000)));
    const [endTime, setEndTime] = useState(() => getLocalDateTime(new Date()));
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState("");
    const [progress, setProgress] = useState("");
    const [segments, setSegments] = useState<PositionHistorySegment[]>([]);
    const [hasSearched, setHasSearched] = useState(false);
    const [selectedPositionIndex, setSelectedPositionIndex] = useState(0);
    const [searchDescription, setSearchDescription] = useState("");
    const [historyVehicleId, setHistoryVehicleId] = useState("");

    useEffect(() => {
        return () => {
            // Όταν κλείνει η ενότητα, ακυρώνουμε και την ανάκτηση επόμενων σελίδων.
            if (requestController.current !== null) requestController.current.abort();
        };
    }, []);

        // Βρίσκουμε τα διαφορετικά οχήματα που περιλαμβάνονται στο αποτέλεσμα.
    const historyVehicles = useMemo(() => {
        const result: { id: string; plateNumber: string }[] = [];

        for (const segment of segments) {
            if (!result.some((vehicle) => vehicle.id === segment.vehicleId)) {
                result.push({ id: segment.vehicleId, plateNumber: segment.plateNumber });
            }
        }

        return result;
    }, [segments]);

    // Ο χάρτης και ο slider χρησιμοποιούν μόνο το επιλεγμένο όχημα.
    const visibleSegments = useMemo(() => {
        return segments.filter((segment) => segment.vehicleId === historyVehicleId);
    }, [segments, historyVehicleId]);

    function selectHistoryVehicle(vehicleId: string) {
        setHistoryVehicleId(vehicleId);
        setSelectedPositionIndex(0);
    }

    const orderedPositions = useMemo(() => {
        const result: { position: HistoricalPosition; segment: PositionHistorySegment }[] = [];

        for (const segment of visibleSegments) {
            for (const position of segment.positions) result.push({ position, segment });
        }

        result.sort((first, second) => {
            const difference = first.position.timestamp_ms - second.position.timestamp_ms;
            if (difference !== 0) return difference;
            return first.position.vehicle_id.localeCompare(second.position.vehicle_id);
        });

        return result;
    }, [visibleSegments]);

    let selectedEntry = null;
    if (selectedPositionIndex < orderedPositions.length) selectedEntry = orderedPositions[selectedPositionIndex];

    let selectedPosition: HistoricalPosition | null = null;
    if (selectedEntry !== null) selectedPosition = selectedEntry.position;

    let selectedSpeed = "—";
    if (selectedPosition !== null && selectedPosition.speed_kmh !== null) {
        selectedSpeed = String(selectedPosition.speed_kmh);
    }

    function getDriverLabel(driverId: string | null, assignmentKnown: boolean): string {
        if (!assignmentKnown) return "Unknown (no assignment audit)";
        if (driverId === null) return "Unassigned";

        const driver = drivers.find((item) => item.driver_id === driverId);
        if (driver === undefined) return driverId;
        return `${driver.first_name} ${driver.last_name} (${driverId})`;
    }

    function clearHistoryResults() {
        setSegments([]);
        setError("");
        setProgress("");
        setHasSearched(false);
        setSelectedPositionIndex(0);
        setSearchDescription("");
        setHistoryVehicleId("");
    }

    function cancelHistorySearch() {
        if (requestController.current !== null) requestController.current.abort();
        requestController.current = null;
        setIsLoading(false);
        clearHistoryResults();
    }

    function selectLastEightHours() {
        clearHistoryResults();
        const now = new Date();
        setStartTime(getLocalDateTime(new Date(now.getTime() - 8 * 60 * 60 * 1000)));
        setEndTime(getLocalDateTime(now));
    }

    async function loadPositionHistory(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!token || isLoading || (!hasRole("admin") && !hasRole("fleet_manager"))) return;

        clearHistoryResults();

        if (selectedId === "") {
            setError("Select a vehicle or driver.");
            return;
        }

        const start = new Date(startTime);
        const end = new Date(endTime);

        if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime()) || start >= end) {
            setError("Select a valid time range. Start must be earlier than end.");
            return;
        }

        const controller = new AbortController();
        requestController.current = controller;
        setIsLoading(true);
        setProgress("Loading history...");

        try {
            // Μετατρέπουμε σε UTC μόνο κατά την αποστολή στο API.
            const startUtc = start.toISOString();
            const endUtc = end.toISOString();
            const params = new URLSearchParams({ start_time: startUtc, end_time: endUtc });
            let loadedSegments: PositionHistorySegment[] = [];
            let description = "";

            if (searchType === "vehicle") {
                const vehicle = vehicles.find((item) => item.id === selectedId);
                if (vehicle === undefined) throw new Error("The selected vehicle is no longer available.");

                const audit = await fetchPositionHistoryJson<VehicleAssignmentAudit[]>(
                    `/vehicles/${encodeURIComponent(selectedId)}/assignment-audit`, token, controller.signal
                );

                const positions = await loadAllVehiclePositions(selectedId, startUtc, endUtc, token, controller.signal, (count) => {
                    if (!controller.signal.aborted) setProgress(`Loaded ${count} positions...`);
                });

                loadedSegments = buildVehicleHistorySegments(selectedId, vehicle.plate_number, startUtc, endUtc, positions, audit);
                description = `Vehicle: ${vehicle.plate_number}`;
            } else {
                const driver = drivers.find((item) => item.driver_id === selectedId);
                if (driver === undefined) throw new Error("The selected driver is no longer available.");

                const result = await fetchPositionHistoryJson<DriverAssignmentPeriodsResponse>(
                    `/drivers/${encodeURIComponent(selectedId)}/vehicle-assignment-periods?${params.toString()}`, token, controller.signal
                );

                let completedPositions = 0;

                // Κάθε ανάθεση ανακτάται χωριστά, με όλες τις σελίδες της.
                // Δεν ζητάμε θέσεις εκτός του διαστήματος που είχε ανατεθεί στον Driver.
                for (const period of result.assignment_periods) {
                    const positions = await loadAllVehiclePositions(
                        period.vehicle_id, period.start_time, period.end_time, token, controller.signal, (count) => {
                            if (!controller.signal.aborted) setProgress(`Loaded ${completedPositions + count} positions...`);
                        }
                    );

                    // Προτιμάμε την τρέχουσα πινακίδα από τη λίστα οχημάτων.
                    // Αν το όχημα δεν υπάρχει πλέον στη λίστα, χρησιμοποιούμε την καταγεγραμμένη.
                    let plateNumber = period.vehicle_id;
                    const vehicle = vehicles.find((item) => item.id === period.vehicle_id);

                    if (vehicle !== undefined) {
                        plateNumber = vehicle.plate_number;
                    } else if (period.plate_number !== null && period.plate_number !== "") {
                        plateNumber = period.plate_number;
                    }

                    loadedSegments.push({
                        vehicleId: period.vehicle_id, plateNumber, driverId: selectedId, assignmentKnown: true,
                        startTime: period.start_time, endTime: period.end_time, positions,
                    });

                    completedPositions += positions.length;
                }

                description = `Driver: ${driver.first_name} ${driver.last_name} (${selectedId})`;
            }

            if (controller.signal.aborted || requestController.current !== controller) return;

            // Εμφανίζουμε αποτέλεσμα μόνο όταν ολοκληρωθούν όλα τα αιτήματα.
            // Αν αποτύχει μία σελίδα, δεν παρουσιάζουμε ελλιπές ιστορικό ως ολοκληρωμένο.
            setSegments(loadedSegments);

                        // Επιλέγουμε αρχικά όχημα με καταγεγραμμένες θέσεις.
            let initialVehicleId = "";

            if (loadedSegments.length > 0) {
                initialVehicleId = loadedSegments[0].vehicleId;
            }

            const segmentWithPositions = loadedSegments.find((segment) => segment.positions.length > 0);

            if (segmentWithPositions !== undefined) {
                initialVehicleId = segmentWithPositions.vehicleId;
            }

            setHistoryVehicleId(initialVehicleId);
            setSelectedPositionIndex(0);

            setSearchDescription(`${description} | ${start.toLocaleString()} – ${end.toLocaleString()}`);
            setHasSearched(true);
            setProgress("");
        } catch (requestError) {
            if (controller.signal.aborted || requestController.current !== controller) return;

            let message = "Could not load position history.";
            if (requestError instanceof Error) message = requestError.message;
            setError(message);
            setProgress("");
        } finally {
            if (requestController.current === controller) {
                requestController.current = null;
                setIsLoading(false);
            }
        }
    }

    if (!hasRole("admin") && !hasRole("fleet_manager")) return null;

    let searchButtonText = "Show History";
    if (isLoading) searchButtonText = "Loading...";

    return (
        <div className="position-history">
            <h3>Position History</h3>
            <p>Times use your browser timezone. Driver names describe recorded assignments.</p>

            <form onSubmit={loadPositionHistory}>
                <div>
                    <label htmlFor={`${inputId}-type`}>Search by</label>
                    <select id={`${inputId}-type`} value={searchType} disabled={isLoading}
                            onChange={(event) => { setSearchType(event.target.value); setSelectedId(""); clearHistoryResults(); }}>
                        <option value="vehicle">Vehicle</option>
                        <option value="driver">Driver</option>
                    </select>
                </div>
                <div>
                    <label htmlFor={`${inputId}-selection`}>Vehicle / Driver</label>
                    <select id={`${inputId}-selection`} value={selectedId} required disabled={isLoading}
                            onChange={(event) => { setSelectedId(event.target.value); clearHistoryResults(); }}>
                        <option value="">Select an item</option>
                        {searchType === "vehicle" && vehicles.map((vehicle) => (
                            <option key={vehicle.id} value={vehicle.id}>{vehicle.plate_number}</option>
                        ))}
                        {searchType === "driver" && drivers.map((driver) => (
                            <option key={driver.driver_id} value={driver.driver_id}>{driver.first_name} {driver.last_name} ({driver.driver_id})</option>
                        ))}
                    </select>
                </div>
                <div>
                    <label htmlFor={`${inputId}-start`}>From</label>
                    <input id={`${inputId}-start`} type="datetime-local" value={startTime} required disabled={isLoading}
                           onChange={(event) => { setStartTime(event.target.value); clearHistoryResults(); }}/>
                </div>
                <div>
                    <label htmlFor={`${inputId}-end`}>To</label>
                    <input id={`${inputId}-end`} type="datetime-local" value={endTime} required disabled={isLoading}
                           onChange={(event) => { setEndTime(event.target.value); clearHistoryResults(); }}/>
                </div>
                <button type="button" onClick={selectLastEightHours} disabled={isLoading}> Last 8 Hours </button>
                <button type="submit" disabled={isLoading || selectedId === "" || !token}> {searchButtonText} </button>
                {isLoading && (<button type="button" onClick={cancelHistorySearch}> Cancel </button>)}
            </form>

            {error !== "" && (<p role="alert">{error}</p>)}
            {isLoading && (<p role="status">{progress}</p>)}

            {hasSearched && (
                <div>
                    <p>{searchDescription}</p>
                    {historyVehicles.length > 1 && (
                        <div>
                            <label htmlFor={`${inputId}-history-vehicle`}>Vehicle to display</label>
                            <select id={`${inputId}-history-vehicle`} value={historyVehicleId} onChange={(event) => selectHistoryVehicle(event.target.value)}>
                                {historyVehicles.map((vehicle) => (
                                    <option key={vehicle.id} value={vehicle.id}>{vehicle.plateNumber}</option>
                                ))}
                            </select>
                        </div>
                    )}
                    <p>Recorded positions for selected vehicle: {orderedPositions.length}</p>
                    {segments.length === 0 && (<p>No assignments found for this driver in the selected time range.</p>)}
                    {orderedPositions.length === 0 && segments.length > 0 && (<p>No recorded positions for the selected vehicle in this time range.</p>)}

                    {segments.length > 0 && (
                        <div className="position-history-table">
                            <table>
                                <thead><tr><th>Vehicle</th><th>Assigned Driver</th><th>From</th><th>To</th><th>Positions</th></tr></thead>
                                <tbody>
                                    {segments.map((segment, index) => (
                                        <tr key={`${segment.vehicleId}-${segment.startTime}-${index}`}>
                                            <td>{segment.plateNumber}</td>
                                            <td>{getDriverLabel(segment.driverId, segment.assignmentKnown)}</td>
                                            <td>{new Date(segment.startTime).toLocaleString()}</td>
                                            <td>{new Date(segment.endTime).toLocaleString()}</td>
                                            <td>{segment.positions.length}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}

                    {selectedEntry !== null && (
                        <div className="position-history-selected">
                            <label htmlFor={`${inputId}-position`}>Recorded position {selectedPositionIndex + 1} / {orderedPositions.length}</label>
                            <input id={`${inputId}-position`} type="range" min="0" max={orderedPositions.length - 1}
                                   value={selectedPositionIndex} onChange={(event) => setSelectedPositionIndex(Number(event.target.value))}/>
                            <p>Vehicle: {selectedEntry.segment.plateNumber} | Assigned driver: {getDriverLabel(selectedEntry.segment.driverId, selectedEntry.segment.assignmentKnown)}</p>
                            <p>Time: {new Date(selectedEntry.position.timestamp_ms).toLocaleString()}</p>
                            <p>Speed: {selectedSpeed} km/h | IMEI: {selectedEntry.position.imei}</p>
                            <p>Coordinates: {selectedEntry.position.latitude}, {selectedEntry.position.longitude}</p>
                        </div>
                    )}

                    <PositionHistoryMap segments={visibleSegments} selectedPosition={selectedPosition} getDriverLabel={getDriverLabel}/>
                    {orderedPositions.length > 0 && (<p>Lines connect recorded GPS points; they are not matched to roads.</p>)}
                </div>
            )}
        </div>
    );
}

export default PositionHistory;
