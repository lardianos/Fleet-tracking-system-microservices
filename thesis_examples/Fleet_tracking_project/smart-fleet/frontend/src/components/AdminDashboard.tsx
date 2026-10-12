
import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import type { Vehicle } from "../types/Vehicle";
import type { DriverProfile as Driver } from "../types/DriverProfile";
import type { FleetManagerProfile as FleetManager } from "../types/FleetManagerProfile";
import type { Fleet } from "../types/Fleet";
import { useVehicleTracking } from "../hooks/useVehicleTracking";
import LatestPosition from "./LatestPosition";
import LiveMap from "./LiveMap";
// Περιγράφουμε μόνο τα πεδία του Fleet που χρειαζόμαστε
// για την εμφάνιση της λίστας στο Admin Dashboard.

interface FleetCreateForm {
    fleet_id: string;
    name: string;
    description: string;
    base_location: {
        name: string;
        address: string;
        city: string;
        postal_code: string;
        latitude: string;
        longitude: string;
    };
}
interface FleetManagerCreateForm {
    username: string;
    manager_id: string;
    first_name: string;
    last_name: string;
    email: string;
    fleet_id: string;
    department_id: string;
    date_of_birth: string;
    identity_card_number: string;
    tax_id: string;
    phone_number: string;
    hire_date: string;
}
// Κρατάμε τις τιμές της φόρμας ως κείμενο.
// Κατά την υποβολή μετατρέπουμε το year σε αριθμό.
interface VehicleCreateForm {
    plate_number: string;
    brand: string;
    model: string;
    year: string;
    device_imei: string;
    driver_id: string;
    fleet_id: string;
}

// Περιγράφουμε τα πεδία της φόρμας δημιουργίας Driver.
// Το Keycloak user id δημιουργείται από το Backend
// και δεν συμπληρώνεται από τον Admin.
interface DriverCreateForm {
    username: string;
    driver_id: string;
    first_name: string;
    last_name: string;
    email: string;
    date_of_birth: string;
    identity_card_number: string;
    tax_id: string;
    phone_number: string;
    license_number: string;
    license_category: string;
    license_expiry_date: string;
    hire_date: string;
    fleet_id: string;
    department_id: string;
}
const emptyFleetForm: FleetCreateForm = {
    fleet_id: "",
    name: "",
    description: "",
    base_location: {
        name: "",
        address: "",
        city: "",
        postal_code: "",
        latitude: "",
        longitude: "",
    },
};

// Αρχικές τιμές για τη φόρμα δημιουργίας Fleet Manager.
// Όλα τα πεδία ξεκινούν κενά, ώστε να μην υπάρχουν
// προκαθορισμένα προσωπικά στοιχεία.
const emptyFleetManagerForm: FleetManagerCreateForm = {
    username: "",
    manager_id: "",
    first_name: "",
    last_name: "",
    email: "",
    fleet_id: "",
    department_id: "",
    date_of_birth: "",
    identity_card_number: "",
    tax_id: "",
    phone_number: "",
    hire_date: "",
};

// Αρχικές τιμές για τη φόρμα δημιουργίας Driver.
// Τα πεδία ξεκινούν κενά και συμπληρώνονται από τον Admin.
const emptyDriverForm: DriverCreateForm = {
    username: "",
    driver_id: "",
    first_name: "",
    last_name: "",
    email: "",
    date_of_birth: "",
    identity_card_number: "",
    tax_id: "",
    phone_number: "",
    license_number: "",
    license_category: "",
    license_expiry_date: "",
    hire_date: "",
    fleet_id: "",
    department_id: "",
};

// Η φόρμα ξεκινά χωρίς προκαθορισμένα στοιχεία ή αναθέσεις.
const emptyVehicleForm: VehicleCreateForm = {
    plate_number: "",
    brand: "",
    model: "",
    year: "",
    device_imei: "",
    driver_id: "",
    fleet_id: "",
};

function AdminDashboard() {
     // Χρησιμοποιούμε το υπάρχον Keycloak authentication.
    const { token, hasRole } = useAuth();
    const isAdmin = hasRole("admin");


    // Κρατάμε τη λίστα Fleets και την κατάσταση του request.
    const [fleets, setFleets] = useState<Fleet[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState("");


    // Κρατάμε τις τιμές της φόρμας δημιουργίας Fleet.
    const [fleetForm, setFleetForm] = useState<FleetCreateForm>( emptyFleetForm );

    // Ξεχωρίζουμε τη δημιουργία από τη φόρτωση της λίστας.
    const [isCreating, setIsCreating] = useState(false);
    const [createError, setCreateError] = useState("");
    const [createSuccess, setCreateSuccess] = useState("");


        // Κρατάμε το Fleet που επεξεργαζόμαστε και τις νέες τιμές του.
    const [editingFleetId, setEditingFleetId] = useState<string | null>(null);
    const [editFleetForm, setEditFleetForm] = useState<FleetCreateForm>( emptyFleetForm );
    const [viewFleetId, setViewFleetId] = useState<string | null>(null);

    const [isUpdating, setIsUpdating] = useState(false);
    const [editError, setEditError] = useState("");

    // Παρακολουθούμε ποιο Fleet διαγράφεται, ώστε να αποτρέπουμε
    // επαναλαμβανόμενα αιτήματα διαγραφής.
    const [deletingFleetId, setDeletingFleetId] = useState<string | null>(null);

    // Διατηρούμε ξεχωριστά τα μηνύματα διαγραφής.
    const [deleteError, setDeleteError] = useState("");
    const [deleteSuccess, setDeleteSuccess] = useState("");

    // Διατηρούμε ξεχωριστά τα δεδομένα και την κατάσταση
    // φόρτωσης των Fleet Managers από τα Fleets.
    const [fleetManagers, setFleetManagers] = useState<FleetManager[]>([]);
    const [isLoadingManagers, setIsLoadingManagers] = useState(true);
    const [managersError, setManagersError] = useState("");

    // Αποθηκεύει τις τιμές που συμπληρώνει ο Admin στη φόρμα.
    const [fleetManagerForm, setFleetManagerForm] = useState<FleetManagerCreateForm>(emptyFleetManagerForm);
    // Δείχνει αν βρίσκεται σε εξέλιξη η δημιουργία Fleet Manager.
    const [isCreatingManager, setIsCreatingManager] = useState(false);
    // Κρατούν το αποτέλεσμα της προσπάθειας δημιουργίας.
    const [createManagerError, setCreateManagerError] = useState("");
    const [createManagerSuccess, setCreateManagerSuccess] = useState("");

    // Κρατάμε τον Fleet Manager που έχει επιλεγεί για επεξεργασία
    // και τις τιμές που θα εμφανίζονται στη φόρμα Edit.
    const [editingManagerId, setEditingManagerId] = useState<string | null>(null);
    const [editFleetManagerForm, setEditFleetManagerForm] = useState<FleetManagerCreateForm>(emptyFleetManagerForm);


    // Ξεχωριστή κατάσταση για την ενημέρωση του Fleet Manager.
    const [isUpdatingManager, setIsUpdatingManager] = useState(false);
    const [editManagerError, setEditManagerError] = useState("");

    // Κρατάμε το ID του Fleet Manager που επιλέχθηκε για προβολή.
    const [viewManagerId, setViewManagerId] = useState<string | null>(null);


    // Κρατάμε το ID του Fleet Manager που απενεργοποιείται,
    // ώστε να αποτρέπουμε επαναλαμβανόμενα αιτήματα.
    const [deactivatingManagerId, setDeactivatingManagerId] = useState<string | null>(null);

    // Κρατάμε τα μηνύματα επιτυχίας και αποτυχίας της απενεργοποίησης.
    const [deactivateManagerError, setDeactivateManagerError] = useState("");
    const [deactivateManagerSuccess, setDeactivateManagerSuccess] = useState("");

    // Κρατάμε το ID του Fleet Manager που ενεργοποιείται,
    // ώστε να αποτρέπουμε επαναλαμβανόμενα αιτήματα.
    const [activatingManagerId, setActivatingManagerId] = useState<string | null>(null);

    // Κρατάμε τα μηνύματα επιτυχίας και αποτυχίας της ενεργοποίησης.
    const [activateManagerError, setActivateManagerError] = useState("");
    const [activateManagerSuccess, setActivateManagerSuccess] = useState("");

    // Κρατάμε το ID του Fleet Manager που διαγράφεται,
    // ώστε να αποτρέπουμε επαναλαμβανόμενα αιτήματα.
    const [deletingManagerId, setDeletingManagerId] = useState<string | null>(null);

    // Κρατάμε τα μηνύματα επιτυχίας και αποτυχίας της διαγραφής.
    const [deleteManagerError, setDeleteManagerError] = useState("");
    const [deleteManagerSuccess, setDeleteManagerSuccess] = useState("");

    // Αποθηκεύουμε τη λίστα των Drivers που επιστρέφει το Fleet API.
    const [drivers, setDrivers] = useState<Driver[]>([]);
    // Παρακολουθούμε αν βρίσκεται σε εξέλιξη η ανάκτηση των Drivers.
    const [isLoadingDrivers, setIsLoadingDrivers] = useState(true);
    // Αποθηκεύουμε τυχόν σφάλμα κατά την ανάκτηση των Drivers.
    const [driversError, setDriversError] = useState("");
    // Αποθηκεύουμε τις τιμές που συμπληρώνει ο Admin
    // στη φόρμα δημιουργίας νέου Driver.
    const [driverForm, setDriverForm] = useState<DriverCreateForm>(emptyDriverForm);

    // Παρακολουθούμε αν βρίσκεται σε εξέλιξη η δημιουργία Driver,
    // ώστε να αποτρέπουμε πολλαπλές υποβολές της φόρμας.
    const [isCreatingDriver, setIsCreatingDriver] = useState(false);

    // Αποθηκεύουμε το μήνυμα σφάλματος αν αποτύχει η δημιουργία.
    const [createDriverError, setCreateDriverError] = useState("");

    // Εμφανίζουμε μήνυμα επιτυχίας όταν δημιουργηθεί ο Driver.
    const [createDriverSuccess, setCreateDriverSuccess] = useState("");
    // Κρατάμε το ID του Driver που έχει επιλέξει ο Admin
    // για να εμφανίσουμε αναλυτικά τα στοιχεία του.
    const [viewDriverId, setViewDriverId] = useState<string | null>(null);

    // Κρατάμε τον Driver που έχει επιλεγεί για επεξεργασία
    // και τις τιμές που θα εμφανίζονται στη φόρμα Edit.
    const [editingDriverId, setEditingDriverId] = useState<string | null>(null);
    const [editDriverForm, setEditDriverForm] = useState<DriverCreateForm>(emptyDriverForm);

    // Ξεχωριστή κατάσταση για την ενημέρωση του Driver.
    const [isUpdatingDriver, setIsUpdatingDriver] = useState(false);
    const [editDriverError, setEditDriverError] = useState("");

        // Κρατάμε το ID του Driver που απενεργοποιείται,
    // ώστε να αποτρέπουμε επαναλαμβανόμενα αιτήματα.
    const [deactivatingDriverId, setDeactivatingDriverId] = useState<string | null>(null);

    // Κρατάμε τα μηνύματα επιτυχίας και αποτυχίας της απενεργοποίησης.
    const [deactivateDriverError, setDeactivateDriverError] = useState("");
    const [deactivateDriverSuccess, setDeactivateDriverSuccess] = useState("");

    // Κρατάμε το ID του Driver που ενεργοποιείται,
    // ώστε να αποτρέπουμε επαναλαμβανόμενα αιτήματα.
    const [activatingDriverId, setActivatingDriverId] = useState<string | null>(null);

    // Κρατάμε ξεχωριστά τα μηνύματα επιτυχίας
    // και αποτυχίας της ενεργοποίησης.
    const [activateDriverError, setActivateDriverError] = useState("");
    const [activateDriverSuccess, setActivateDriverSuccess] = useState("");

    // Κρατάμε το ID του Driver που διαγράφεται,
    // ώστε να αποτρέπουμε επαναλαμβανόμενα αιτήματα διαγραφής.
    const [deletingDriverId, setDeletingDriverId] = useState<string | null>(null);

    // Κρατάμε ξεχωριστά τα μηνύματα επιτυχίας
    // και αποτυχίας της διαγραφής.
    const [deleteDriverError, setDeleteDriverError] = useState("");
    const [deleteDriverSuccess, setDeleteDriverSuccess] = useState("");

    // Κρατάμε τον Driver του οποίου θέλουμε να δούμε τα ανατεθειμένα οχήματα.
    const [selectedDriverId, setSelectedDriverId] = useState<string | null>(null);

        // Κρατάμε τα οχήματα που είναι ανατεθειμένα στον επιλεγμένο Driver.
    const [driverVehicles, setDriverVehicles] = useState<Vehicle[]>([]);

    // Παρακολουθούμε τη φόρτωση των οχημάτων του Driver.
    const [isLoadingDriverVehicles, setIsLoadingDriverVehicles] = useState(false);

    // Κρατάμε το μήνυμα σφάλματος αν αποτύχει η ανάκτηση των οχημάτων.
    const [driverVehiclesError, setDriverVehiclesError] = useState("");

        // Κρατάμε το όχημα που επέλεξε ο Admin για παρακολούθηση GPS.
    const [selectedTrackingVehicle, setSelectedTrackingVehicle] = useState<Vehicle | null>(null);
        // Παρακολουθούμε το IMEI του επιλεγμένου οχήματος.
    // Χωρίς επιλογή οχήματος, το hook κλείνει τη σύνδεση.
    // Βρίσκουμε το IMEI του οχήματος που επέλεξε ο Admin.
    let trackingImei: string | null = null;

    if (selectedTrackingVehicle !== null) { trackingImei = selectedTrackingVehicle.device_imei; }
    // Το κοινό hook αναλαμβάνει τη σύνδεση και τις ενημερώσεις θέσης.
    const latestPosition = useVehicleTracking(trackingImei);

        // Κρατάμε όλα τα οχήματα που επιστρέφει το API για τον Admin.
    const [vehicles, setVehicles] = useState<Vehicle[]>([]);

    // Παρακολουθούμε τη φόρτωση της συνολικής λίστας οχημάτων.
    const [isLoadingVehicles, setIsLoadingVehicles] = useState(true);

    // Εμφανίζουμε τυχόν σφάλμα κατά την ανάκτηση των οχημάτων.
    const [vehiclesError, setVehiclesError] = useState("");

        // Κρατάμε το ID του οχήματος που επέλεξε ο Admin για προβολή.
    const [viewVehicleId, setViewVehicleId] = useState<string | null>(null);

        // Κρατάμε τα στοιχεία που συμπληρώνει ο Admin.
    const [vehicleForm, setVehicleForm] = useState<VehicleCreateForm>(emptyVehicleForm);

    // Παρακολουθούμε την υποβολή και τα μηνύματα αποτελέσματος.
    const [isCreatingVehicle, setIsCreatingVehicle] = useState(false);
    const [createVehicleError, setCreateVehicleError] = useState("");
    const [createVehicleSuccess, setCreateVehicleSuccess] = useState("");

        // Κρατάμε το όχημα που επεξεργάζεται ο Admin.
    const [editingVehicleId, setEditingVehicleId] = useState<string | null>(null);

    // Χρησιμοποιούμε τα ίδια πεδία φόρμας για τη δημιουργία και το Edit.
    const [editVehicleForm, setEditVehicleForm] = useState<VehicleCreateForm>(emptyVehicleForm);

    // Παρακολουθούμε την ενημέρωση και τυχόν σφάλμα.
    const [isUpdatingVehicle, setIsUpdatingVehicle] = useState(false);
    const [editVehicleError, setEditVehicleError] = useState("");

        // Κρατάμε το ID του οχήματος που απενεργοποιείται.
    const [deactivatingVehicleId, setDeactivatingVehicleId] = useState<string | null>(null);

    // Κρατάμε το αποτέλεσμα της απενεργοποίησης.
    const [deactivateVehicleError, setDeactivateVehicleError] = useState("");
    const [deactivateVehicleSuccess, setDeactivateVehicleSuccess] = useState("");

        // Κρατάμε το όχημα που ενεργοποιείται και το αποτέλεσμα του αιτήματος.
    const [activatingVehicleId, setActivatingVehicleId] = useState<string | null>(null);
    const [activateVehicleError, setActivateVehicleError] = useState("");
    const [activateVehicleSuccess, setActivateVehicleSuccess] = useState("");

        // Κρατάμε το όχημα που διαγράφεται και το αποτέλεσμα του αιτήματος.
    const [deletingVehicleId, setDeletingVehicleId] = useState<string | null>(null);
    const [deleteVehicleError, setDeleteVehicleError] = useState("");
    const [deleteVehicleSuccess, setDeleteVehicleSuccess] = useState("");
    const [vehiclesRefreshNumber, setVehiclesRefreshNumber] = useState(0);

    useEffect(() => {
        // Δεν ζητάμε δεδομένα αν ο χρήστης δεν είναι Admin
        // ή αν δεν υπάρχει διαθέσιμο access token.
        if (!isAdmin || !token) {
            setIsLoading(false);
            return;
        }

        // Επιτρέπει την ακύρωση του request όταν το component
        // αποσυνδεθεί ή αλλάξουν οι εξαρτήσεις του effect.
        const controller = new AbortController();

        async function loadFleets() {
            setIsLoading(true);
            setError("");

            try {
                // Το Frontend επικοινωνεί μόνο με το API Gateway.
                const response = await fetch(
                    "http://localhost:8004/api/v1/fleets",
                    {
                        headers: {
                            Authorization: `Bearer ${token}`,
                        },
                        signal: controller.signal,
                    }
                );

                if (!response.ok) {
                    throw new Error(
                        `Failed to load fleets: ${response.status}`
                    );
                }

                const fleetData: Fleet[] = await response.json();

                // Ενημερώνουμε τη λίστα μόνο αν το request
                // δεν έχει ακυρωθεί.
                if (!controller.signal.aborted) {
                    setFleets(fleetData);
                }
            } catch (requestError) {
                if (!controller.signal.aborted) {
                    console.error(
                        "Failed to load fleets:",
                        requestError
                    );

                    setError("Could not load fleets.");
                }
            } finally {
                if (!controller.signal.aborted) {
                    setIsLoading(false);
                }
            }
        }

        loadFleets();

        return () => {
            controller.abort();
        };
    }, [token, isAdmin]);

    useEffect(() => {
        if (!isAdmin || !token) {
            setIsLoadingManagers(false);
            return;
        }

        // Ακυρώνουμε το request αν αποσυνδεθεί το component
        // ή αλλάξει το access token.
        const controller = new AbortController();

        async function loadFleetManagers() {
            setIsLoadingManagers(true);
            setManagersError("");

            try {
                // Όλα τα requests περνούν από το API Gateway.
                const response = await fetch( "http://localhost:8004/api/v1/admin/fleet-managers", {
                        headers: { Authorization: `Bearer ${token}`, }, signal: controller.signal,
                    }
                );

                if (!response.ok) {
                    throw new Error( `Failed to load fleet managers: ${response.status}` );
                }

                const managerData: FleetManager[] = await response.json();

                if (!controller.signal.aborted) {
                    setFleetManagers(managerData);
                }
            } catch (requestError) {
                if (!controller.signal.aborted) {
                    console.error( "Failed to load fleet managers:", requestError );

                    setManagersError("Could not load fleet managers.");
                }
            } finally {
                if (!controller.signal.aborted) {
                    setIsLoadingManagers(false);
                }
            }
        }

        loadFleetManagers();

        return () => controller.abort();
    }, [token, isAdmin]);

    useEffect(() => {
        // Δεν ανακτούμε Drivers αν ο χρήστης δεν είναι Admin
        // ή αν δεν υπάρχει διαθέσιμο access token.
        if (!isAdmin || !token) {
            setIsLoadingDrivers(false);
            return;
        }

        // Χρησιμοποιούμε AbortController για να ακυρώνουμε
        // το προηγούμενο request όταν αλλάζει το token
        // ή όταν αποσυνδέεται το component.
        const controller = new AbortController();

        async function loadDrivers() {
            setIsLoadingDrivers(true);
            setDriversError("");

            try {
                // Το Frontend επικοινωνεί μόνο με το API Gateway.
                // Το Gateway ελέγχει τον Admin και προωθεί
                // το αίτημα στο Fleet API.
                const response = await fetch(
                    "http://localhost:8004/api/v1/admin/drivers",
                    {
                        headers: {
                            Authorization: `Bearer ${token}`,
                        },
                        signal: controller.signal,
                    }
                );

                if (!response.ok) {
                    throw new Error(
                        `Failed to load drivers: ${response.status}`
                    );
                }

                const data: Driver[] = await response.json();

                // Αποθηκεύουμε τα Driver Profiles μόνο εφόσον
                // το request δεν έχει ακυρωθεί.
                if (!controller.signal.aborted) {
                    setDrivers(data);
                }
            } catch (error) {
                // Η ακύρωση request δεν αποτελεί πραγματικό σφάλμα.
                if (controller.signal.aborted) return;

                setDriversError(
                    error instanceof Error
                        ? error.message
                        : "Could not load drivers."
                );
            } finally {
                if (!controller.signal.aborted) {
                    setIsLoadingDrivers(false);
                }
            }
        }

        loadDrivers();

        return () => controller.abort();
    }, [isAdmin, token]);

    useEffect(() => {
        // Ζητάμε τη λίστα μόνο όταν υπάρχει συνδεδεμένος Admin.
        if (!isAdmin || !token) {
            setIsLoadingVehicles(false);
            return;
        }

        // Ακυρώνουμε το request όταν αλλάξει το token
        // ή όταν αποσυνδεθεί το Dashboard.
        const controller = new AbortController();

        async function loadVehicles() {
            setIsLoadingVehicles(true);
            setVehiclesError("");

            try {
                const response = await fetch(
                    "http://localhost:8004/api/v1/vehicles",
                    {
                        headers: {
                            Authorization: `Bearer ${token}`,
                        },
                        signal: controller.signal,
                    }
                );

                if (!response.ok) {
                    throw new Error(
                        `Failed to load vehicles: ${response.status}`
                    );
                }

                const data: Vehicle[] = await response.json();

                // Δεν ενημερώνουμε τη λίστα αν το request ακυρώθηκε.
                if (!controller.signal.aborted) {
                    setVehicles(data);
                }
            } catch (error) {
                if (!controller.signal.aborted) {
                    console.error("Failed to load vehicles:", error);
                    setVehiclesError("Could not load vehicles.");
                }
            } finally {
                if (!controller.signal.aborted) {
                    setIsLoadingVehicles(false);
                }
            }
        }

        loadVehicles();

        return () => {
            controller.abort();
        };
    }, [isAdmin, token, vehiclesRefreshNumber]);

    useEffect(() => {
        // Χωρίς επιλεγμένο Driver καθαρίζουμε τη λίστα.
        if (!token || !isAdmin || selectedDriverId === null) {
            setDriverVehicles([]);
            setDriverVehiclesError("");
            setIsLoadingDriverVehicles(false);
            return;
        }

        const controller = new AbortController();

        // Ανακτούμε τα οχήματα του επιλεγμένου Driver από το API Gateway.
        async function loadSelectedDriverVehicles() {
            setDriverVehicles([]);
            setDriverVehiclesError("");
            setIsLoadingDriverVehicles(true);

            try {
                const response = await fetch(
                    `http://localhost:8004/api/v1/admin/drivers/${encodeURIComponent(selectedDriverId)}/vehicles`,
                    { headers: { Authorization: `Bearer ${token}`, }, signal: controller.signal, }
                );

                if (controller.signal.aborted) return;

                const result = await response.json();

                if (!response.ok) {
                    let errorMessage = `Failed to load Driver vehicles: ${response.status}`;

                    if (result !== null && typeof result.detail === "string") {
                        errorMessage = result.detail;
                    }

                    throw new Error(errorMessage);
                }

                if (!Array.isArray(result)) {
                    throw new Error("Invalid Driver vehicles response.");
                }

                // Δεν χρησιμοποιούμε δεδομένα από request που ακυρώθηκε.
                if (!controller.signal.aborted) {
                    setDriverVehicles(result);
                }
            } catch (error) {
                if (controller.signal.aborted) return;

                let errorMessage = "Could not load Driver vehicles.";

                if (error instanceof Error) {
                    errorMessage = error.message;
                }

                setDriverVehiclesError(errorMessage);
            } finally {
                if (!controller.signal.aborted) {
                    setIsLoadingDriverVehicles(false);
                }
            }
        }

        loadSelectedDriverVehicles();

        // Ακυρώνουμε το request όταν κλείνει η λίστα,
        // αλλάζει ο Driver ή χρειάζεται νέα φόρτωση.
        return () => {
            controller.abort();
        };
    }, [isAdmin, token, selectedDriverId, vehiclesRefreshNumber]);

    async function createFleet(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!token || !isAdmin || isCreating) {
        return;
    }

    setCreateError("");
    setCreateSuccess("");

    // Ελέγχουμε τα υποχρεωτικά πεδία πριν από το request.
    if (
        !fleetForm.fleet_id.trim() ||
        !fleetForm.name.trim() ||
        !fleetForm.base_location.name.trim() ||
        !fleetForm.base_location.latitude.trim() ||
        !fleetForm.base_location.longitude.trim()
    ) {
        setCreateError("Please complete all required fields.");
        return;
    }

    const latitude = Number(fleetForm.base_location.latitude);
    const longitude = Number(fleetForm.base_location.longitude);

    // Οι γεωγραφικές συντεταγμένες πρέπει να είναι έγκυρες.
    if (
        !Number.isFinite(latitude) ||
        !Number.isFinite(longitude) ||
        latitude < -90 ||
        latitude > 90 ||
        longitude < -180 ||
        longitude > 180
    ) {
        setCreateError("Invalid latitude or longitude.");
        return;
    }

    const requestBody = {
        fleet_id: fleetForm.fleet_id.trim(),
        name: fleetForm.name.trim(),
        description: fleetForm.description.trim() || null,
        base_location: {
            name: fleetForm.base_location.name.trim(),
            address: fleetForm.base_location.address.trim() || null,
            city: fleetForm.base_location.city.trim() || null,
            postal_code: fleetForm.base_location.postal_code.trim() || null,
            latitude,
            longitude,
        },
    };

    setIsCreating(true);

    try {
        // Η δημιουργία πραγματοποιείται μέσω του API Gateway.
        const response = await fetch(
            "http://localhost:8004/api/v1/fleets",
            {
                method: "POST",
                headers: {
                    Authorization: `Bearer ${token}`,
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(requestBody),
            }
        );

        if (!response.ok) {
            // Εμφανίζουμε το μήνυμα του Backend, όπου είναι διαθέσιμο.
            const errorBody = await response.json().catch(() => null);

            const detail = errorBody?.detail;
            const errorMessage =
                typeof detail === "string"
                    ? detail
                    : `Failed to create fleet: ${response.status}`;

            throw new Error(errorMessage);
        }

        const createdFleet: Fleet = await response.json();

        // Ενημερώνουμε αμέσως τη λίστα χωρίς νέο GET request.
        setFleets((previousFleets) => [
            ...previousFleets,
            createdFleet,
        ]);

        setFleetForm(emptyFleetForm);
        setCreateSuccess("Fleet created successfully.");
    } catch (requestError) {
        setCreateError(
            requestError instanceof Error
                ? requestError.message
                : "Failed to create fleet."
        );
    } finally {
        setIsCreating(false);
    }
}
    function startEditingFleet(fleet: Fleet) {
        // Συμπληρώνουμε τη φόρμα με τις υπάρχουσες τιμές.
        setEditingFleetId(fleet.fleet_id);

        setEditFleetForm({
            fleet_id: fleet.fleet_id,
            name: fleet.name,
            description: fleet.description ?? "",
            base_location: {
                name: fleet.base_location.name,
                address: fleet.base_location.address ?? "",
                city: fleet.base_location.city ?? "",
                postal_code: fleet.base_location.postal_code ?? "",
                latitude: String(fleet.base_location.latitude),
                longitude: String(fleet.base_location.longitude),
            },
        });

        setEditError("");
    }
    function show_fleets(){
        if (isLoading) return <p>Loading fleets...</p>;
        if (error) return <p role="alert">{error}</p>;
        if (fleets.length === 0) return <p>No fleets available.</p>;
        return (
            <table align={"center"}>
                <thead align={"left"}>
                <tr>
                    <th>Fleet ID</th>
                    <th>Name</th>
                    <th>Description</th>
                    <th>Actions</th>
                </tr>
                </thead>

                <tbody align={"left"}>
                {fleets.map((fleet) => (
                    <tr   key={fleet.fleet_id}>
                        <td>| {fleet.fleet_id} </td>
                        <td>| {fleet.name} </td>
                        <td>| {fleet.description ?? "—"} </td>
                        <td>
                            <button type="button" onClick={()=>fleetDetails(fleet)} disabled={deletingFleetId !== null}>view</button>
                            <button type="button" onClick={() => startEditingFleet(fleet)} disabled={deletingFleetId !== null}> Edit </button>
                            <button type="button" onClick={() => deleteFleet(fleet)} disabled={deletingFleetId !== null}>
                                {deletingFleetId === fleet.fleet_id ? "Deleting..." : "Delete"} </button>

                        </td>
                    </tr>
                ))}
                </tbody>
            </table>
        );

    }
    function edit_fleet_details(){
        if(editingFleetId)
            return (
                <form onSubmit={updateFleet}>
                    <h3>Edit Fleet: {editingFleetId}</h3>

                    <div>
                        <label htmlFor="edit-fleet-name">Fleet Name *</label>
                        <input
                            id="edit-fleet-name"
                            required
                            value={editFleetForm.name}
                            onChange={(event) =>
                                setEditFleetForm({...editFleetForm, name: event.target.value, })
                            }
                        />
                    </div>

                    <div>
                        <label htmlFor="edit-fleet-description">Description</label>
                        <textarea
                            id="edit-fleet-description"
                            value={editFleetForm.description}
                            onChange={(event) =>
                                setEditFleetForm({...editFleetForm, description: event.target.value, })
                            }
                        />
                    </div>

                    <h4>Base Location</h4>

                    {(
                        [
                            ["name", "Location Name", true],
                            ["address", "Address", false],
                            ["city", "City", false],
                            ["postal_code", "Postal Code", false],
                            ["latitude", "Latitude", true],
                            ["longitude", "Longitude", true],
                        ] as const
                    ).map(([field, label, required]) => (
                        <div key={field}>
                            <label htmlFor={`edit-fleet-${field}`}>
                                {label}{required ? " *" : ""}
                            </label>

                            <input
                                id={`edit-fleet-${field}`}
                                required={required}
                                type={ field === "latitude" || field === "longitude" ? "number" : "text" }
                                step={ field === "latitude" || field === "longitude" ? "any" : undefined }
                                value={editFleetForm.base_location[field]}
                                onChange={(event) =>
                                    setEditFleetForm({...editFleetForm,base_location: {...editFleetForm.base_location,[field]: event.target.value,},})
                                }
                            />
                        </div>
                    ))}

                    {editError && <p role="alert">{editError}</p>}

                    <button type="submit" disabled={isUpdating}> {isUpdating ? "Saving..." : "Save Changes"} </button>
                    <button type="button" disabled={isUpdating} onClick={() => setEditingFleetId(null)}> Cancel </button>
                </form> )
        return (null)
    }
    function show_fleet_details() {
        const fleet = fleets.find((f) => f.fleet_id === viewFleetId);
        if (!fleet) return null;

        return (
            <div>
                <h3>Details: {fleet.fleet_id}</h3>
                <p>Name: {fleet.name}</p>
                <p>Description: {fleet.description ?? "—"}</p>
                <p>Base: {fleet.base_location.name}</p>
                <p>Address: {fleet.base_location.address ?? "—"}</p>
                <p>City: {fleet.base_location.city ?? "—"}</p>
                <p>Postcode: {fleet.base_location.postal_code ?? "—"}</p>
                <p>Lat/Lng: {fleet.base_location.latitude}, {fleet.base_location.longitude}</p>
                <button type="button" onClick={() => setViewFleetId(null)}>Close</button>
            </div>
        );
    }
    function  fleetDetails(fleet: Fleet){
        setViewFleetId(fleet.fleet_id);
    }
    // Επιλέγουμε τον Fleet Manager που θέλουμε να επεξεργαστούμε
    // και συμπληρώνουμε τη φόρμα με τα διαθέσιμα στοιχεία του.

    async function updateFleet(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();

        if (!token || !isAdmin || !editingFleetId || isUpdating) {
            return;
        }

        setEditError("");

        const latitudeText = editFleetForm.base_location.latitude.trim();
        const longitudeText = editFleetForm.base_location.longitude.trim();

        if (
            !editFleetForm.name.trim() ||
            !editFleetForm.base_location.name.trim() ||
            !latitudeText ||
            !longitudeText
        ) {
            setEditError("Please complete all required fields.");
            return;
        }

        const latitude = Number(latitudeText);
        const longitude = Number(longitudeText);

        if (
            !Number.isFinite(latitude) ||
            !Number.isFinite(longitude) ||
            latitude < -90 ||
            latitude > 90 ||
            longitude < -180 ||
            longitude > 180
        ) {
            setEditError("Invalid latitude or longitude.");
            return;
        }

        // Στέλνουμε μόνο τα πεδία που επιτρέπεται να τροποποιηθούν.
        // Το fleet_id δεν περιλαμβάνεται στο PATCH.
        const requestBody = {
            name: editFleetForm.name.trim(),
            description: editFleetForm.description.trim() || null,
            base_location: {
                name: editFleetForm.base_location.name.trim(),
                address: editFleetForm.base_location.address.trim() || null,
                city: editFleetForm.base_location.city.trim() || null,
                postal_code:
                    editFleetForm.base_location.postal_code.trim() || null,
                latitude,
                longitude,
            },
        };

        setIsUpdating(true);

        try {
            const response = await fetch(
                `http://localhost:8004/api/v1/fleets/${encodeURIComponent(editingFleetId)}`,
                {
                    method: "PATCH",
                    headers: {
                        Authorization: `Bearer ${token}`,
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify(requestBody),
                }
            );

            if (!response.ok) {
                const errorBody = await response.json().catch(() => null);

                throw new Error(
                    typeof errorBody?.detail === "string"
                        ? errorBody.detail
                        : `Failed to update fleet: ${response.status}`
                );
            }

            const updatedFleet: Fleet = await response.json();

            // Αντικαθιστούμε το Fleet στη λίστα χωρίς νέο GET.
            setFleets((previousFleets) =>
                previousFleets.map((fleet) =>
                    fleet.fleet_id === editingFleetId
                        ? updatedFleet
                        : fleet
                )
            );

            setEditingFleetId(null);
        } catch (requestError) {
            setEditError(
                requestError instanceof Error
                    ? requestError.message
                    : "Failed to update fleet."
            );
        } finally {
            setIsUpdating(false);
        }
    }
    async function deleteFleet(fleet: Fleet) {
        if (!token || !isAdmin || deletingFleetId !== null) {
            return;
        }

        // Ζητάμε επιβεβαίωση πριν από μια μη αναστρέψιμη ενέργεια.
        const confirmed = window.confirm(
            `Are you sure you want to permanently delete fleet "${fleet.name}" (${fleet.fleet_id})?`
        );

        if (!confirmed) {
            return;
        }

        setDeleteError("");
        setDeleteSuccess("");
        setDeletingFleetId(fleet.fleet_id);

        try {
            // Το Backend ελέγχει αν υπάρχουν συνδεδεμένοι
            // Fleet Managers, Drivers ή Vehicles.
            const response = await fetch(
                `http://localhost:8004/api/v1/fleets/${encodeURIComponent(fleet.fleet_id)}`,
                {
                    method: "DELETE",
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                }
            );

            if (!response.ok) {
                const errorBody = await response.json().catch(() => null);

                // Το 409 σημαίνει ότι το Fleet έχει ενεργές
                // συσχετίσεις που εμποδίζουν τη διαγραφή.
                if (response.status === 409) {
                    throw new Error(
                        typeof errorBody?.detail === "string"
                            ? errorBody.detail
                            : "Fleet cannot be deleted while linked records exist."
                    );
                }

                throw new Error(
                    typeof errorBody?.detail === "string"
                        ? errorBody.detail
                        : `Failed to delete fleet: ${response.status}`
                );
            }

            // Αφαιρούμε το Fleet από τη λίστα μόνο αφού
            // επιβεβαιωθεί η επιτυχία από το Backend.
            setFleets((previousFleets) =>
                previousFleets.filter(
                    (existingFleet) =>
                        existingFleet.fleet_id !== fleet.fleet_id
                )
            );

            // Κλείνουμε τη φόρμα Edit αν αφορά το Fleet
            // που μόλις διαγράφηκε.
            if (editingFleetId === fleet.fleet_id) {
                setEditingFleetId(null);
            }
            if (viewFleetId === fleet.fleet_id) setViewFleetId(null);

            setDeleteSuccess(
                `Fleet "${fleet.name}" deleted successfully.`
            );
        } catch (requestError) {
            setDeleteError(
                requestError instanceof Error
                    ? requestError.message
                    : "Failed to delete fleet."
            );
        } finally {
            setDeletingFleetId(null);
        }
    }
    // Δημιουργεί νέο Fleet Manager μέσω του API Gateway.
    // Το Backend αναλαμβάνει τη δημιουργία Keycloak user και business profile.
    async function createFleetManager( event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();

        if (!token || isCreatingManager) return;

        setIsCreatingManager(true);
        setCreateManagerError("");
        setCreateManagerSuccess("");

        try {
            // Μετατρέπουμε τα κενά προαιρετικά πεδία σε null.
            const payload = {
                username: fleetManagerForm.username.trim(),
                manager_id: fleetManagerForm.manager_id.trim(),
                first_name: fleetManagerForm.first_name.trim(),
                last_name: fleetManagerForm.last_name.trim(),
                email: fleetManagerForm.email.trim(),
                fleet_id: fleetManagerForm.fleet_id,
                department_id: fleetManagerForm.department_id.trim() || null,
                date_of_birth: fleetManagerForm.date_of_birth || null,
                identity_card_number:
                    fleetManagerForm.identity_card_number.trim() || null,
                tax_id: fleetManagerForm.tax_id.trim() || null,
                phone_number: fleetManagerForm.phone_number.trim() || null,
                hire_date: fleetManagerForm.hire_date || null,
            };

            const response = await fetch(
                "http://localhost:8004/api/v1/admin/fleet-managers",
                {
                    method: "POST",
                    headers: {
                        Authorization: `Bearer ${token}`,
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify(payload),
                }
            );

            const result = await response.json();

            if (!response.ok) {
                const detail = result.detail;

                // Το FastAPI επιστρέφει τα σφάλματα επικύρωσης
                // ως πίνακα με το πεδίο και την αιτία του σφάλματος.
                if (Array.isArray(detail)) {
                    const validationErrors = detail.map((error) => {
                        const field = Array.isArray(error.loc)
                            ? error.loc.join(".")
                            : "unknown";

                        return `${field}: ${error.msg}`;
                    });

                    throw new Error(validationErrors.join(" | "));
                }

                throw new Error(
                    typeof detail === "string"
                        ? detail
                        : `Failed to create fleet manager: ${response.status}`
                );
            }

            // Προσθέτουμε το νέο profile στη λίστα χωρίς νέο GET request,
            // εφόσον η απάντηση περιέχει το Fleet Manager Profile.
            if (result.manager_id) {
                setFleetManagers((previous) => [...previous, result]);
            }

            // Καθαρίζουμε τη φόρμα μόνο μετά από επιτυχημένη δημιουργία.
            setFleetManagerForm({ ...emptyFleetManagerForm });
            setCreateManagerSuccess("Fleet Manager created successfully.");
        } catch (error) {
            setCreateManagerError(
                error instanceof Error
                    ? error.message
                    : "Could not create fleet manager."
            );
        } finally {
            setIsCreatingManager(false);
        }
    }
    // Ενημερώνει τα στοιχεία του Fleet Manager μέσω του API Gateway.
    function startEditingFleetManager(manager: FleetManager) {
        setEditingManagerId(manager.manager_id);

        setEditFleetManagerForm({
            ...emptyFleetManagerForm,
            manager_id: manager.manager_id,
            first_name: manager.first_name,
            last_name: manager.last_name,
            date_of_birth: manager.date_of_birth ?? "",
            identity_card_number: manager.identity_card_number ?? "",
            tax_id: manager.tax_id ?? "",
            phone_number: manager.phone_number ?? "",
            email: manager.email ?? "",
            fleet_id: manager.fleet_id ?? "",
            department_id: manager.department_id ?? "",
            hire_date: manager.hire_date ?? "",
        });

        setEditManagerError("");
    }
    async function updateFleetManager(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();

        if (!token || !editingManagerId || isUpdatingManager) return;

        setIsUpdatingManager(true);
        setEditManagerError("");

        try {
                        // Το Unassigned αποστέλλεται ως null, ώστε να αφαιρεθεί η συσχέτιση.
            let fleetId: string | null = null;

            if (editFleetManagerForm.fleet_id.trim() !== "") {
                fleetId = editFleetManagerForm.fleet_id.trim();
            }
            // Στέλνουμε μόνο τα πεδία που επιτρέπεται να επεξεργαστεί ο Admin.
            const payload = {
                first_name: editFleetManagerForm.first_name.trim(),
                last_name: editFleetManagerForm.last_name.trim(),
                date_of_birth: editFleetManagerForm.date_of_birth || null,
                identity_card_number: editFleetManagerForm.identity_card_number.trim() || null,
                tax_id: editFleetManagerForm.tax_id.trim() || null,
                phone_number: editFleetManagerForm.phone_number.trim() || null,
                email: editFleetManagerForm.email.trim(),
                fleet_id: fleetId,
                hire_date: editFleetManagerForm.hire_date || null,
            };

            const response = await fetch(
                `http://localhost:8004/api/v1/admin/fleet-managers/${encodeURIComponent(editingManagerId)}`,
                {
                    method: "PATCH",
                    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", },
                    body: JSON.stringify(payload),
                }
            );

            const result = await response.json();

            if (!response.ok) {
                throw new Error(
                    typeof result.detail === "string" ? result.detail : `Failed to update fleet manager: ${response.status}`
                );
            }

            // Ανανεώνουμε τα στοιχεία του Manager στη λίστα.
            setFleetManagers((previous) =>
                previous.map((manager) =>
                    manager.manager_id === editingManagerId ? result : manager
                )
            );

            setEditingManagerId(null);

        } catch (error) {
            setEditManagerError(
                error instanceof Error ? error.message : "Could not update fleet manager."
            );
        } finally {
            setIsUpdatingManager(false);
        }
    }
    // Απενεργοποιεί τον Fleet Manager μέσω του API Gateway.
    // Το Backend αναλαμβάνει την ενημέρωση του Fleet API και του Keycloak.
    async function deactivateFleetManager(manager: FleetManager) {
        setDeactivateManagerError("");
        setDeactivateManagerSuccess("");
        setActivateManagerError("");
        setActivateManagerSuccess("");
        setDeleteManagerError("")
        setDeleteManagerSuccess("")
        if (!token || deactivatingManagerId) return;

        if (!window.confirm(`Deactivate Fleet Manager ${manager.manager_id}?`)) return;

        setDeactivatingManagerId(manager.manager_id);
        setDeactivateManagerError("");
        setDeactivateManagerSuccess("");

        try {
            const response = await fetch(
                `http://localhost:8004/api/v1/admin/fleet-managers/${encodeURIComponent(manager.manager_id)}/deactivate`,
                {
                    method: "POST", headers: { Authorization: `Bearer ${token}`, },
                }
            );

            const result = await response.json();

            if (!response.ok) {
                throw new Error(
                    typeof result.detail === "string" ? result.detail : `Failed to deactivate Fleet Manager: ${response.status}` );
            }

            // Ενημερώνουμε τη λίστα μόνο μετά από επιτυχημένη απάντηση.
            setFleetManagers((previous) =>
                previous.map((item) =>
                    item.manager_id === manager.manager_id ? result : item
                )
            );

            setDeactivateManagerSuccess("Fleet Manager deactivated successfully.");

        } catch (error) {
            setDeactivateManagerError(
                error instanceof Error ? error.message : "Could not deactivate Fleet Manager.");
        } finally {
            setDeactivatingManagerId(null);
        }
    }
    // Ενεργοποιεί ξανά τον Fleet Manager μέσω του API Gateway.
    // Το Backend αναλαμβάνει την ενημέρωση του Fleet API και του Keycloak.
    async function activateFleetManager(manager: FleetManager) {
        setDeactivateManagerError("");
        setDeactivateManagerSuccess("");
        setActivateManagerError("");
        setActivateManagerSuccess("");
        setDeleteManagerError("")
        setDeleteManagerSuccess("")
        if (!token || activatingManagerId) return;

        if (!window.confirm(`Activate Fleet Manager ${manager.manager_id}?`)) return;

        setActivatingManagerId(manager.manager_id);
        setActivateManagerError("");
        setActivateManagerSuccess("");

        try {
            const response = await fetch(
                `http://localhost:8004/api/v1/admin/fleet-managers/${encodeURIComponent(manager.manager_id)}/activate`,
                {
                    method: "POST",
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                }
            );

            const result = await response.json();

            if (!response.ok) {
                throw new Error(
                    typeof result.detail === "string"
                        ? result.detail
                        : `Failed to activate Fleet Manager: ${response.status}`
                );
            }

            // Ενημερώνουμε τη λίστα με τα νέα δεδομένα του Fleet Manager.
            setFleetManagers((previous) =>
                previous.map((item) =>
                    item.manager_id === manager.manager_id ? result : item
                )
            );

            setActivateManagerSuccess("Fleet Manager activated successfully.");

        } catch (error) {
            setActivateManagerError(
                error instanceof Error
                    ? error.message
                    : "Could not activate Fleet Manager."
            );
        } finally {
            setActivatingManagerId(null);
        }
    }
    // Διαγράφει οριστικά τον Fleet Manager μέσω του API Gateway.
    // Το Backend αναλαμβάνει τη διαγραφή από το Fleet API και το Keycloak.
    async function deleteFleetManager(manager: FleetManager) {
        setDeactivateManagerError("");
        setDeactivateManagerSuccess("");
        setActivateManagerError("");
        setActivateManagerSuccess("");
        setDeleteManagerError("")
        setDeleteManagerSuccess("")
        if (!token || deletingManagerId) return;

        // Το Backend επιτρέπει Hard Delete μόνο για INACTIVE Fleet Managers.
        if (manager.status !== "INACTIVE") return;

        if (!window.confirm(`Permanently delete Fleet Manager ${manager.manager_id}? This action cannot be undone.`)) return;

        setDeletingManagerId(manager.manager_id);
        setDeleteManagerError("");
        setDeleteManagerSuccess("");

        try {
            const response = await fetch(
                `http://localhost:8004/api/v1/admin/fleet-managers/${encodeURIComponent(manager.manager_id)}`,
                {
                    method: "DELETE",
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                }
            );

            // Διαβάζουμε την απάντηση χωρίς να υποθέτουμε ότι περιέχει πάντα JSON.
            const result = await response.json().catch(() => null);

            if (!response.ok) {
                throw new Error(
                    typeof result?.detail === "string"
                        ? result.detail
                        : `Failed to delete Fleet Manager: ${response.status}`
                );
            }

            // Αφαιρούμε τον Fleet Manager μόνο μετά από επιτυχημένη διαγραφή.
            setFleetManagers((previous) =>
                previous.filter((item) => item.manager_id !== manager.manager_id)
            );

            // Κλείνουμε τυχόν ανοιχτά στοιχεία του διαγραμμένου Fleet Manager.
            setViewManagerId((previous) =>
                previous === manager.manager_id ? null : previous
            );

            setEditingManagerId((previous) =>
                previous === manager.manager_id ? null : previous
            );

            setDeleteManagerSuccess("Fleet Manager deleted successfully.");

        } catch (error) {
            setDeleteManagerError(
                error instanceof Error
                    ? error.message
                    : "Could not delete Fleet Manager."
            );
        } finally {
            setDeletingManagerId(null);
        }
    }
    function show_fleet_managers(){
        if (isLoadingManagers) return <p>Loading fleet managers...</p>;
        if (managersError) return <p role="alert">{managersError}</p>;
        if (fleetManagers.length === 0) return <p>No fleet managers available.</p>;
        return (
            <table align={"center"}>
                                <thead align={"left"}>
                                    <tr>
                                        <th>Manager ID</th>
                                        <th>Name</th>
                                        <th>Email</th>
                                        <th>Fleet</th>
                                        <th>Status</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>

                                <tbody align={"left"}>
                                    {fleetManagers.map((manager) => (
                                        <tr key={manager.manager_id}>
                                            <td>{manager.manager_id}</td>
                                            <td>{manager.first_name} {manager.last_name}</td>
                                            <td>{manager.email ?? "—"}</td>
                                            <td>{manager.fleet_id ?? "Unassigned"}</td>
                                            <td>{manager.status === "INACTIVE" ? <p style={{ color: "red" }}>{manager.status}</p> : <p style={{ color: "green" }}>{manager.status}</p> }</td>
                                            <td>
                                                <button type="button" onClick={() => setViewManagerId(viewManagerId === manager.manager_id ? null : manager.manager_id)}> View </button>

                                            </td>
                                            <td>
                                                <button type="button" onClick={() => startEditingFleetManager(manager)} disabled={isUpdatingManager}> Edit </button>
                                            </td>
                                            <td>
                                                {manager.status === "ACTIVE" &&
                                                    (<button type="button" onClick={() => deactivateFleetManager(manager)} disabled={deactivatingManagerId !== null}>
                                                        {deactivatingManagerId === manager.manager_id ? "Deactivating..." : "Deactivate"} </button>)}
                                                {manager.status === "INACTIVE" &&
                                                    (<button type="button" onClick={() => activateFleetManager(manager)} disabled={activatingManagerId !== null}>
                                                        {activatingManagerId === manager.manager_id ? "Activating..." : "Activate"} </button>)}
                                            </td>
                                            <td>
                                                {manager.status === "INACTIVE" && (
                                                    <button type="button" onClick={() => deleteFleetManager(manager)} disabled={deletingManagerId !== null}>
                                                        {deletingManagerId === manager.manager_id ? "Deleting..." : "Delete"} </button>
                                                )}
                                            </td>

                                        </tr>
                                    ))}
                                    <tr>

                                    </tr>
                                </tbody>
                            </table>
        );

    }
    // Εμφανίζουμε τη φόρμα επεξεργασίας μόνο όταν
    // ο Admin έχει επιλέξει έναν Fleet Manager.
    function edit_fleet_manager_details(){
        if(editingManagerId)
            return (
                        <form onSubmit={updateFleetManager}>
                            <h3>Edit Fleet Manager: {editingManagerId}</h3>

                            {
                                (
                                    [
                                        ["first_name", "First Name"],
                                        ["last_name", "Last Name"],
                                        ["email", "Email"],
                                        ["phone_number", "Phone Number"],
                                        ["date_of_birth", "Date of Birth"],
                                        ["identity_card_number", "Identity Card Number"],
                                        ["tax_id", "Tax ID"],
                                        ["hire_date", "Hire Date"],
                                    ] as const
                                ).map(([field, label]) => (
                                    <div key={field}>
                                        <label htmlFor={`edit-manager-${field}`}>{label}</label>
                                        <input
                                            id={`edit-manager-${field}`}
                                            type={field === "email" ? "email" : field === "date_of_birth" || field === "hire_date" ? "date" : "text"}
                                            value={editFleetManagerForm[field]}
                                            onChange={(event) =>
                                                setEditFleetManagerForm({...editFleetManagerForm, [field]: event.target.value,})
                                            }
                                        />
                                    </div>
                                ))
                            }

                            <div>
                                <label htmlFor="edit-manager-fleet">Fleet</label>
                                <select id="edit-manager-fleet" value={editFleetManagerForm.fleet_id}
                                        onChange={(event) =>
                                            setEditFleetManagerForm({...editFleetManagerForm, fleet_id: event.target.value,}) }>
                                    <option value="">Unassigned</option>
                                    {
                                        fleets.map((fleet) => (
                                            <option key={fleet.fleet_id} value={fleet.fleet_id}>
                                                {fleet.name} ({fleet.fleet_id})
                                            </option>
                                        ))
                                    }
                                </select>
                            </div>
                            { editManagerError && ( <p role="alert">{editManagerError}</p> ) }

                            <button type="submit" disabled={isUpdatingManager}> Save Changes </button>
                            <button type="button" disabled={isUpdatingManager} onClick={() => setEditingManagerId(null)}> Cancel </button>
                        </form>
                    )
        return (null)
    }
    // Εμφανίζουμε τα στοιχεία του Fleet Manager που επέλεξε ο Admin.
    function show_fleet_manager_details(){
        if(viewManagerId){
            const manager = fleetManagers.find((manager) => manager.manager_id === viewManagerId);
            if(manager)
                return (
                    <div>
                        <h3>Fleet Manager Details: {manager.manager_id}</h3>

                        <p>First Name: {manager.first_name}</p>
                        <p>Last Name: {manager.last_name}</p>
                        <p>Date of Birth: {manager.date_of_birth ?? "—"}</p>
                        <p>Identity Card Number: {manager.identity_card_number ?? "—"}</p>
                        <p>Tax ID: {manager.tax_id ?? "—"}</p>
                        <p>Phone Number: {manager.phone_number ?? "—"}</p>
                        <p>Email: {manager.email ?? "—"}</p>
                        <p>Fleet ID: {manager.fleet_id ?? "Unassigned"}</p>
                        <p>Hire Date: {manager.hire_date ?? "—"}</p>
                        <p>Status: {manager.status}</p>

                        <button type="button" onClick={() => setViewManagerId(null)}> Close </button>
                    </div>
                )
        }

        return (null)
    }

    function manager_error_show() {
        if (activateManagerSuccess) return <p role="status">{activateManagerSuccess}</p>;
        if (activateManagerError) return <p role="alert">{activateManagerError}</p>;
        if (deactivateManagerSuccess) return <p role="status">{deactivateManagerSuccess}</p>;
        if (deactivateManagerError) return <p role="alert">{deactivateManagerError}</p>;
        if (deleteManagerSuccess) return <p role="alert">{deleteManagerSuccess}</p>;
        if (deleteManagerError) return <p role="alert">{deleteManagerError}</p>;
        return null;
    }


    function driver_error_show() {
        if (activateDriverSuccess) return <p role="status">{activateDriverSuccess}</p>;
        if (activateDriverError) return <p role="alert">{activateDriverError}</p>;
        if (deactivateDriverSuccess) return <p role="status">{deactivateDriverSuccess}</p>;
        if (deactivateDriverError) return <p role="alert">{deactivateDriverError}</p>;
        if (deleteDriverError) return <p role="alert">{deleteDriverError}</p>;
        if (deleteDriverSuccess) return <p role="alert">{deleteDriverSuccess}</p>;
        return null;
    }
    async function createDriver(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();

        // Αποτρέπουμε την υποβολή χωρίς έγκυρο access token.
        if (!token || isCreatingDriver) return;

        setIsCreatingDriver(true);
        setCreateDriverError("");
        setCreateDriverSuccess("");

        try {
            // Μετατρέπουμε τα προαιρετικά κενά πεδία σε null,
            // σύμφωνα με το μοντέλο AdminDriverCreate του Backend.
            const payload = {
                username: driverForm.username.trim(),
                driver_id: driverForm.driver_id.trim(),
                first_name: driverForm.first_name.trim(),
                last_name: driverForm.last_name.trim(),
                email: driverForm.email.trim(),
                date_of_birth: driverForm.date_of_birth || null,
                identity_card_number:
                    driverForm.identity_card_number.trim() || null,
                tax_id: driverForm.tax_id.trim() || null,
                phone_number: driverForm.phone_number.trim() || null,
                license_number: driverForm.license_number.trim() || null,
                license_category: driverForm.license_category.trim() || null,
                license_expiry_date:
                    driverForm.license_expiry_date || null,
                hire_date: driverForm.hire_date || null,
                fleet_id: driverForm.fleet_id.trim() || null,
                department_id: driverForm.department_id.trim() || null,
            };

            // Το API Gateway αναλαμβάνει τη δημιουργία της
            // Keycloak identity και του Driver Profile.
            const response = await fetch(
                "http://localhost:8004/api/v1/admin/drivers",
                {
                    method: "POST",
                    headers: {
                        Authorization: `Bearer ${token}`,
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify(payload),
                }
            );

            const result = await response.json();

            if (!response.ok) {
                const detail = result.detail;

                // Εμφανίζουμε αναλυτικά τα σφάλματα επικύρωσης
                // που επιστρέφει το FastAPI.
                if (Array.isArray(detail)) {
                    const validationErrors = detail.map((error) => {
                        const field = Array.isArray(error.loc)
                            ? error.loc.join(".")
                            : "unknown";

                        return `${field}: ${error.msg}`;
                    });

                    throw new Error(validationErrors.join(" | "));
                }

                throw new Error(
                    typeof detail === "string"
                        ? detail
                        : `Failed to create driver: ${response.status}`
                );
            }

            // Προσθέτουμε τον Driver στη λίστα όταν η απάντηση
            // περιλαμβάνει το ολοκληρωμένο Driver Profile.
            if (result.driver_id) {
                setDrivers((previous) => [...previous, result]);
            }

            // Καθαρίζουμε τη φόρμα μόνο μετά την επιτυχία.
            setDriverForm({ ...emptyDriverForm });
            setCreateDriverSuccess("Driver created successfully.");

        } catch (error) {
            setCreateDriverError(
                error instanceof Error
                    ? error.message
                    : "Could not create driver."
            );
        } finally {
            setIsCreatingDriver(false);
        }
    }
    function show_drivers() {
        // Εμφανίζουμε μήνυμα όσο περιμένουμε τα Driver Profiles.
        if (isLoadingDrivers) return <p>Loading drivers...</p>;

        // Εμφανίζουμε τυχόν σφάλμα από το API Gateway.
        if (driversError) return <p role="alert">{driversError}</p>;

        // Ενημερώνουμε τον Admin όταν δεν υπάρχουν οδηγοί.
        if (drivers.length === 0) return <p>No drivers available.</p>;

                // Αρχικά εμφανίζουμε μήνυμα μέχρι να φτάσει θέση από το Gateway.
        // let trackingContent = <p>No position received yet.</p>;

        // if (latestPosition !== null) {
        //     trackingContent = (
        //         <>
        //             <LatestPosition position={latestPosition} />
        //             <LiveMap position={latestPosition} />
        //         </>
        //     );
        // }

        // Εμφανίζουμε τα βασικά στοιχεία όλων των Drivers.
        return (
            <div>
            <table align={"center"}>
                <thead align={"left"}>
                    <tr>
                        <th>Driver ID</th>
                        <th>Name</th>
                        {/*<th>Email</th>*/}
                        <th>Fleet</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>

                <tbody align={"left"}>
                    {drivers.map((driver) => (
                        <tr key={driver.driver_id}>
                            <td>{driver.driver_id}</td>
                            <td>{driver.first_name} {driver.last_name}</td>
                            {/*<td>{driver.email ?? "-"}</td>*/}
                            <td>{driver.fleet_id ?? "-"}</td>
                            <td >{driver.status === "INACTIVE" ? <p style={{ color: "red" }}>{driver.status}</p> : <p style={{ color: "green" }}>{driver.status}</p> }</td>
                            <td>
                                <button type="button" onClick={() => setViewDriverId(viewDriverId === driver.driver_id ? null : driver.driver_id)}> View </button>
                            </td>
                            <td>
                                <button type="button" onClick={() => startEditingDriver(driver)} disabled={isUpdatingDriver}> Edit </button>
                            </td>
                            <td>

                                {driver.status === "ACTIVE" &&
                                    (<button type="button" onClick={() => deactivateDriver(driver)} disabled={deactivatingDriverId !== null}>
                                        {deactivatingDriverId === driver.driver_id ? "Deactivating..." : "Deactivate"} </button>)}
                                {driver.status === "INACTIVE" &&
                                    (<button type="button" onClick={() => activateDriver(driver)} disabled={activatingDriverId !== null}>
                                        {activatingDriverId === driver.driver_id ? "Activating..." : "Activate"} </button>)}
                            </td>
                            <td>
                                {driver.status === "INACTIVE" &&
                                    (<button type="button" onClick={() => deleteDriver(driver)} disabled={deletingDriverId !== null}>
                                        {deletingDriverId === driver.driver_id ? "Deleting..." : "Delete"} </button>)}
                            </td>
                            <td>
                                {/*<button type="button" onClick={() => loadDriverVehicles(driver)} disabled={isLoadingDriverVehicles}>*/}
                                {/*    Vehicles*/}
                                {/*</button>*/}
                                <button type="button" onClick={() => setSelectedDriverId(driver.driver_id)} disabled={isLoadingDriverVehicles}> Vehicles </button>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
            {
                selectedDriverId && (
                <div>
                    <h3>Vehicles assigned to Driver: {selectedDriverId}</h3>
                    <button type="button" onClick={() => { setSelectedDriverId(null); setDriverVehicles([]); setDriverVehiclesError(""); }}>Close</button>
                            {isLoadingDriverVehicles && <p>Loading vehicles...</p>}

                            {driverVehiclesError && <p role="alert">{driverVehiclesError}</p>}

                            {!isLoadingDriverVehicles && !driverVehiclesError && ( driverVehicles.length === 0
                                    ? <p>No vehicles assigned to this Driver.</p>
                                    : <table align={"center"}>
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
                                            {driverVehicles.map((vehicle) => (
                                                <tr key={vehicle.id}>
                                                    <td>{vehicle.plate_number}</td>
                                                    <td>{vehicle.brand}</td>
                                                    <td>{vehicle.model}</td>
                                                    <td>{vehicle.device_imei}</td>
                                                    <td>
                                                        <button type="button" onClick={() => setSelectedTrackingVehicle(vehicle)}> Track </button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                   )}
                </div>
            )}
            {/*    {*/}
            {/*    selectedTrackingVehicle && (*/}
            {/*            <div>*/}
            {/*                <h3>GPS Tracking</h3>*/}
            {/*                <p>Vehicle: {selectedTrackingVehicle.plate_number}</p>*/}
            {/*                <p>Brand: {selectedTrackingVehicle.brand}</p>*/}
            {/*                <p>Model: {selectedTrackingVehicle.model}</p>*/}
            {/*                <p>Device IMEI: {selectedTrackingVehicle.device_imei}</p>*/}
            {/*                /!* Εμφανίζουμε τη θέση και τον υπάρχοντα χάρτη. *!/*/}
            {/*                {trackingContent}*/}

            {/*                <button type="button" onClick={() => setSelectedTrackingVehicle(null)}> Close Tracking </button>*/}
            {/*            </div>*/}
            {/*)}*/}
            </div>
        );

    }
    // Εμφανίζουμε αναλυτικά τα στοιχεία του Driver που επέλεξε ο Admin.
    function show_driver_details(){
        if(viewDriverId){
            const driver = drivers.find((driver) => driver.driver_id === viewDriverId);
            if(driver)
                return (
                    <div>
                        <h3>Driver Details: {driver.driver_id}</h3>

                        <p>First Name: {driver.first_name}</p>
                        <p>Last Name: {driver.last_name}</p>
                        <p>Date of Birth: {driver.date_of_birth ?? "—"}</p>
                        <p>Identity Card Number: {driver.identity_card_number ?? "—"}</p>
                        <p>Tax ID: {driver.tax_id ?? "—"}</p>
                        <p>Phone Number: {driver.phone_number ?? "—"}</p>
                        <p>Email: {driver.email ?? "—"}</p>
                        <p>License Number: {driver.license_number ?? "—"}</p>
                        <p>License Category: {driver.license_category ?? "—"}</p>
                        <p>License Expiry Date: {driver.license_expiry_date ?? "—"}</p>
                        <p>Hire Date: {driver.hire_date ?? "—"}</p>
                        <p>Fleet ID: {driver.fleet_id ?? "Unassigned"}</p>
                        <p>Department ID: {driver.department_id ?? "—"}</p>
                        <p>Keycloak User ID: {driver.keycloak_user_id}</p>
                        <p>Status: {driver.status}</p>

                        <button type="button" onClick={() => setViewDriverId(null)}> Close </button>
                    </div>
                )
        }

        return (null)
    }
    // Επιλέγουμε τον Driver που θέλουμε να επεξεργαστούμε
    // και συμπληρώνουμε τη φόρμα με τα υπάρχοντα στοιχεία του.
    function startEditingDriver(driver: Driver) {
        setEditingDriverId(driver.driver_id);

        setEditDriverForm({
            ...emptyDriverForm,
            driver_id: driver.driver_id,
            first_name: driver.first_name,
            last_name: driver.last_name,
            email: driver.email ?? "",
            date_of_birth: driver.date_of_birth ?? "",
            identity_card_number: driver.identity_card_number ?? "",
            tax_id: driver.tax_id ?? "",
            phone_number: driver.phone_number ?? "",
            license_number: driver.license_number ?? "",
            license_category: driver.license_category ?? "",
            license_expiry_date: driver.license_expiry_date ?? "",
            hire_date: driver.hire_date ?? "",
            fleet_id: driver.fleet_id ?? "",
            department_id: driver.department_id ?? "",
        });

        setEditDriverError("");
    }
        // Ενημερώνουμε τα στοιχεία του Driver μέσω του API Gateway.
    // Το Backend αναλαμβάνει την ενημέρωση του Driver Profile και του Keycloak.
    async function updateDriver(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();

        if (!token || !editingDriverId || isUpdatingDriver) return;

        setIsUpdatingDriver(true);
        setEditDriverError("");

        try {
            // Στέλνουμε μόνο τα πεδία που επιτρέπεται να επεξεργαστεί ο Admin.
            const payload = {
                first_name: editDriverForm.first_name.trim(),
                last_name: editDriverForm.last_name.trim(),
                email: editDriverForm.email.trim() || null,
                date_of_birth: editDriverForm.date_of_birth || null,
                identity_card_number: editDriverForm.identity_card_number.trim() || null,
                tax_id: editDriverForm.tax_id.trim() || null,
                phone_number: editDriverForm.phone_number.trim() || null,
                license_number: editDriverForm.license_number.trim() || null,
                license_category: editDriverForm.license_category.trim() || null,
                license_expiry_date: editDriverForm.license_expiry_date || null,
                hire_date: editDriverForm.hire_date || null,
                fleet_id: editDriverForm.fleet_id.trim() || null,
                department_id: editDriverForm.department_id.trim() || null,
            };

            const response = await fetch(
                `http://localhost:8004/api/v1/admin/drivers/${encodeURIComponent(editingDriverId)}`,
                {
                    method: "PATCH",
                    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", },
                    body: JSON.stringify(payload),
                }
            );

            const result = await response.json().catch(() => null);

            if (!response.ok) {
                // Εμφανίζουμε αναλυτικά τα σφάλματα επικύρωσης
                // που επιστρέφει το FastAPI για το PATCH Driver.
                console.error("Driver PATCH validation error:", result);

                const detail = result?.detail;

                if (Array.isArray(detail)) {
                    const validationErrors = detail.map((error) => {
                        const field = Array.isArray(error.loc)
                            ? error.loc.join(".")
                            : "unknown";

                        return `${field}: ${error.msg}`;
                    });

                    throw new Error(validationErrors.join(" | "));
                }

                throw new Error(
                    typeof detail === "string"
                        ? detail
                        : `Failed to update Driver: ${response.status}`
                );
            }

            // Ανανεώνουμε τον Driver στη λίστα μετά την επιτυχημένη ενημέρωση.
            setDrivers((previous) =>
                previous.map((driver) =>
                    driver.driver_id === editingDriverId ? result : driver
                )
            );
            // Η αλλαγή Fleet του Driver μπορεί να αποδεσμεύσει οχήματα.
            setVehiclesRefreshNumber((previous) => previous + 1);

            setEditingDriverId(null);

        } catch (error) {
            setEditDriverError(
                error instanceof Error ? error.message : "Could not update Driver."
            );
        } finally {
            setIsUpdatingDriver(false);
        }
    }

    // Εμφανίζουμε τη φόρμα επεξεργασίας μόνο όταν
    // ο Admin έχει επιλέξει έναν Driver.
    function edit_driver_details(){
        if(editingDriverId)
            return (
                        <form onSubmit={updateDriver}>
                            <h3>Edit Driver: {editingDriverId}</h3>

                            {
                                (
                                    [
                                        ["first_name", "First Name"],
                                        ["last_name", "Last Name"],
                                        ["email", "Email"],
                                        ["phone_number", "Phone Number"],
                                        ["date_of_birth", "Date of Birth"],
                                        ["identity_card_number", "Identity Card Number"],
                                        ["tax_id", "Tax ID"],
                                        ["license_number", "License Number"],
                                        ["license_category", "License Category"],
                                        ["license_expiry_date", "License Expiry Date"],
                                        ["hire_date", "Hire Date"],
                                    ] as const
                                ).map(([field, label]) => (
                                    <div key={field}>
                                        <label htmlFor={`edit-driver-${field}`}>{label}</label>
                                        <input
                                            id={`edit-driver-${field}`}
                                            type={field === "email" ? "email" : field === "date_of_birth" || field === "license_expiry_date" || field === "hire_date" ? "date" : "text"}
                                            value={editDriverForm[field]}
                                            onChange={(event) =>
                                                setEditDriverForm({...editDriverForm, [field]: event.target.value,})
                                            }
                                        />
                                    </div>
                                ))
                            }

                            <div>
                                <label htmlFor="edit-driver-fleet">Fleet</label>
                                <select id="edit-driver-fleet" value={editDriverForm.fleet_id}
                                        onChange={(event) =>
                                            setEditDriverForm({...editDriverForm, fleet_id: event.target.value,}) }>
                                    <option value="">Unassigned</option>
                                    {
                                        fleets.map((fleet) => (
                                            <option key={fleet.fleet_id} value={fleet.fleet_id}>
                                                {fleet.name} ({fleet.fleet_id})
                                            </option>
                                        ))
                                    }
                                </select>
                            </div>

                            <div>
                                <label htmlFor="edit-driver-department">Department ID</label>
                                <input id="edit-driver-department" type="text" value={editDriverForm.department_id}
                                       onChange={(event) =>
                                           setEditDriverForm({...editDriverForm, department_id: event.target.value,}) } />
                            </div>

                            { editDriverError && ( <p role="alert">{editDriverError}</p> ) }

                            <button type="submit" disabled={isUpdatingDriver}> Save Changes </button>
                            <button type="button" disabled={isUpdatingDriver} onClick={() => setEditingDriverId(null)}> Cancel </button>
                        </form>
                    )
        return (null)
    }
        // Απενεργοποιεί τον Driver μέσω του API Gateway.
    // Το Backend αναλαμβάνει την ενημέρωση του Fleet API και του Keycloak.
    async function deactivateDriver(driver: Driver) {
        setDeactivateDriverError("");
        setDeactivateDriverSuccess("");
        setActivateDriverError("");
        setActivateDriverSuccess("");
        setDeleteDriverError("")
        setDeleteDriverSuccess("")
        if (!token || deactivatingDriverId) return;

        if (!window.confirm(`Deactivate Driver ${driver.driver_id}?`)) return;

        setDeactivatingDriverId(driver.driver_id);
        setDeactivateDriverError("");
        setDeactivateDriverSuccess("");

        try {
            const response = await fetch(
                `http://localhost:8004/api/v1/admin/drivers/${encodeURIComponent(driver.driver_id)}/deactivate`,
                {
                    method: "POST",
                    headers: { Authorization: `Bearer ${token}`, },
                }
            );

            const result = await response.json().catch(() => null);

            if (!response.ok) {
                throw new Error(
                    typeof result?.detail === "string" ? result.detail : `Failed to deactivate Driver: ${response.status}`
                );
            }

            // Ενημερώνουμε τη λίστα μόνο μετά από επιτυχημένη απάντηση.
            setDrivers((previous) =>
                previous.map((item) =>
                    item.driver_id === driver.driver_id ? result : item
                )
            );

            // Η απενεργοποίηση αποδεσμεύει τα οχήματα του Driver.
            setVehiclesRefreshNumber((previous) => previous + 1);
            setDeactivateDriverSuccess("Driver deactivated successfully.");
               // Κλείνουμε τη λίστα αν αφορά τον Driver που απενεργοποιήθηκε.
            if (selectedDriverId === driver.driver_id) {
                setSelectedDriverId(null);
                setDriverVehicles([]);
                setDriverVehiclesError("");
            }

        } catch (error) {
            setDeactivateDriverError(
                error instanceof Error ? error.message : "Could not deactivate Driver."
            );
        } finally {
            setDeactivatingDriverId(null);
        }
    }

        // Ενεργοποιεί ξανά έναν ανενεργό Driver μέσω του API Gateway.
    // Το Backend αναλαμβάνει την ενημέρωση του Fleet API και του Keycloak.
    async function activateDriver(driver: Driver) {
        setDeactivateDriverError("");
        setDeactivateDriverSuccess("");
        setActivateDriverError("");
        setActivateDriverSuccess("");
        setDeleteDriverError("")
        setDeleteDriverSuccess("")
        if (!token || activatingDriverId) return;

        if (!window.confirm(`Activate Driver ${driver.driver_id}?`)) return;

        setActivatingDriverId(driver.driver_id);
        setActivateDriverError("");
        setActivateDriverSuccess("");

        try {
            const response = await fetch(
                `http://localhost:8004/api/v1/admin/drivers/${encodeURIComponent(driver.driver_id)}/activate`,
                {
                    method: "POST",
                    headers: { Authorization: `Bearer ${token}`, },
                }
            );

            const result = await response.json().catch(() => null);

            if (!response.ok) {
                throw new Error(
                    typeof result?.detail === "string" ? result.detail : `Failed to activate Driver: ${response.status}`
                );
            }

            // Ενημερώνουμε τον Driver στον πίνακα μόνο
            // αφού το Backend επιβεβαιώσει την ενεργοποίηση.
            setDrivers((previous) =>
                previous.map((item) =>
                    item.driver_id === driver.driver_id ? result : item
                )
            );

            setActivateDriverSuccess("Driver activated successfully.");

        } catch (error) {
            setActivateDriverError(
                error instanceof Error ? error.message : "Could not activate Driver."
            );
        } finally {
            setActivatingDriverId(null);
        }
    }

        // Διαγράφει οριστικά έναν Driver μόνο όταν είναι INACTIVE.
    // Το Backend διαχειρίζεται το Fleet API και το Keycloak.
    async function deleteDriver(driver: Driver) {
        setDeactivateDriverError("");
        setDeactivateDriverSuccess("");
        setActivateDriverError("");
        setActivateDriverSuccess("");
        setDeleteDriverError("")
        setDeleteDriverSuccess("")
        if (!token || deletingDriverId || driver.status !== "INACTIVE") return;

        if (!window.confirm(`Permanently delete Driver ${driver.driver_id}?`)) return;

        setDeletingDriverId(driver.driver_id);
        setDeleteDriverError("");
        setDeleteDriverSuccess("");

        try {
            const response = await fetch(
                `http://localhost:8004/api/v1/admin/drivers/${encodeURIComponent(driver.driver_id)}`,
                {
                    method: "DELETE",
                    headers: { Authorization: `Bearer ${token}`, },
                }
            );

            const result = await response.json().catch(() => null);

            if (!response.ok) {
                throw new Error(
                    typeof result?.detail === "string" ? result.detail : `Failed to delete Driver: ${response.status}`
                );
            }

            // Αφαιρούμε τον Driver από τον πίνακα μόνο μετά την επιτυχημένη διαγραφή.
            setDrivers((previous) =>
                previous.filter((item) => item.driver_id !== driver.driver_id)
            );

            setDeleteDriverSuccess("Driver deleted successfully.");

        } catch (error) {
            setDeleteDriverError(
                error instanceof Error ? error.message : "Could not delete Driver."
            );
        } finally {
            setDeletingDriverId(null);
        }
    }

    //     // Ανακτά τα οχήματα που είναι ανατεθειμένα στον επιλεγμένο Driver.
    // async function loadDriverVehicles(driver: Driver) {
    //
    //     if (!token) return;
    //
    //     // Αποθηκεύουμε τον Driver και καθαρίζουμε τα προηγούμενα αποτελέσματα.
    //     setSelectedDriverId(driver.driver_id);
    //     setDriverVehicles([]);
    //     setDriverVehiclesError("");
    //     setIsLoadingDriverVehicles(true);
    //
    //     try {
    //         const response = await fetch(
    //             `http://localhost:8004/api/v1/admin/drivers/${encodeURIComponent(driver.driver_id)}/vehicles`,
    //             {
    //                 method: "GET",
    //                 headers: { Authorization: `Bearer ${token}` },
    //             }
    //         );
    //
    //         const result = await response.json().catch(() => null);
    //
    //         if (!response.ok) {
    //             throw new Error(
    //                 typeof result?.detail === "string"
    //                     ? result.detail
    //                     : `Failed to load Driver vehicles: ${response.status}`
    //             );
    //         }
    //
    //         // Ελέγχουμε ότι το API επέστρεψε πίνακα οχημάτων.
    //         if (!Array.isArray(result)) {
    //             throw new Error("Invalid Driver vehicles response.");
    //         }
    //
    //         setDriverVehicles(result as Vehicle[]);
    //
    //     } catch (error) {
    //         setDriverVehiclesError(
    //             error instanceof Error ? error.message : "Could not load Driver vehicles."
    //         );
    //     } finally {
    //         setIsLoadingDriverVehicles(false);
    //     }
    // }

        // Δημιουργούμε το όχημα μέσω του API Gateway.
    async function createVehicle(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();

        if (!token || !isAdmin || isCreatingVehicle) {
            return;
        }

        setCreateVehicleError("");
        setCreateVehicleSuccess("");

        const plateNumber = vehicleForm.plate_number.trim();
        const deviceImei = vehicleForm.device_imei.trim();
        const yearText = vehicleForm.year.trim();

        if (plateNumber === "" || deviceImei === "") {
            setCreateVehicleError("Please complete Plate Number and Device IMEI.");
            return;
        }

        // Το κενό έτος παραμένει null.
        // Αν συμπληρωθεί, πρέπει να είναι ακέραιος αριθμός.
        let year: number | null = null;

        if (yearText !== "") {
            year = Number(yearText);

            if (!Number.isInteger(year)) {
                setCreateVehicleError("Year must be a whole number.");
                return;
            }
        }

        // Τα προαιρετικά πεδία ξεκινούν ως null
        // και συμπληρώνονται μόνο αν έχουν τιμή.
        const payload: {
            plate_number: string;
            device_imei: string;
            brand: string | null;
            model: string | null;
            year: number | null;
            driver_id: string | null;
            fleet_id: string | null;
        } = {
            plate_number: plateNumber,
            device_imei: deviceImei,
            brand: null,
            model: null,
            year,
            driver_id: null,
            fleet_id: null,
        };

        if (vehicleForm.brand.trim() !== "") {
            payload.brand = vehicleForm.brand.trim();
        }

        if (vehicleForm.model.trim() !== "") {
            payload.model = vehicleForm.model.trim();
        }

        if (vehicleForm.driver_id.trim() !== "") {
            payload.driver_id = vehicleForm.driver_id.trim();
        }

        if (vehicleForm.fleet_id.trim() !== "") {
            payload.fleet_id = vehicleForm.fleet_id.trim();
        }

        setIsCreatingVehicle(true);

        try {
            const response = await fetch(
                "http://localhost:8004/api/v1/vehicles",
                {
                    method: "POST",
                    headers: {
                        Authorization: `Bearer ${token}`,
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify(payload),
                }
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

            // Ενημερώνουμε τη λίστα με το όχημα που επέστρεψε το backend.
            setVehicles((previous) => [...previous, createdVehicle]);
            setVehicleForm({ ...emptyVehicleForm });
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

        // Συμπληρώνουμε τη φόρμα Edit με τα υπάρχοντα στοιχεία του οχήματος.
    function startEditingVehicle(vehicle: Vehicle) {
        const form: VehicleCreateForm = {
            plate_number: vehicle.plate_number,
            brand: "",
            model: "",
            year: "",
            device_imei: vehicle.device_imei,
            driver_id: "",
            fleet_id: "",
        };

        // Τα προαιρετικά πεδία γίνονται κενό κείμενο όταν είναι null.
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

        if (vehicle.fleet_id !== null) {
            form.fleet_id = vehicle.fleet_id;
        }

        setEditingVehicleId(vehicle.id);
        setEditVehicleForm(form);
        setEditVehicleError("");
    }

        // Ενημερώνουμε το όχημα μέσω του API Gateway.
    async function updateVehicle(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();

        if (!token || !isAdmin || editingVehicleId === null || isUpdatingVehicle) {
            return;
        }

        setEditVehicleError("");

        const plateNumber = editVehicleForm.plate_number.trim();
        const deviceImei = editVehicleForm.device_imei.trim();
        const yearText = editVehicleForm.year.trim();

        if (plateNumber === "" || deviceImei === "") {
            setEditVehicleError("Please complete Plate Number and Device IMEI.");
            return;
        }

        // Το έτος είναι προαιρετικό, αλλά πρέπει να είναι ακέραιο αν συμπληρωθεί.
        let year: number | null = null;

        if (yearText !== "") {
            year = Number(yearText);

            if (!Number.isInteger(year)) {
                setEditVehicleError("Year must be a whole number.");
                return;
            }
        }

        // Στέλνουμε μόνο τα επεξεργάσιμα πεδία.
        // Το id και το status δεν αλλάζουν μέσω αυτής της φόρμας.
        const payload: {
            plate_number: string;
            device_imei: string;
            brand: string | null;
            model: string | null;
            year: number | null;
            driver_id: string | null;
            fleet_id: string | null;
        } = {
            plate_number: plateNumber,
            device_imei: deviceImei,
            brand: null,
            model: null,
            year,
            driver_id: null,
            fleet_id: null,
        };

        if (editVehicleForm.brand.trim() !== "") {
            payload.brand = editVehicleForm.brand.trim();
        }

        if (editVehicleForm.model.trim() !== "") {
            payload.model = editVehicleForm.model.trim();
        }

        if (editVehicleForm.driver_id.trim() !== "") {
            payload.driver_id = editVehicleForm.driver_id.trim();
        }

        if (editVehicleForm.fleet_id.trim() !== "") {
            payload.fleet_id = editVehicleForm.fleet_id.trim();
        }

        setIsUpdatingVehicle(true);

        try {
            const response = await fetch(
                `http://localhost:8004/api/v1/vehicles/${encodeURIComponent(editingVehicleId)}`,
                {
                    method: "PATCH",
                    headers: {
                        Authorization: `Bearer ${token}`,
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify(payload),
                }
            );

            const result = await response.json();

            if (!response.ok) {
                let errorMessage = `Failed to update vehicle: ${response.status}`;

                if (result !== null && typeof result.detail === "string") {
                    errorMessage = result.detail;
                } else if (result !== null && Array.isArray(result.detail)) {
                    // Εμφανίζουμε αναλυτικά τα σφάλματα επικύρωσης του backend.
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

            const updatedVehicle: Vehicle = result;

            // Χρησιμοποιούμε τα τελικά δεδομένα που επέστρεψε το backend.
            setVehicles((previous) =>
                previous.map((vehicle) => {
                    if (vehicle.id === updatedVehicle.id) {
                        return updatedVehicle;
                    }

                    return vehicle;
                })
            );

            // Η ενημέρωση μπορεί να αλλάξει τις αναθέσεις.
            // Καθαρίζουμε την ανοιχτή λίστα Driver vehicles
            // ώστε να ανακτηθεί ξανά με τα σωστά δεδομένα.
            setSelectedDriverId(null);
            setDriverVehicles([]);
            setDriverVehiclesError("");

            // Σταματάμε το tracking αν επεξεργαστήκαμε το επιλεγμένο όχημα,
            // επειδή μπορεί να έχει αλλάξει το IMEI του.
            if (selectedTrackingVehicle !== null) {
                if (selectedTrackingVehicle.id === updatedVehicle.id) {
                    setSelectedTrackingVehicle(null);
                }
            }

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

        // Απενεργοποιούμε το όχημα μέσω του API Gateway.
    // Το backend αποδεσμεύει τον Driver και διατηρεί το Fleet.
    async function deactivateVehicle(vehicle: Vehicle) {
        setDeleteVehicleError("");
        setDeleteVehicleSuccess("");
        setActivateVehicleError("");
        setActivateVehicleSuccess("");
        setDeactivateVehicleError("");
        setDeactivateVehicleSuccess("");


        if (!token || !isAdmin || deactivatingVehicleId !== null) {
            return;
        }

        if (vehicle.status !== "ACTIVE") {
            return;
        }

        const confirmed = window.confirm(
            `Deactivate vehicle ${vehicle.plate_number}?`
        );

        if (!confirmed) {
            return;
        }

        setDeactivatingVehicleId(vehicle.id);
        setDeactivateVehicleError("");
        setDeactivateVehicleSuccess("");

        try {
            const response = await fetch(
                `http://localhost:8004/api/v1/vehicles/${encodeURIComponent(vehicle.id)}/deactivate`,
                {
                    method: "POST",
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                }
            );

            const result = await response.json();

            if (!response.ok) {
                let errorMessage = `Failed to deactivate vehicle: ${response.status}`;

                if (result !== null && typeof result.detail === "string") {
                    errorMessage = result.detail;
                }

                throw new Error(errorMessage);
            }

            const updatedVehicle: Vehicle = result;

            // Ενημερώνουμε τη λίστα με τα τελικά δεδομένα του backend.
            setVehicles((previous) =>
                previous.map((item) => {
                    if (item.id === updatedVehicle.id) {
                        return updatedVehicle;
                    }

                    return item;
                })
            );

            // Καθαρίζουμε την προηγούμενη λίστα Driver vehicles,
            // επειδή η απενεργοποίηση λύνει την ανάθεση.
            setSelectedDriverId(null);
            setDriverVehicles([]);
            setDriverVehiclesError("");

            // Σταματάμε την παρακολούθηση του συγκεκριμένου οχήματος.
            if (selectedTrackingVehicle !== null) {
                if (selectedTrackingVehicle.id === updatedVehicle.id) {
                    setSelectedTrackingVehicle(null);
                }
            }

            // Κλείνουμε το Edit ώστε να μη μείνει η παλιά ανάθεση στη φόρμα.
            if (editingVehicleId === updatedVehicle.id) {
                setEditingVehicleId(null);
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

        // Ενεργοποιούμε το όχημα χωρίς να επαναφέρουμε την προηγούμενη ανάθεση Driver.
    async function activateVehicle(vehicle: Vehicle) {
        setDeleteVehicleError("");
        setDeleteVehicleSuccess("");
        setActivateVehicleError("");
        setActivateVehicleSuccess("");
        setDeactivateVehicleError("");
        setDeactivateVehicleSuccess("");


        if (!token || !isAdmin || activatingVehicleId !== null) return;
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

            const updatedVehicle: Vehicle = result;

            // Ενημερώνουμε τη λίστα με την κατάσταση που επέστρεψε το backend.
            setVehicles((previous) =>
                previous.map((item) => {
                    if (item.id === updatedVehicle.id) return updatedVehicle;
                    return item;
                })
            );

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

        // Διαγράφουμε οριστικά μόνο INACTIVE όχημα.
    // Το backend ελέγχει επίσης αν επιτρέπεται η διαγραφή.
    async function deleteVehicle(vehicle: Vehicle) {
        setDeleteVehicleError("");
        setDeleteVehicleSuccess("");
        setActivateVehicleError("");
        setActivateVehicleSuccess("");
        setDeactivateVehicleError("");
        setDeactivateVehicleSuccess("");


        if (!token || !isAdmin || deletingVehicleId !== null) return;
        if (vehicle.status !== "INACTIVE") return;

        const confirmed = window.confirm(`Permanently delete vehicle ${vehicle.plate_number}? This action cannot be undone.`);
        if (!confirmed) return;

        setDeletingVehicleId(vehicle.id);
        setDeleteVehicleError("");
        setDeleteVehicleSuccess("");
        setActivateVehicleError("");
        setActivateVehicleSuccess("");
        setDeactivateVehicleError("");
        setDeactivateVehicleSuccess("");

        try {
            const response = await fetch(
                `http://localhost:8004/api/v1/vehicles/${encodeURIComponent(vehicle.id)}`,
                { method: "DELETE", headers: { Authorization: `Bearer ${token}`, }, }
            );

            // Η επιτυχής διαγραφή μπορεί να επιστρέψει απάντηση χωρίς JSON.
            if (!response.ok) {
                let errorMessage = `Failed to delete vehicle: ${response.status}`;

                try {
                    const result = await response.json();

                    if (result !== null && typeof result.detail === "string") {
                        errorMessage = result.detail;
                    }
                } catch {
                    // Κρατάμε το μήνυμα με τον HTTP κωδικό αν δεν υπάρχει JSON.
                }

                throw new Error(errorMessage);
            }

            // Αφαιρούμε το όχημα μόνο μετά την επιτυχημένη διαγραφή.
            setVehicles((previous) => previous.filter((item) => item.id !== vehicle.id));

            if (viewVehicleId === vehicle.id) {
                setViewVehicleId(null);
            }

            if (editingVehicleId === vehicle.id) {
                setEditingVehicleId(null);
            }

            // Αφαιρούμε το όχημα και από τυχόν ανοιχτή λίστα Driver vehicles.
            setDriverVehicles((previous) => previous.filter((item) => item.id !== vehicle.id));

            if (selectedTrackingVehicle !== null) {
                if (selectedTrackingVehicle.id === vehicle.id) {
                    setSelectedTrackingVehicle(null);
                }
            }

            setDeleteVehicleSuccess("Vehicle deleted successfully.");
        } catch (error) {
            let errorMessage = "Could not delete vehicle.";

            if (error instanceof Error) {
                errorMessage = error.message;
            }

            setDeleteVehicleError(errorMessage);
        } finally {
            setDeletingVehicleId(null);
        }
    }
        // Εμφανίζουμε όλα τα οχήματα που μπορεί να διαχειριστεί ο Admin.
    function show_vehicles() {
        if (isLoadingVehicles) {
            return <p>Loading vehicles...</p>;
        }

        if (vehiclesError !== "") {
            return <p role="alert">{vehiclesError}</p>;
        }

        if (vehicles.length === 0) {
            return <p>No vehicles available.</p>;
        }

        return (
            <table align={"center"}>
                <thead align={"left"}>
                    <tr>
                        <th>Plate Number</th>
                        <th>Brand</th>
                        <th>Model</th>
                        <th>Year</th>
                        <th>Device IMEI</th>
                        <th>Fleet</th>
                        <th>Driver</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>

                <tbody align={"left"}>
                    {vehicles.map((vehicle) => {
                        // Δίνουμε κατανοητή ένδειξη όταν δεν υπάρχει ανάθεση.
                        let fleetName = "Unassigned";
                        let driverName = "Unassigned";

                        if (vehicle.fleet_id !== null) {
                            fleetName = vehicle.fleet_id;
                        }

                        if (vehicle.driver_id !== null) {
                            driverName = vehicle.driver_id;
                        }

                        return (
                            <tr key={vehicle.id}>
                                <td>{vehicle.plate_number}</td>
                                <td>{vehicle.brand}</td>
                                <td>{vehicle.model}</td>
                                <td>{vehicle.year}</td>
                                <td>{vehicle.device_imei}</td>
                                <td>{fleetName}</td>
                                <td>{driverName}</td>
                                <td>{vehicle.status === "INACTIVE" ? <p style={{ color: "red" }}>{vehicle.status}</p> : <p style={{ color: "green" }}>{vehicle.status}</p> }</td>
                                <td>
                                    <button type="button" onClick={() => setViewVehicleId(vehicle.id)}> View </button>
                                </td>
                                <td>
                                    <button type="button" onClick={() => startEditingVehicle(vehicle)} disabled={isUpdatingVehicle}> Edit </button>
                                </td>
                                <td>
                                    {vehicle.status === "ACTIVE" && ( <button type="button" onClick={() => deactivateVehicle(vehicle)} disabled={deactivatingVehicleId !== null}> Deactivate </button> )}
                                    {vehicle.status === "INACTIVE" && (<button type="button" onClick={() => activateVehicle(vehicle)} disabled={activatingVehicleId !== null}> Activate </button>)}
                                </td>
                                <td>
                                    {vehicle.status === "INACTIVE" && (<button type="button" onClick={() => deleteVehicle(vehicle)} disabled={deletingVehicleId !== null}> Delete </button>)}
                                </td>
                                <td>
                                    <button type="button" onClick={() => setSelectedTrackingVehicle(vehicle)}> Track </button>
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        );
    }
        // Εμφανίζουμε τα στοιχεία του επιλεγμένου οχήματος
    // από τη λίστα που έχουμε ήδη ανακτήσει.
    function show_vehicle_details() {
        if (viewVehicleId === null) {
            return null;
        }

        const vehicle = vehicles.find(
            (item) => item.id === viewVehicleId
        );

        if (vehicle === undefined) {
            return null;
        }

        // Εμφανίζουμε ξεκάθαρα τις συσχετίσεις που δεν έχουν οριστεί.
        let fleetName = "Unassigned";
        let driverName = "Unassigned";

        if (vehicle.fleet_id !== null) {
            fleetName = vehicle.fleet_id;
        }

        if (vehicle.driver_id !== null) {
            driverName = vehicle.driver_id;
        }

        return (
            <div>
                <h3>Vehicle Details: {vehicle.plate_number}</h3>

                <p>Vehicle ID: {vehicle.id}</p>
                <p>Plate Number: {vehicle.plate_number}</p>
                <p>Brand: {vehicle.brand}</p>
                <p>Model: {vehicle.model}</p>
                <p>Year: {vehicle.year}</p>
                <p>Device IMEI: {vehicle.device_imei}</p>
                <p>Fleet ID: {fleetName}</p>
                <p>Driver ID: {driverName}</p>
                <p>Status: {vehicle.status}</p>

                <button type="button" onClick={() => setViewVehicleId(null)}> Close </button>
            </div>
        );
    }

        // Εμφανίζουμε τη φόρμα μόνο όταν έχει επιλεγεί όχημα για επεξεργασία.
    function edit_vehicle_details() {
        if (editingVehicleId === null) {
            return null;
        }

        return (
            <form onSubmit={updateVehicle}>
                <h3>Edit Vehicle: {editingVehicleId}</h3>

                <div>
                    <label htmlFor="edit-vehicle-plate">Plate Number *</label>
                    <input id="edit-vehicle-plate" required value={editVehicleForm.plate_number}
                           onChange={(event) =>
                               setEditVehicleForm({...editVehicleForm, plate_number: event.target.value,})} />
                </div>

                <div>
                    <label htmlFor="edit-vehicle-brand">Brand</label>
                    <input id="edit-vehicle-brand" value={editVehicleForm.brand}
                           onChange={(event) =>
                               setEditVehicleForm({...editVehicleForm, brand: event.target.value,})} />
                </div>

                <div>
                    <label htmlFor="edit-vehicle-model">Model</label>
                    <input id="edit-vehicle-model" value={editVehicleForm.model}
                           onChange={(event) =>
                               setEditVehicleForm({...editVehicleForm, model: event.target.value,})} />
                </div>

                <div>
                    <label htmlFor="edit-vehicle-year">Year</label>
                    <input id="edit-vehicle-year" type="number" step="1" value={editVehicleForm.year}
                           onChange={(event) =>
                               setEditVehicleForm({...editVehicleForm, year: event.target.value,})} />
                </div>

                <div>
                    <label htmlFor="edit-vehicle-imei">Device IMEI *</label>
                    <input id="edit-vehicle-imei" required value={editVehicleForm.device_imei}
                           onChange={(event) =>
                               setEditVehicleForm({...editVehicleForm, device_imei: event.target.value,})} />
                </div>

                {/* Η αλλαγή Fleet καθαρίζει την προηγούμενη επιλογή Driver. */}
                <div>
                    <label htmlFor="edit-vehicle-fleet">Fleet</label>
                    <select id="edit-vehicle-fleet" value={editVehicleForm.fleet_id}
                            onChange={(event) =>
                                setEditVehicleForm({
                                    ...editVehicleForm,
                                    fleet_id: event.target.value,
                                    driver_id: "",
                                })}>
                        <option value="">Unassigned</option>

                        {fleets.map((fleet) => (
                            <option key={fleet.fleet_id} value={fleet.fleet_id}>
                                {fleet.name} ({fleet.fleet_id})
                            </option>
                        ))}
                    </select>
                </div>

                {/* Επιτρέπουμε επιλογή ACTIVE Driver με Fleet. */}
                <div>
                    <label htmlFor="edit-vehicle-driver">Driver</label>
                    <select id="edit-vehicle-driver" value={editVehicleForm.driver_id}
                            onChange={(event) =>
                                setEditVehicleForm({...editVehicleForm, driver_id: event.target.value,})}>
                        <option value="">Unassigned</option>

                        {drivers.map((driver) => {
                            if (driver.status !== "ACTIVE") {
                                return null;
                            }

                            if (driver.fleet_id === null || driver.fleet_id === "") {
                                return null;
                            }

                            if (editVehicleForm.fleet_id !== "" &&
                                driver.fleet_id !== editVehicleForm.fleet_id) {
                                return null;
                            }

                            return (
                                <option key={driver.driver_id} value={driver.driver_id}>
                                    {driver.first_name} {driver.last_name} ({driver.driver_id})
                                </option>
                            );
                        })}
                    </select>
                </div>

                {editVehicleError && (
                    <p role="alert">{editVehicleError}</p>
                )}

                <button type="submit" disabled={isUpdatingVehicle}> Save Changes </button>
                <button type="button" disabled={isUpdatingVehicle}
                        onClick={() => setEditingVehicleId(null)}> Cancel </button>
            </form>
        );
    }

        // Εμφανίζουμε κοινό tracking για όχημα από οποιαδήποτε λίστα.
    function show_vehicle_tracking() {
        if (selectedTrackingVehicle === null) return null;

        let trackingContent = <p>No position received yet.</p>;

        if (latestPosition !== null) {
            trackingContent = (
                <>
                    <LatestPosition position={latestPosition} />
                    <LiveMap position={latestPosition} />
                </>
            );
        }

        return (
            <div>
                <h3>GPS Tracking</h3>
                <p>Vehicle: {selectedTrackingVehicle.plate_number}</p>
                <p>Brand: {selectedTrackingVehicle.brand}</p>
                <p>Model: {selectedTrackingVehicle.model}</p>
                <p>Device IMEI: {selectedTrackingVehicle.device_imei}</p>

                {/* Χρησιμοποιούμε την ίδια θέση και τον ίδιο χάρτη για όλες τις επιλογές. */}
                {trackingContent}

                <button type="button" onClick={() => setSelectedTrackingVehicle(null)}> Close Tracking </button>
            </div>
        );
    }

    if (isAdmin) {
        return (
            <section>
                <h2>Admin Dashboard</h2>

                <h3>Create Fleet</h3>

                <form onSubmit={createFleet}>
                    <div align={"center"}>
                        <label htmlFor="fleet-id">Fleet ID *</label>
                        <input id="fleet-id" required value= { fleetForm.fleet_id }
                            onChange={(event) => setFleetForm({ ...fleetForm, fleet_id: event.target.value, })}
                        />
                    </div>

                    <div>
                        <label htmlFor="fleet-name">Fleet Name *</label>
                        <input
                            id="fleet-name" required value= { fleetForm.name }
                            onChange={(event) => setFleetForm({ ...fleetForm, name: event.target.value, })}
                        />
                    </div>

                    <div>
                        <label htmlFor="fleet-description">Description</label>
                        <textarea id="fleet-description" value= { fleetForm.description }
                                onChange={(event) => setFleetForm({...fleetForm, description: event.target.value,}) }
                        />
                    </div>

                    <h4>Base Location</h4>
                    {
                        (
                            [
                                ["name", "Location Name", true],
                                ["address", "Address", false],
                                ["city", "City", false],
                                ["postal_code", "Postal Code", false],
                                ["latitude", "Latitude", true],
                                ["longitude", "Longitude", true],
                            ] as const
                        ).map( ([field, label, required]) =>
                            (
                                <div key={field}>
                                    <label htmlFor={`fleet-${field}`}>
                                        {label}{required ? " *" : ""}
                                    </label>

                                    <input
                                        id={`fleet-${field}`}
                                        required={required}
                                        type={ field === "latitude" || field === "longitude" ? "number" : "text"}
                                        step={ field === "latitude" || field === "longitude" ? "any" : undefined }
                                        value={fleetForm.base_location[field]}
                                        onChange={(event) =>
                                            setFleetForm({ ...fleetForm, base_location: { ...fleetForm.base_location, [field]: event.target.value, },})
                                        }
                                    />
                                </div>
                            )
                        )
                    }
                    {
                        createError && ( <p role="alert">{createError}</p> )
                    }

                    {
                        createSuccess && ( <p role="status">{createSuccess}</p> )
                    }

                    <button type="submit" disabled={isCreating}>
                        {isCreating ? "Creating..." : "Create Fleet"}
                    </button>
                </form>

                <hr />

                <h3>Fleets</h3>
                {
                    show_fleets()
                }
                {
                    deleteError && <p role="alert">{deleteError}</p>
                }
                {
                    deleteSuccess && <p role="status">{deleteSuccess}</p>
                }
                {
                    show_fleet_details()
                }
                {
                    edit_fleet_details()
                }

                <hr />
                <section>
                    {/* Φόρμα δημιουργίας νέου Fleet Manager από τον Admin. */}
                    <h3>Create Fleet Manager</h3>

                    <form onSubmit={createFleetManager}>
                        <div>
                            <label htmlFor="manager-username">Username</label>
                            <input
                                id="manager-username"
                                type="text"
                                value={fleetManagerForm.username}
                                onChange={(event) =>
                                    setFleetManagerForm({ ...fleetManagerForm, username: event.target.value, }) } required />
                        </div>

                        <div>
                            <label htmlFor="manager-id">Manager ID</label>
                            <input id="manager-id" type="text" value={fleetManagerForm.manager_id}
                                   onChange={(event) =>
                                       setFleetManagerForm({...fleetManagerForm, manager_id: event.target.value,}) } required />
                        </div>

                        <div>
                            <label htmlFor="manager-first-name">First Name</label>
                            <input id="manager-first-name" type="text" value={fleetManagerForm.first_name}
                                   onChange={(event) =>
                                       setFleetManagerForm({...fleetManagerForm, first_name: event.target.value,}) } required />
                        </div>

                        <div>
                            <label htmlFor="manager-last-name">Last Name</label>
                            <input id="manager-last-name" type="text" value={fleetManagerForm.last_name}
                                   onChange={(event) =>
                                       setFleetManagerForm({...fleetManagerForm, last_name: event.target.value,}) } required />
                        </div>

                        <div>
                            <label htmlFor="manager-email">Email</label>
                            <input id="manager-email" type="email" value={fleetManagerForm.email}
                                onChange={(event) =>
                                    setFleetManagerForm({...fleetManagerForm, email: event.target.value,}) } required />
                        </div>

                        <div>
                            <label htmlFor="manager-fleet">Fleet</label>
                            <select id="manager-fleet" value={fleetManagerForm.fleet_id}
                                    onChange={(event) =>
                                        setFleetManagerForm({...fleetManagerForm, fleet_id: event.target.value,}) } required >
                                <option value="">Select Fleet</option>

                                {
                                    fleets.map((fleet) => (
                                            <option key={fleet.fleet_id} value={fleet.fleet_id}>
                                                {fleet.name} ({fleet.fleet_id})
                                            </option>
                                        )
                                    )
                                }
                            </select>
                        </div>

                        <div>
                            <label htmlFor="manager-department">Department ID</label>
                            <input id="manager-department" type="text" value={fleetManagerForm.department_id}
                                   onChange={(event) =>
                                       setFleetManagerForm({...fleetManagerForm, department_id: event.target.value,}) } />
                        </div>

                        <div>
                            <label htmlFor="manager-birth-date">Date of Birth</label>
                            <input id="manager-birth-date" type="date" value={fleetManagerForm.date_of_birth}
                                onChange={(event) =>
                                    setFleetManagerForm({...fleetManagerForm, date_of_birth: event.target.value,}) } />
                        </div>

                        <div>
                            <label htmlFor="manager-identity">Identity Card Number</label>
                            <input id="manager-identity" type="text" value={fleetManagerForm.identity_card_number}
                                onChange={(event) =>
                                    setFleetManagerForm({...fleetManagerForm, identity_card_number: event.target.value,}) }/>
                        </div>

                        <div>
                            <label htmlFor="manager-tax-id">Tax ID</label>
                            <input id="manager-tax-id" type="text" value={fleetManagerForm.tax_id}
                                onChange={(event) =>
                                    setFleetManagerForm({...fleetManagerForm,tax_id: event.target.value,}) } />
                        </div>

                        <div>
                            <label htmlFor="manager-phone">Phone Number</label>
                            <input id="manager-phone" type="tel" value={fleetManagerForm.phone_number}
                                onChange={(event) =>
                                    setFleetManagerForm({ ...fleetManagerForm, phone_number: event.target.value, }) } />
                        </div>

                        <div>
                            <label htmlFor="manager-hire-date">Hire Date</label>
                            <input id="manager-hire-date" type="date" value={fleetManagerForm.hire_date}
                                onChange={(event) =>
                                    setFleetManagerForm({ ...fleetManagerForm, hire_date: event.target.value, }) } />
                        </div>

                        <button type="submit" disabled={isCreatingManager}>
                            {isCreatingManager ? "Creating..." : "Create Fleet Manager"}
                        </button>

                        {
                            createManagerError && ( <p role="alert">{createManagerError}</p>)
                        }

                        {
                            createManagerSuccess && (<p>{createManagerSuccess}</p>)
                        }

                    </form>

                    <hr />
                    <h3>Fleet Managers</h3>
                    {
                        show_fleet_managers()
                    }
                    {
                        show_fleet_manager_details()
                    }
                    {
                        edit_fleet_manager_details()
                    }
                    {
                        manager_error_show()
                    }
                    <hr />
                                    {/* Φόρμα δημιουργίας νέου Driver από τον Admin. */}
                    <h3>Create Driver</h3>

                    <form onSubmit={createDriver}>
                        {(
                            [
                                ["username", "Username", true],
                                ["driver_id", "Driver ID", true],
                                ["first_name", "First Name", true],
                                ["last_name", "Last Name", true],
                                ["email", "Email", true],
                                ["date_of_birth", "Date of Birth", false],
                                ["identity_card_number", "Identity Card Number", false],
                                ["tax_id", "Tax ID", false],
                                ["phone_number", "Phone Number", false],
                                ["license_number", "License Number", false],
                                ["license_category", "License Category", false],
                                ["license_expiry_date", "License Expiry Date", false],
                                ["hire_date", "Hire Date", false],
                            ] as const
                        ).map(([field, label, required]) => (
                            <div key={field}>
                                <label htmlFor={`driver-${field}`}>
                                    {label}{required ? " *" : ""}
                                </label>

                                <input
                                    id={`driver-${field}`}
                                    required={required}
                                    type={
                                        field === "email"
                                            ? "email"
                                            : field === "date_of_birth" ||
                                              field === "license_expiry_date" ||
                                              field === "hire_date"
                                            ? "date"
                                            : "text"
                                    }
                                    value={driverForm[field]}
                                    onChange={(event) =>
                                        setDriverForm({
                                            ...driverForm,
                                            [field]: event.target.value,
                                        })
                                    }
                                />
                            </div>
                        ))}

                        {/* Επιλέγουμε Fleet από τα ήδη διαθέσιμα Fleets. */}
                        <div>
                            <label htmlFor="driver-fleet">Fleet</label>
                            <select
                                id="driver-fleet"
                                value={driverForm.fleet_id}
                                onChange={(event) =>
                                    setDriverForm({
                                        ...driverForm,
                                        fleet_id: event.target.value,
                                    })
                                }
                            >
                                <option value="">No Fleet</option>
                                {fleets.map((fleet) => (
                                    <option key={fleet.fleet_id} value={fleet.fleet_id}>
                                        {fleet.name} ({fleet.fleet_id})
                                    </option>
                                ))}
                            </select>
                        </div>

                        {/* Το Department παραμένει προαιρετικό. */}
                        {/*<div>*/}
                        {/*    <label htmlFor="driver-department">Department ID</label>*/}
                        {/*    <input*/}
                        {/*        id="driver-department"*/}
                        {/*        value={driverForm.department_id}*/}
                        {/*        onChange={(event) =>*/}
                        {/*            setDriverForm({*/}
                        {/*                ...driverForm,*/}
                        {/*                department_id: event.target.value,*/}
                        {/*            })*/}
                        {/*        }*/}
                        {/*    />*/}
                        {/*</div>*/}

                        {createDriverError && (
                            <p role="alert">{createDriverError}</p>
                        )}

                        {createDriverSuccess && (
                            <p role="status">{createDriverSuccess}</p>
                        )}

                        <button type="submit" disabled={isCreatingDriver}> {isCreatingDriver ? "Creating..." : "Create Driver"} </button>
                    </form>

                    <hr />
                    <h3>Drivers</h3>
                    {
                        show_drivers()
                    }
                    {
                        show_driver_details()
                    }
                    {
                        edit_driver_details()
                    }
                    {
                        driver_error_show()
                    }
                    <hr />

                    <h3>Create Vehicle</h3>

                    <form onSubmit={createVehicle}>
                        <div>
                            <label htmlFor="vehicle-plate">Plate Number *</label>
                            <input id="vehicle-plate" required value={vehicleForm.plate_number}
                                   onChange={(event) =>
                                       setVehicleForm({...vehicleForm, plate_number: event.target.value,})} />
                        </div>

                        <div>
                            <label htmlFor="vehicle-brand">Brand</label>
                            <input id="vehicle-brand" value={vehicleForm.brand}
                                   onChange={(event) =>
                                       setVehicleForm({...vehicleForm, brand: event.target.value,})} />
                        </div>

                        <div>
                            <label htmlFor="vehicle-model">Model</label>
                            <input id="vehicle-model" value={vehicleForm.model}
                                   onChange={(event) =>
                                       setVehicleForm({...vehicleForm, model: event.target.value,})} />
                        </div>

                        <div>
                            <label htmlFor="vehicle-year">Year</label>
                            <input id="vehicle-year" type="number" step="1" value={vehicleForm.year}
                                   onChange={(event) =>
                                       setVehicleForm({...vehicleForm, year: event.target.value,})} />
                        </div>

                        <div>
                            <label htmlFor="vehicle-imei">Device IMEI *</label>
                            <input id="vehicle-imei" required value={vehicleForm.device_imei}
                                   onChange={(event) =>
                                       setVehicleForm({...vehicleForm, device_imei: event.target.value,})} />
                        </div>

                        {/* Χρησιμοποιούμε τη λίστα Fleets που έχει ήδη φορτωθεί. */}
                        <div>
                            <label htmlFor="vehicle-fleet">Fleet</label>
                            <select id="vehicle-fleet" value={vehicleForm.fleet_id}
                                    onChange={(event) =>
                                        setVehicleForm({...vehicleForm, fleet_id: event.target.value,driver_id: "",})}>
                                <option value="">Unassigned</option>

                                {fleets.map((fleet) => (
                                    <option key={fleet.fleet_id} value={fleet.fleet_id}>
                                        {fleet.name} ({fleet.fleet_id})
                                    </option>
                                ))}
                            </select>
                        </div>

                        {/* Προσφέρουμε για ανάθεση μόνο ACTIVE Drivers με Fleet. */}
                        <div>
                            <label htmlFor="vehicle-driver">Driver</label>
                            <select id="vehicle-driver" value={vehicleForm.driver_id}
                                    onChange={(event) =>
                                        setVehicleForm({...vehicleForm, driver_id: event.target.value,})}>
                                <option value="">Unassigned</option>

                                {drivers.map((driver) => {
                                    if (driver.status !== "ACTIVE") {
                                        return null;
                                    }

                                    if (driver.fleet_id === null || driver.fleet_id === "") {
                                        return null;
                                    }

                                    // Αν έχει επιλεγεί Fleet, δείχνουμε μόνο τους Drivers του.
                                    if (vehicleForm.fleet_id !== "" &&
                                        driver.fleet_id !== vehicleForm.fleet_id) {
                                        return null;
                                    }

                                    return (
                                        <option key={driver.driver_id} value={driver.driver_id}>
                                            {driver.first_name} {driver.last_name} ({driver.driver_id})
                                        </option>
                                    );
                                })}
                            </select>
                        </div>

                        <p>The backend checks Fleet and Driver assignments.</p>

                        {createVehicleError && (
                            <p role="alert">{createVehicleError}</p>
                        )}

                        {createVehicleSuccess && (
                            <p role="status">{createVehicleSuccess}</p>
                        )}

                        <button type="submit" disabled={isCreatingVehicle}>
                            Create Vehicle
                        </button>
                    </form>

                    <hr />
                    <h3>Vehicles</h3>
                    {
                        show_vehicles()
                    }
                    {
                        show_vehicle_details()
                    }
                    {
                        edit_vehicle_details()
                    }
                    {
                        show_vehicle_tracking()
                    }
                    {
                        deactivateVehicleError && (<p role="alert">{deactivateVehicleError}</p>)
                    }

                    {
                        deactivateVehicleSuccess && (<p role="status">{deactivateVehicleSuccess}</p>)
                    }
                    {
                        activateVehicleError && (<p role="alert">{activateVehicleError}</p>)
                    }
                    {
                        activateVehicleSuccess && (<p role="status">{activateVehicleSuccess}</p>)
                    }
                    {
                        deleteVehicleError && (<p role="alert">{deleteVehicleError}</p>)
                    }
                    {
                        deleteVehicleSuccess && (<p role="status">{deleteVehicleSuccess}</p>)
                    }


                </section>
            </section>
        );
    }
    else {
        return null;
    }
}

export default AdminDashboard;
