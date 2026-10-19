import { useState } from "react";
import type { Vehicle } from "../types/Vehicle";
import { useAuth } from "../auth/AuthContext";
import type { DriverProfile } from "../types/DriverProfile";

interface FleetVehiclesProps {
    vehicles: Vehicle[];
    drivers: DriverProfile[];
    onTrackVehicle: (vehicle: Vehicle) => void;
    onVehicleUpdated: (vehicle: Vehicle) => void;
    onVehicleCreated: (vehicle: Vehicle) => void;
}
// Κρατάμε τις τιμές της φόρμας δημιουργίας ως κείμενο.
interface VehicleCreateForm {
    plate_number: string;
    brand: string;
    model: string;
    year: string;
    device_imei: string;
    driver_id: string;
}

const emptyVehicleForm: VehicleCreateForm = {
    plate_number: "",
    brand: "",
    model: "",
    year: "",
    device_imei: "",
    driver_id: "",
};

// Εμφανίζουμε παύλα όταν ένα προαιρετικό στοιχείο δεν έχει τιμή.
function displayVehicleValue(value: string | number | null): string {
    if (value === null || value === "") return "—";
    return String(value);
}

function FleetVehicles({ vehicles, drivers, onTrackVehicle, onVehicleUpdated, onVehicleCreated }: FleetVehiclesProps) {
    const { token } = useAuth();

    // Κρατάμε το όχημα και τον Driver της φόρμας ανάθεσης.
    const [assignmentVehicleId, setAssignmentVehicleId] = useState<string | null>(null);
    const [assignmentDriverId, setAssignmentDriverId] = useState("");
    const [isAssigningDriver, setIsAssigningDriver] = useState(false);
    const [assignmentError, setAssignmentError] = useState("");
    const [viewVehicleId, setViewVehicleId] = useState<string | null>(null);

        // Εμφανίζουμε τη φόρμα δημιουργίας από το ίδιο κουμπί.
    const [showCreateVehicle, setShowCreateVehicle] = useState(false);
    const [vehicleForm, setVehicleForm] = useState<VehicleCreateForm>(emptyVehicleForm);

    // Παρακολουθούμε τη δημιουργία και το αποτέλεσμα του αιτήματος.
    const [isCreatingVehicle, setIsCreatingVehicle] = useState(false);
    const [createVehicleError, setCreateVehicleError] = useState("");
    const [createVehicleSuccess, setCreateVehicleSuccess] = useState("");

    const selectedVehicle = vehicles.find((vehicle) => vehicle.id === viewVehicleId);
    const assignmentVehicle = vehicles.find((vehicle) => vehicle.id === assignmentVehicleId);

    // Κρατάμε το όχημα και τις τιμές της φόρμας επεξεργασίας.
    const [editingVehicleId, setEditingVehicleId] = useState<string | null>(null);
    const [editVehicleForm, setEditVehicleForm] = useState<VehicleCreateForm>(emptyVehicleForm);
    const [isUpdatingVehicle, setIsUpdatingVehicle] = useState(false);
    const [editVehicleError, setEditVehicleError] = useState("");

    // Παρακολουθούμε την απενεργοποίηση και το αποτέλεσμα του αιτήματος.
    const [deactivatingVehicleId, setDeactivatingVehicleId] = useState<string | null>(null);
    const [deactivateVehicleError, setDeactivateVehicleError] = useState("");
    const [deactivateVehicleSuccess, setDeactivateVehicleSuccess] = useState("");

    // Παρακολουθούμε την ενεργοποίηση και το αποτέλεσμα του αιτήματος.
    const [activatingVehicleId, setActivatingVehicleId] = useState<string | null>(null);
    const [activateVehicleError, setActivateVehicleError] = useState("");
    const [activateVehicleSuccess, setActivateVehicleSuccess] = useState("");
    // Επιτρέπουμε μία αλλαγή οχήματος κάθε φορά.
    const isVehicleActionRunning = isCreatingVehicle || isUpdatingVehicle || isAssigningDriver || deactivatingVehicleId !== null || activatingVehicleId !== null;


    // Ανοίγουμε ή κλείνουμε την προβολή του συγκεκριμένου οχήματος.
    function toggleVehicleDetails(vehicle: Vehicle) {
        if (viewVehicleId === vehicle.id) {
            setViewVehicleId(null);
        } else {
            setViewVehicleId(vehicle.id);
        }

    }

    // Ανοίγουμε τη φόρμα με την υπάρχουσα ανάθεση ή την κλείνουμε.
    function toggleDriverAssignment(vehicle: Vehicle) {
        if (isVehicleActionRunning) return;

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

        if (!token || assignmentVehicle === undefined || isVehicleActionRunning) return;

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

        // Δημιουργούμε όχημα στο Fleet του συνδεδεμένου Manager.
    // Το backend βρίσκει και ελέγχει το Fleet από το JWT.
    async function createVehicle(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();

        if (!token || isVehicleActionRunning) return;

        setCreateVehicleError("");
        setCreateVehicleSuccess("");

        const plateNumber = vehicleForm.plate_number.trim();
        const deviceImei = vehicleForm.device_imei.trim();
        const yearText = vehicleForm.year.trim();

        if (plateNumber === "" || deviceImei === "") {
            setCreateVehicleError("Please complete Plate Number and Device IMEI.");
            return;
        }

        // Το έτος είναι προαιρετικό, αλλά πρέπει να είναι ακέραιο αν συμπληρωθεί.
        let year: number | null = null;

        if (yearText !== "") {
            year = Number(yearText);

            if (!Number.isInteger(year)) {
                setCreateVehicleError("Year must be a whole number.");
                return;
            }
        }

        const payload: {
            plate_number: string;
            device_imei: string;
            brand: string | null;
            model: string | null;
            year: number | null;
            driver_id: string | null;
        } = {
            plate_number: plateNumber,
            device_imei: deviceImei,
            brand: null,
            model: null,
            year,
            driver_id: null,
        };

        // Μετατρέπουμε τα κενά προαιρετικά πεδία σε null.
        if (vehicleForm.brand.trim() !== "") {
            payload.brand = vehicleForm.brand.trim();
        }

        if (vehicleForm.model.trim() !== "") {
            payload.model = vehicleForm.model.trim();
        }

        if (vehicleForm.driver_id !== "") {
            payload.driver_id = vehicleForm.driver_id;
        }

        setIsCreatingVehicle(true);

        try {
            const response = await fetch(
                "http://localhost:8004/api/v1/vehicles",
                { method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", },
                  body: JSON.stringify(payload), }
            );

            const result = await response.json();

            if (!response.ok) {
                let errorMessage = `Failed to create vehicle: ${response.status}`;

                if (result !== null && typeof result.detail === "string") {
                    errorMessage = result.detail;
                } else if (result !== null && Array.isArray(result.detail)) {
                    // Εμφανίζουμε το πεδίο και την αιτία κάθε validation error.
                    const validationErrors = [];

                    for (const validationError of result.detail) {
                        let field = "unknown";

                        if (Array.isArray(validationError.loc)) {
                            field = validationError.loc.join(".");
                        }

                        validationErrors.push(`${field}: ${validationError.msg}`);
                    }

                    errorMessage = validationErrors.join(" | ");
                }

                throw new Error(errorMessage);
            }

            const createdVehicle: Vehicle = result;

            // Προσθέτουμε το νέο όχημα στην κοινή λίστα του App.
            onVehicleCreated(createdVehicle);
            setVehicleForm({ ...emptyVehicleForm });
            setShowCreateVehicle(false);
            setCreateVehicleSuccess("Vehicle created successfully.");
        } catch (error) {
            let errorMessage = "Could not create vehicle.";

            if (error instanceof Error) {
                errorMessage = error.message;
            }

            setCreateVehicleError(errorMessage);
        } finally {
            setIsCreatingVehicle(false);
        }
    }

        // Ανοίγουμε το Edit με τις υπάρχουσες τιμές ή κλείνουμε την ίδια φόρμα.
    function toggleVehicleEdit(vehicle: Vehicle) {
        if (isVehicleActionRunning) return;

        if (editingVehicleId === vehicle.id) {
            setEditingVehicleId(null);
            return;
        }

        const form: VehicleCreateForm = {
            plate_number: vehicle.plate_number,
            brand: "",
            model: "",
            year: "",
            device_imei: vehicle.device_imei,
            driver_id: "",
        };

        // Μετατρέπουμε τα προαιρετικά στοιχεία σε τιμές κατάλληλες για τα inputs.
        if (vehicle.brand !== null) {
            form.brand = vehicle.brand;
        }

        if (vehicle.model !== null) {
            form.model = vehicle.model;
        }

        if (vehicle.year !== null) {
            form.year = String(vehicle.year);
        }

        if (vehicle.driver_id !== null) {
            form.driver_id = vehicle.driver_id;
        }

        setEditVehicleForm(form);
        setEditingVehicleId(vehicle.id);
        setEditVehicleError("");
    }

        // Αποθηκεύουμε τα στοιχεία του οχήματος χωρίς αλλαγή των αναθέσεών του.
    async function updateVehicle(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();

        if (!token || editingVehicleId === null || isVehicleActionRunning) return;

        setEditVehicleError("");

        const plateNumber = editVehicleForm.plate_number.trim();
        const deviceImei = editVehicleForm.device_imei.trim();
        const yearText = editVehicleForm.year.trim();

        if (plateNumber === "" || deviceImei === "") {
            setEditVehicleError("Please complete Plate Number and Device IMEI.");
            return;
        }

        let year: number | null = null;

        if (yearText !== "") {
            year = Number(yearText);

            if (!Number.isInteger(year)) {
                setEditVehicleError("Year must be a whole number.");
                return;
            }
        }

        const payload: {
            plate_number: string;
            device_imei: string;
            brand: string | null;
            model: string | null;
            year: number | null;
        } = {
            plate_number: plateNumber,
            device_imei: deviceImei,
            brand: null,
            model: null,
            year,
        };

        if (editVehicleForm.brand.trim() !== "") {
            payload.brand = editVehicleForm.brand.trim();
        }

        if (editVehicleForm.model.trim() !== "") {
            payload.model = editVehicleForm.model.trim();
        }

        setIsUpdatingVehicle(true);

        try {
            const response = await fetch(
                `http://localhost:8004/api/v1/vehicles/${encodeURIComponent(editingVehicleId)}`,
                { method: "PATCH", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", },
                  body: JSON.stringify(payload), }
            );

            const result = await response.json();

            if (!response.ok) {
                let errorMessage = `Failed to update vehicle: ${response.status}`;

                if (result !== null && typeof result.detail === "string") {
                    errorMessage = result.detail;
                } else if (result !== null && Array.isArray(result.detail)) {
                    const validationErrors = [];

                    for (const validationError of result.detail) {
                        let field = "unknown";

                        if (Array.isArray(validationError.loc)) {
                            field = validationError.loc.join(".");
                        }

                        validationErrors.push(`${field}: ${validationError.msg}`);
                    }

                    errorMessage = validationErrors.join(" | ");
                }

                throw new Error(errorMessage);
            }

            // Ενημερώνουμε την κοινή λίστα με την απάντηση του backend.
            onVehicleUpdated(result);
            setEditingVehicleId(null);
        } catch (error) {
            let errorMessage = "Could not update vehicle.";

            if (error instanceof Error) {
                errorMessage = error.message;
            }

            setEditVehicleError(errorMessage);
        } finally {
            setIsUpdatingVehicle(false);
        }
    }

        // Απενεργοποιούμε όχημα του Fleet του Manager μέσω του API Gateway.
    async function deactivateVehicle(vehicle: Vehicle) {

        setActivateVehicleError("");
        setActivateVehicleSuccess("");
        setActivateVehicleError("");
        setActivateVehicleSuccess("");

        if (!token || isVehicleActionRunning) return;
        if (vehicle.status !== "ACTIVE") return;

        const confirmed = window.confirm(`Deactivate vehicle ${vehicle.plate_number}?`);
        if (!confirmed) return;

        setDeactivatingVehicleId(vehicle.id);
        setDeactivateVehicleError("");
        setDeactivateVehicleSuccess("");

        try {
            const response = await fetch(
                `http://localhost:8004/api/v1/vehicles/${encodeURIComponent(vehicle.id)}/deactivate`,
                { method: "POST", headers: { Authorization: `Bearer ${token}`, }, }
            );

            const result = await response.json();

            if (!response.ok) {
                let errorMessage = `Failed to deactivate vehicle: ${response.status}`;

                if (result !== null && typeof result.detail === "string") {
                    errorMessage = result.detail;
                }

                throw new Error(errorMessage);
            }

            // Η κοινή λίστα ενημερώνεται με το νέο status και την αποδέσμευση Driver.
            onVehicleUpdated(result);

            if (editingVehicleId === vehicle.id) {
                setEditingVehicleId(null);
            }

            if (assignmentVehicleId === vehicle.id) {
                setAssignmentVehicleId(null);
            }

            setDeactivateVehicleSuccess("Vehicle deactivated successfully.");
        } catch (error) {
            let errorMessage = "Could not deactivate vehicle.";

            if (error instanceof Error) {
                errorMessage = error.message;
            }

            setDeactivateVehicleError(errorMessage);
        } finally {
            setDeactivatingVehicleId(null);
        }
    }

        // Ενεργοποιούμε το όχημα χωρίς αυτόματη επαναφορά της προηγούμενης ανάθεσης Driver.
    async function activateVehicle(vehicle: Vehicle) {
        if (!token || isVehicleActionRunning) return;
        if (vehicle.status !== "INACTIVE") return;

        const confirmed = window.confirm(`Activate vehicle ${vehicle.plate_number}?`);
        if (!confirmed) return;

        setActivatingVehicleId(vehicle.id);
        setActivateVehicleError("");
        setActivateVehicleSuccess("");
        setDeactivateVehicleError("");
        setDeactivateVehicleSuccess("");

        try {
            const response = await fetch(
                `http://localhost:8004/api/v1/vehicles/${encodeURIComponent(vehicle.id)}/activate`,
                { method: "POST", headers: { Authorization: `Bearer ${token}`, }, }
            );

            const result = await response.json();

            if (!response.ok) {
                let errorMessage = `Failed to activate vehicle: ${response.status}`;

                if (result !== null && typeof result.detail === "string") {
                    errorMessage = result.detail;
                }

                throw new Error(errorMessage);
            }

            // Ενημερώνουμε την κοινή λίστα με την απάντηση του backend.
            onVehicleUpdated(result);
            setActivateVehicleSuccess("Vehicle activated successfully.");
        } catch (error) {
            let errorMessage = "Could not activate vehicle.";

            if (error instanceof Error) {
                errorMessage = error.message;
            }

            setActivateVehicleError(errorMessage);
        } finally {
            setActivatingVehicleId(null);
        }
    }

    return (
        <div>
            <h3>Fleet Vehicles</h3>

            {/* Το ίδιο κουμπί ανοίγει και κλείνει τη φόρμα δημιουργίας. */}
            <button type="button" onClick={() => setShowCreateVehicle((previous) => !previous)} disabled={isCreatingVehicle || isAssigningDriver}> Create Vehicle </button>

            {showCreateVehicle && (
                <form onSubmit={createVehicle}>
                    <h3>Create Vehicle</h3>

                    <div>
                        <label htmlFor="manager-vehicle-plate">Plate Number *</label>
                        <input id="manager-vehicle-plate" required value={vehicleForm.plate_number}
                               onChange={(event) => setVehicleForm({...vehicleForm, plate_number: event.target.value,})} />
                    </div>

                    <div>
                        <label htmlFor="manager-vehicle-brand">Brand</label>
                        <input id="manager-vehicle-brand" value={vehicleForm.brand}
                               onChange={(event) => setVehicleForm({...vehicleForm, brand: event.target.value,})} />
                    </div>

                    <div>
                        <label htmlFor="manager-vehicle-model">Model</label>
                        <input id="manager-vehicle-model" value={vehicleForm.model}
                               onChange={(event) => setVehicleForm({...vehicleForm, model: event.target.value,})} />
                    </div>

                    <div>
                        <label htmlFor="manager-vehicle-year">Year</label>
                        <input id="manager-vehicle-year" type="number" step="1" value={vehicleForm.year}
                               onChange={(event) => setVehicleForm({...vehicleForm, year: event.target.value,})} />
                    </div>

                    <div>
                        <label htmlFor="manager-vehicle-imei">Device IMEI *</label>
                        <input id="manager-vehicle-imei" required value={vehicleForm.device_imei}
                               onChange={(event) => setVehicleForm({...vehicleForm, device_imei: event.target.value,})} />
                    </div>

                    {/* Η λίστα περιέχει τους Drivers του Fleet του Manager. */}
                    <div>
                        <label htmlFor="manager-vehicle-driver">Driver</label>
                        <select id="manager-vehicle-driver" value={vehicleForm.driver_id}
                                onChange={(event) => setVehicleForm({...vehicleForm, driver_id: event.target.value,})}>
                            <option value="">Unassigned</option>

                            {drivers.map((driver) => {
                                if (driver.status !== "ACTIVE") return null;
                                if (driver.fleet_id === null || driver.fleet_id === "") return null;

                                return (
                                    <option key={driver.driver_id} value={driver.driver_id}>
                                        {driver.first_name} {driver.last_name} ({driver.driver_id})
                                    </option>
                                );
                            })}
                        </select>
                    </div>

                    <button type="submit" disabled={isCreatingVehicle || isAssigningDriver}> Create Vehicle </button>
                </form>
            )}

            {/* Τα μηνύματα παραμένουν ορατά και όταν κλείνει η φόρμα. */}
            {createVehicleError !== "" && (<p role="alert">{createVehicleError}</p>)}
            {createVehicleSuccess !== "" && (<p role="status">{createVehicleSuccess}</p>)}

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
                            <th colSpan={5}>Actions</th>
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
                                <td>
                                    <button type="button" onClick={() => toggleVehicleEdit(vehicle)} disabled={isCreatingVehicle || isAssigningDriver || isUpdatingVehicle}> Edit </button>
                                </td>
                                <td>
                                    {vehicle.status === "ACTIVE" && (<button type="button" onClick={() => deactivateVehicle(vehicle)} disabled={isVehicleActionRunning}> Deactivate </button>)}
                                    {vehicle.status === "INACTIVE" && (<button type="button" onClick={() => activateVehicle(vehicle)} disabled={isVehicleActionRunning}> Activate </button>)}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}

            {
                deactivateVehicleError !== "" && (<p role="alert">{deactivateVehicleError}</p>)
            }
            {
                deactivateVehicleSuccess !== "" && (<p role="status">{deactivateVehicleSuccess}</p>)
            }
            {
                activateVehicleError !== "" && (<p role="alert">{activateVehicleError}</p>)
            }
            {
                activateVehicleSuccess !== "" && (<p role="status">{activateVehicleSuccess}</p>)
            }

            {
                editingVehicleId !== null && (
                <form onSubmit={updateVehicle}>
                    <h3>Edit Vehicle: {editingVehicleId}</h3>

                    <div>
                        <label htmlFor="manager-edit-plate">Plate Number *</label>
                        <input id="manager-edit-plate" required value={editVehicleForm.plate_number}
                               onChange={(event) => setEditVehicleForm({...editVehicleForm, plate_number: event.target.value,})} />
                    </div>

                    <div>
                        <label htmlFor="manager-edit-brand">Brand</label>
                        <input id="manager-edit-brand" value={editVehicleForm.brand}
                               onChange={(event) => setEditVehicleForm({...editVehicleForm, brand: event.target.value,})} />
                    </div>

                    <div>
                        <label htmlFor="manager-edit-model">Model</label>
                        <input id="manager-edit-model" value={editVehicleForm.model}
                               onChange={(event) => setEditVehicleForm({...editVehicleForm, model: event.target.value,})} />
                    </div>

                    <div>
                        <label htmlFor="manager-edit-year">Year</label>
                        <input id="manager-edit-year" type="number" step="1" value={editVehicleForm.year}
                               onChange={(event) => setEditVehicleForm({...editVehicleForm, year: event.target.value,})} />
                    </div>

                    <div>
                        <label htmlFor="manager-edit-imei">Device IMEI *</label>
                        <input id="manager-edit-imei" required value={editVehicleForm.device_imei}
                               onChange={(event) => setEditVehicleForm({...editVehicleForm, device_imei: event.target.value,})} />
                    </div>

                    {editVehicleError !== "" && (<p role="alert">{editVehicleError}</p>)}

                    <button type="submit" disabled={isUpdatingVehicle || isCreatingVehicle || isAssigningDriver}> Save Changes </button>
                    <button type="button" onClick={() => setEditingVehicleId(null)} disabled={isUpdatingVehicle}> Cancel </button>
                </form>
            )}

            {
                assignmentVehicle !== undefined && (
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