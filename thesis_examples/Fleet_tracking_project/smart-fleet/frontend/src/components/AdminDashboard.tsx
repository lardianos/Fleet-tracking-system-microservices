
import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";

// Περιγράφουμε μόνο τα πεδία του Fleet που χρειαζόμαστε
// για την εμφάνιση της λίστας στο Admin Dashboard.
interface Fleet {
    fleet_id: string;
    name: string;
    description: string | null;
    base_location: {
        name: string;
        address: string | null;
        city: string | null;
        postal_code: string | null;
        latitude: number;
        longitude: number;
    };
}
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
interface FleetManager {
    id: string;
    manager_id: string;
    keycloak_user_id: string;
    first_name: string;
    last_name: string;
    email: string | null;
    phone_number: string | null;
    fleet_id: string | null;
    department_id: string | null;
    status: string;
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
                const response = await fetch(
                    "http://localhost:8004/api/v1/admin/fleet-managers",
                    {
                        headers: {
                            Authorization: `Bearer ${token}`,
                        },
                        signal: controller.signal,
                    }
                );

                if (!response.ok) {
                    throw new Error(
                        `Failed to load fleet managers: ${response.status}`
                    );
                }

                const managerData: FleetManager[] = await response.json();

                if (!controller.signal.aborted) {
                    setFleetManagers(managerData);
                }
            } catch (requestError) {
                if (!controller.signal.aborted) {
                    console.error(
                        "Failed to load fleet managers:",
                        requestError
                    );

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

    if (isAdmin) {
        return (
            <section>
            <h2>Admin Dashboard</h2>

            <h3>Create Fleet</h3>

            <form onSubmit={createFleet}>
                <div align={"center"}>
                    <label htmlFor="fleet-id">Fleet ID *</label>
                    <input
                        id="fleet-id"
                        required
                        value={fleetForm.fleet_id}
                        onChange={(event) => setFleetForm({ ...fleetForm, fleet_id: event.target.value, })}
                    />
                </div>

                <div>
                    <label htmlFor="fleet-name">Fleet Name *</label>
                    <input
                        id="fleet-name"
                        required
                        value={fleetForm.name}
                        onChange={(event) => setFleetForm({ ...fleetForm, name: event.target.value, })}
                    />
                </div>

                <div>
                    <label htmlFor="fleet-description">Description</label>
                    <textarea
                        id="fleet-description"
                        value={fleetForm.description}
                        onChange={(event) =>
                            setFleetForm({
                                ...fleetForm,
                                description: event.target.value,
                            })
                        }
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
                isLoading ? (
                    <p>Loading fleets...</p>
                ) : error ? (
                    <p role="alert">{error}</p>
                ) : fleets.length === 0 ? (
                    <p>No fleets available.</p>
                ) : (
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
                                        <button type="button" onClick={() => startEditingFleet(fleet)} disabled={deletingFleetId !== null}> Edit </button>
                                        <button type="button" onClick={() => deleteFleet(fleet)} disabled={deletingFleetId !== null}>
                                            {deletingFleetId === fleet.fleet_id ? "Deleting..." : "Delete"} </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )
            }
            {
                editingFleetId && ( <form onSubmit={updateFleet}>
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
            }

            <hr />
            <section>
                <h3>Fleet Managers</h3>
                {/* Φόρμα δημιουργίας νέου Fleet Manager από τον Admin. */}
                <h4>Create Fleet Manager</h4>

                <form onSubmit={createFleetManager}>
                    <div>
                        <label htmlFor="manager-username">Username</label>
                        <input
                            id="manager-username"
                            type="text"
                            value={fleetManagerForm.username}
                            onChange={(event) =>
                                setFleetManagerForm({
                                    ...fleetManagerForm,
                                    username: event.target.value,
                                })
                            }
                            required
                        />
                    </div>

                    <div>
                        <label htmlFor="manager-id">Manager ID</label>
                        <input
                            id="manager-id"
                            type="text"
                            value={fleetManagerForm.manager_id}
                            onChange={(event) =>
                                setFleetManagerForm({
                                    ...fleetManagerForm,
                                    manager_id: event.target.value,
                                })
                            }
                            required
                        />
                    </div>

                    <div>
                        <label htmlFor="manager-first-name">First Name</label>
                        <input
                            id="manager-first-name"
                            type="text"
                            value={fleetManagerForm.first_name}
                            onChange={(event) =>
                                setFleetManagerForm({
                                    ...fleetManagerForm,
                                    first_name: event.target.value,
                                })
                            }
                            required
                        />
                    </div>

                    <div>
                        <label htmlFor="manager-last-name">Last Name</label>
                        <input
                            id="manager-last-name"
                            type="text"
                            value={fleetManagerForm.last_name}
                            onChange={(event) =>
                                setFleetManagerForm({
                                    ...fleetManagerForm,
                                    last_name: event.target.value,
                                })
                            }
                            required
                        />
                    </div>

                    <div>
                        <label htmlFor="manager-email">Email</label>
                        <input
                            id="manager-email"
                            type="email"
                            value={fleetManagerForm.email}
                            onChange={(event) =>
                                setFleetManagerForm({
                                    ...fleetManagerForm,
                                    email: event.target.value,
                                })
                            }
                            required
                        />
                    </div>

                    <div>
                        <label htmlFor="manager-fleet">Fleet</label>
                        <select
                            id="manager-fleet"
                            value={fleetManagerForm.fleet_id}
                            onChange={(event) =>
                                setFleetManagerForm({
                                    ...fleetManagerForm,
                                    fleet_id: event.target.value,
                                })
                            }
                            required
                        >
                            <option value="">Select Fleet</option>

                            {fleets.map((fleet) => (
                                <option key={fleet.fleet_id} value={fleet.fleet_id}>
                                    {fleet.name} ({fleet.fleet_id})
                                </option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label htmlFor="manager-department">Department ID</label>
                        <input
                            id="manager-department"
                            type="text"
                            value={fleetManagerForm.department_id}
                            onChange={(event) =>
                                setFleetManagerForm({
                                    ...fleetManagerForm,
                                    department_id: event.target.value,
                                })
                            }
                        />
                    </div>

                    <div>
                        <label htmlFor="manager-birth-date">Date of Birth</label>
                        <input
                            id="manager-birth-date"
                            type="date"
                            value={fleetManagerForm.date_of_birth}
                            onChange={(event) =>
                                setFleetManagerForm({
                                    ...fleetManagerForm,
                                    date_of_birth: event.target.value,
                                })
                            }
                        />
                    </div>

                    <div>
                        <label htmlFor="manager-identity">Identity Card Number</label>
                        <input
                            id="manager-identity"
                            type="text"
                            value={fleetManagerForm.identity_card_number}
                            onChange={(event) =>
                                setFleetManagerForm({
                                    ...fleetManagerForm,
                                    identity_card_number: event.target.value,
                                })
                            }
                        />
                    </div>

                    <div>
                        <label htmlFor="manager-tax-id">Tax ID</label>
                        <input
                            id="manager-tax-id"
                            type="text"
                            value={fleetManagerForm.tax_id}
                            onChange={(event) =>
                                setFleetManagerForm({
                                    ...fleetManagerForm,
                                    tax_id: event.target.value,
                                })
                            }
                        />
                    </div>

                    <div>
                        <label htmlFor="manager-phone">Phone Number</label>
                        <input
                            id="manager-phone"
                            type="tel"
                            value={fleetManagerForm.phone_number}
                            onChange={(event) =>
                                setFleetManagerForm({
                                    ...fleetManagerForm,
                                    phone_number: event.target.value,
                                })
                            }
                        />
                    </div>

                    <div>
                        <label htmlFor="manager-hire-date">Hire Date</label>
                        <input
                            id="manager-hire-date"
                            type="date"
                            value={fleetManagerForm.hire_date}
                            onChange={(event) =>
                                setFleetManagerForm({
                                    ...fleetManagerForm,
                                    hire_date: event.target.value,
                                })
                            }
                        />
                    </div>

                    <button type="submit" disabled={isCreatingManager}>
                        {isCreatingManager ? "Creating..." : "Create Fleet Manager"}
                    </button>

                    {createManagerError && (
                        <p role="alert">{createManagerError}</p>
                    )}

                    {createManagerSuccess && (
                        <p>{createManagerSuccess}</p>
                    )}
                </form>
                {
                    isLoadingManagers ? (
                        <p>Loading fleet managers...</p>
                    ) : managersError ? (
                        <p role="alert">{managersError}</p>
                    ) : fleetManagers.length === 0 ? (
                        <p>No fleet managers available.</p>
                    ) : (
                            <table>
                                <thead>
                                    <tr>
                                        <th>Manager ID</th>
                                        <th>Name</th>
                                        <th>Email</th>
                                        <th>Fleet</th>
                                        <th>Status</th>
                                    </tr>
                                </thead>

                                <tbody>
                                    {fleetManagers.map((manager) => (
                                        <tr key={manager.manager_id}>
                                            <td>{manager.manager_id}</td>
                                            <td>
                                                {manager.first_name} {manager.last_name}
                                            </td>
                                            <td>{manager.email ?? "—"}</td>
                                            <td>{manager.fleet_id ?? "Unassigned"}</td>
                                            <td>{manager.status}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )
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
