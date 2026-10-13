import { useState } from "react";
import type { Vehicle } from "../types/Vehicle";
import { useAuth } from "../auth/AuthContext";
import type { DriverProfile } from "../types/DriverProfile";

interface FleetVehiclesProps {
    vehicles: Vehicle[];
    drivers: DriverProfile[];
    onTrackVehicle: (vehicle: Vehicle) => void;
    onVehicleUpdated: (vehicle: Vehicle) => void;
}

// Εμφανίζουμε παύλα όταν ένα προαιρετικό στοιχείο δεν έχει τιμή.
function displayVehicleValue(value: string | number | null): string {
    if (value === null || value === "") return "—";
    return String(value);
}

function FleetVehicles({ vehicles, drivers, onTrackVehicle, onVehicleUpdated }: FleetVehiclesProps) {
    const { token } = useAuth();

    // Κρατάμε το όχημα και τον Driver της φόρμας ανάθεσης.
    const [assignmentVehicleId, setAssignmentVehicleId] = useState<string | null>(null);
    const [assignmentDriverId, setAssignmentDriverId] = useState("");
    const [isAssigningDriver, setIsAssigningDriver] = useState(false);
    const [assignmentError, setAssignmentError] = useState("");
    const [viewVehicleId, setViewVehicleId] = useState<string | null>(null);

    // Ανοίγουμε ή κλείνουμε την προβολή του συγκεκριμένου οχήματος.
    function toggleVehicleDetails(vehicle: Vehicle) {
        if (viewVehicleId === vehicle.id) {
            setViewVehicleId(null);
        } else {
            setViewVehicleId(vehicle.id);
        }
    }

    const selectedVehicle = vehicles.find((vehicle) => vehicle.id === viewVehicleId);
        const assignmentVehicle = vehicles.find((vehicle) => vehicle.id === assignmentVehicleId);

    // Ανοίγουμε τη φόρμα με την υπάρχουσα ανάθεση ή την κλείνουμε.
    function toggleDriverAssignment(vehicle: Vehicle) {
        if (isAssigningDriver) return;

        if (assignmentVehicleId === vehicle.id) {
            setAssignmentVehicleId(null);
            return;
        }

        let driverId = "";

        if (vehicle.driver_id !== null) {
            driverId = vehicle.driver_id;
        }

        setAssignmentVehicleId(vehicle.id);
        setAssignmentDriverId(driverId);
        setAssignmentError("");
    }

    // Αποθηκεύουμε μόνο την ανάθεση Driver, χωρίς αλλαγή των άλλων πεδίων.
    async function saveDriverAssignment(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();

        if (!token || assignmentVehicle === undefined || isAssigningDriver) return;

        if (assignmentVehicle.status !== "ACTIVE") {
            setAssignmentError("Driver assignment requires an ACTIVE vehicle.");
            return;
        }

        let driverId: string | null = null;

        if (assignmentDriverId !== "") {
            driverId = assignmentDriverId;
        }

        setIsAssigningDriver(true);
        setAssignmentError("");

        try {
            const response = await fetch(
                `http://localhost:8004/api/v1/vehicles/${encodeURIComponent(assignmentVehicle.id)}`,
                { method: "PATCH", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", },
                  body: JSON.stringify({ driver_id: driverId }), }
            );

            const result = await response.json();

            if (!response.ok) {
                let errorMessage = `Failed to assign Driver: ${response.status}`;

                if (result !== null && typeof result.detail === "string") {
                    errorMessage = result.detail;
                }

                throw new Error(errorMessage);
            }

            // Ενημερώνουμε την κοινή λίστα με την πραγματική ανάθεση του backend.
            onVehicleUpdated(result);
            setAssignmentVehicleId(null);
        } catch (error) {
            let errorMessage = "Could not assign Driver.";

            if (error instanceof Error) {
                errorMessage = error.message;
            }

            setAssignmentError(errorMessage);
        } finally {
            setIsAssigningDriver(false);
        }
    }
    return (
        <div>
            <h3>Fleet Vehicles</h3>

            {vehicles.length === 0 && (<p>No vehicles found.</p>)}

            {vehicles.length > 0 && (
                <table>
                    <thead>
                        <tr>
                            <th>Plate Number</th>
                            <th>Brand</th>
                            <th>Model</th>
                            <th>Driver</th>
                            <th>Status</th>
                             <th colSpan={3}>Actions</th>
                        </tr>
                    </thead>

                    <tbody>
                        {vehicles.map((vehicle) => (
                            <tr key={vehicle.id}>
                                <td>{vehicle.plate_number}</td>
                                <td>{displayVehicleValue(vehicle.brand)}</td>
                                <td>{displayVehicleValue(vehicle.model)}</td>
                                <td>{displayVehicleValue(vehicle.driver_id)}</td>
                                <td>{vehicle.status}</td>
                                <td>
                                    <button type="button" onClick={() => toggleVehicleDetails(vehicle)}> View </button>
                                </td>
                                <td>
                                    <button type="button" onClick={() => onTrackVehicle(vehicle)}> Track </button>
                                </td>
                                <td>
                                    <button type="button" onClick={() => toggleDriverAssignment(vehicle)} disabled={isAssigningDriver || vehicle.status !== "ACTIVE"}> Assign Driver </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}
                        {assignmentVehicle !== undefined && (
                <form onSubmit={saveDriverAssignment}>
                    <h3>Assign Driver: {assignmentVehicle.plate_number}</h3>

                    <div>
                        <label htmlFor="manager-assignment-driver">Driver</label>
                        <select id="manager-assignment-driver" value={assignmentDriverId} disabled={isAssigningDriver}
                                onChange={(event) => setAssignmentDriverId(event.target.value)}>
                            <option value="">Unassigned</option>

                            {/* Προσφέρουμε μόνο ενεργούς Drivers του ίδιου Fleet. */}
                            {drivers.map((driver) => {
                                if (driver.status !== "ACTIVE") return null;
                                if (driver.fleet_id === null || driver.fleet_id !== assignmentVehicle.fleet_id) return null;

                                return (
                                    <option key={driver.driver_id} value={driver.driver_id}>
                                        {driver.first_name} {driver.last_name} ({driver.driver_id})
                                    </option>
                                );
                            })}
                        </select>
                    </div>

                    {assignmentError !== "" && (<p role="alert">{assignmentError}</p>)}

                    <button type="submit" disabled={isAssigningDriver}> Save Assignment </button>
                    <button type="button" onClick={() => setAssignmentVehicleId(null)} disabled={isAssigningDriver}> Cancel </button>
                </form>
            )}

            {/* Χρησιμοποιούμε τα ήδη φορτωμένα δεδομένα του Fleet. */}
            {selectedVehicle !== undefined && (
                <div className="dashboard-details">
                    <h3>Vehicle Details: {selectedVehicle.plate_number}</h3>

                    <p>Plate Number: {selectedVehicle.plate_number}</p>
                    <p>Brand: {displayVehicleValue(selectedVehicle.brand)}</p>
                    <p>Model: {displayVehicleValue(selectedVehicle.model)}</p>
                    <p>Year: {displayVehicleValue(selectedVehicle.year)}</p>
                    <p>Device IMEI: {selectedVehicle.device_imei}</p>
                    <p>Driver ID: {displayVehicleValue(selectedVehicle.driver_id)}</p>
                    <p>Fleet ID: {displayVehicleValue(selectedVehicle.fleet_id)}</p>
                    <p>Status: {selectedVehicle.status}</p>

                    <button type="button" onClick={() => setViewVehicleId(null)}> Close </button>
                </div>
            )}
        </div>
    );
}

export default FleetVehicles;