import { useState } from "react";
import type { DriverProfile } from "../types/DriverProfile";
import type { Vehicle } from "../types/Vehicle";

interface FleetDriversProps {
    drivers: DriverProfile[];
    vehicles: Vehicle[];
    onTrackVehicle: (vehicle: Vehicle) => void;
}

// Εμφανίζουμε παύλα όταν ένα προαιρετικό στοιχείο δεν έχει τιμή.
function displayDriverValue(value: string | null): string {
    if (value === null || value === "") return "—";
    return value;
}

function FleetDrivers({ drivers, vehicles, onTrackVehicle }: FleetDriversProps) {
    const [viewDriverId, setViewDriverId] = useState<string | null>(null);
        // Κρατάμε τον Driver του οποίου εμφανίζουμε τα ανατεθειμένα οχήματα.
    const [selectedDriverId, setSelectedDriverId] = useState<string | null>(null);

    // Φιλτράρουμε την ήδη φορτωμένη λίστα οχημάτων του Fleet.
    const selectedDriverVehicles = vehicles.filter((vehicle) => vehicle.driver_id === selectedDriverId);

    // Ανοίγουμε ή κλείνουμε την προβολή του συγκεκριμένου Driver.
    function toggleDriverDetails(driver: DriverProfile) {
        if (viewDriverId === driver.driver_id) {
            setViewDriverId(null);
        } else {
            setViewDriverId(driver.driver_id);
        }
    }

    const selectedDriver = drivers.find((driver) => driver.driver_id === viewDriverId);

    return (
        <div>
            <h3>Fleet Drivers</h3>

            {drivers.length === 0 && (<p>No drivers found.</p>)}

            {drivers.length > 0 && (
                <table>
                    <thead>
                        <tr>
                            <th>Driver ID</th>
                            <th>Name</th>
                            <th>Email</th>
                            <th>Status</th>
                            <th colSpan={2}>Actions</th>
                        </tr>
                    </thead>

                    <tbody>
                        {drivers.map((driver) => (
                            <tr key={driver.id}>
                                <td>{driver.driver_id}</td>
                                <td>{driver.first_name} {driver.last_name}</td>
                                <td>{displayDriverValue(driver.email)}</td>
                                <td>{driver.status}</td>
                                <td>
                                    <button type="button" onClick={() => toggleDriverDetails(driver)}> View </button>
                                </td>
                                <td>
                                    <button type="button" onClick={() => setSelectedDriverId(driver.driver_id)}> Vehicles </button>
                                    {/*<button type="button" onClick={() => setSelectedDriverId(driver.driver_id)}> Vehicles </button>*/}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}

            {/* Τα στοιχεία προέρχονται από την ήδη φορτωμένη λίστα του Fleet. */}
            {
                selectedDriver !== undefined && (
                    <div className="dashboard-details">
                        <h3>Driver Details: {selectedDriver.driver_id}</h3>

                        <p>First Name: {selectedDriver.first_name}</p>
                        <p>Last Name: {selectedDriver.last_name}</p>
                        <p>Date of Birth: {displayDriverValue(selectedDriver.date_of_birth)}</p>
                        <p>Identity Card Number: {displayDriverValue(selectedDriver.identity_card_number)}</p>
                        <p>Tax ID: {displayDriverValue(selectedDriver.tax_id)}</p>
                        <p>Phone Number: {displayDriverValue(selectedDriver.phone_number)}</p>
                        <p>Email: {displayDriverValue(selectedDriver.email)}</p>
                        <p>License Number: {displayDriverValue(selectedDriver.license_number)}</p>
                        <p>License Category: {displayDriverValue(selectedDriver.license_category)}</p>
                        <p>License Expiry: {displayDriverValue(selectedDriver.license_expiry_date)}</p>
                        <p>Hire Date: {displayDriverValue(selectedDriver.hire_date)}</p>
                        <p>Fleet ID: {displayDriverValue(selectedDriver.fleet_id)}</p>
                        <p>Status: {selectedDriver.status}</p>

                        <button type="button" onClick={() => setViewDriverId(null)}> Close </button>
                    </div>
                )
            }
                        {/* Εμφανίζουμε όλα τα οχήματα του επιλεγμένου Driver. */}
            {selectedDriverId !== null && (
                <div>
                    <h3>Vehicles assigned to Driver: {selectedDriverId}</h3>
                    <button type="button" onClick={() => setSelectedDriverId(null)}> Close </button>

                    {selectedDriverVehicles.length === 0 && (<p>No vehicles assigned to this Driver.</p>)}

                    {selectedDriverVehicles.length > 0 && (
                        <table>
                            <thead>
                                <tr>
                                    <th>Plate Number</th>
                                    <th>Brand</th>
                                    <th>Model</th>
                                    <th>Device IMEI</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>

                            <tbody>
                                {selectedDriverVehicles.map((vehicle) => (
                                    <tr key={vehicle.id}>
                                        <td>{vehicle.plate_number}</td>
                                        <td>{vehicle.brand}</td>
                                        <td>{vehicle.model}</td>
                                        <td>{vehicle.device_imei}</td>
                                        <td>
                                            <button type="button" onClick={() => onTrackVehicle(vehicle)}> Track </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            )}
        </div>
    );
}

export default FleetDrivers;