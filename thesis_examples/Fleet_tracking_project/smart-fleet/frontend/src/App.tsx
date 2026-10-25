import { useEffect, useState } from "react";
import { useAuth } from "./auth/AuthContext";
import "./App.css";

import { authenticatedFetch } from "./auth/session";

import type { Vehicle } from "./types/Vehicle";
import type { DriverProfile as DriverProfileData } from "./types/DriverProfile";
import type {  FleetManagerProfile as FleetManagerProfileData } from "./types/FleetManagerProfile";

import { useVehicleTracking } from "./hooks/useVehicleTracking";

import LatestPosition from "./components/LatestPosition";
import LiveMap from "./components/LiveMap";
import DriverProfile from "./components/DriverProfile";
import MyVehicle from "./components/MyVehicle";
import FleetManagerProfile from "./components/FleetManagerProfile";
import FleetVehicles from "./components/FleetVehicles";
import FleetDrivers from "./components/FleetDrivers";
import AdminDashboard from "./components/AdminDashboard";

import TokenTimer from "./components/TokenTimer";
import PositionHistory from "./components/PositionHistory";

import DashboardNotifications from "./components/DashboardNotifications";

function App() {

    const { username, roles, hasRole, logout, token } = useAuth();
    // Κρατάει την τελευταία γνωστή θέση του οχήματος.
    // Αρχικά είναι null μέχρι να ολοκληρωθεί το πρώτο REST request.

    // const [latestPosition, setLatestPosition] = useState<Position | null>(null);
    // Κρατάμε την επιλεγμένη ενότητα του Driver.
    const [activeDriverSection, setActiveDriverSection] = useState("profile");
        // Κρατάμε την επιλεγμένη ενότητα του Fleet Manager.
    const [activeManagerSection, setActiveManagerSection] = useState("profile");

        // Κρατάμε το όχημα που επέλεξε ο Fleet Manager για tracking.
    const [managerTrackingVehicle, setManagerTrackingVehicle] = useState<Vehicle | null>(null);

    let managerTrackingImei: string | null = null;

    if (managerTrackingVehicle !== null) { managerTrackingImei = managerTrackingVehicle.device_imei;}

    // Χρησιμοποιούμε την ίδια λειτουργία tracking με Driver και Admin.
    const managerLatestPosition = useVehicleTracking(managerTrackingImei);

    // Κρατάει πιθανό μήνυμα σφάλματος από το REST request.
    const [error, setError] = useState("");

    const [vehicleImei, setVehicleImei] = useState<string | null>(null);
        // Χρησιμοποιούμε την κοινή λειτουργία tracking για το όχημα του Driver.
    const latestPosition = useVehicleTracking(vehicleImei);

    // Κρατάει τα στοιχεία του authenticated driver.
    const [driverProfile, setDriverProfile] = useState<DriverProfileData | null>(null);

    // Κρατάει ολόκληρο το vehicle ώστε να μπορούμε
    // να εμφανίσουμε και τα στοιχεία του στο dashboard.

    const [assignedVehicle, setAssignedVehicle] = useState<Vehicle | null>(null);

        // Κρατάμε όλα τα οχήματα που είναι ανατεθειμένα στον Driver.
    const [driverVehicles, setDriverVehicles] = useState<Vehicle[]>([]);
    const [isLoadingDriverVehicles, setIsLoadingDriverVehicles] = useState(false);
    const [driverVehiclesError, setDriverVehiclesError] = useState("");

    // Κρατάει το business profile του authenticated Fleet Manager.
    const [fleetManagerProfile, setFleetManagerProfile] = useState< FleetManagerProfileData | null>(null);

    // Κρατάει όλα τα vehicles του fleet που διαχειρίζεται ο manager.
    const [fleetVehicles, setFleetVehicles] = useState<Vehicle[]>([]);

    // Κρατάει όλους τους drivers του fleet που διαχειρίζεται ο manager.
    const [fleetDrivers, setFleetDrivers] = useState<DriverProfileData[]>([]);

    // Παρακολουθούμε την ενεργοποίηση και το αποτέλεσμα του αιτήματος.
    const [activatingVehicleId, setActivatingVehicleId] = useState<string | null>(null);
    const [activateVehicleError, setActivateVehicleError] = useState("");
    const [activateVehicleSuccess, setActivateVehicleSuccess] = useState("");

    useEffect(() => {
      async function loadDriverProfile() {
          try {
              setError("");
              // Ζητάμε το Driver Profile του authenticated χρήστη.
              // Το API Gateway βρίσκει το σωστό profile από το JWT sub.
              const response = await fetch(
                  "http://localhost:8004/api/v1/drivers/me", { headers: { Authorization: `Bearer ${token}`, }, } );

              if (!response.ok) {
                throw new Error(
                  `Failed to load driver profile: ${response.status}`
                );
              }

              const profile: DriverProfileData = await response.json();

              setDriverProfile(profile);

            } catch (requestError) {
              console.error("Failed to load driver profile:", requestError);
              setError("Could not load driver profile.");
            }
      }

      if (token && hasRole("driver")) {
        loadDriverProfile();
      }
    }, [token, hasRole]);

    useEffect(() => {
        if (!token || !hasRole("driver")) return;

        const controller = new AbortController();

        // Ανανεώνουμε τη λίστα χωρίς να καθαρίζουμε την επιλογή του Driver.
        async function loadAssignedVehicles() {
            setIsLoadingDriverVehicles(true);
            setDriverVehiclesError("");

            try {
                const response = await authenticatedFetch(
                    "http://localhost:8004/api/v1/drivers/me/vehicles",
                    { signal: controller.signal }
                );

                if (!response.ok) {
                    throw new Error(`Failed to load assigned vehicles: ${response.status}`);
                }

                const vehicles: Vehicle[] = await response.json();

                if (controller.signal.aborted) return;

                setDriverVehicles(vehicles);

                // Διατηρούμε το επιλεγμένο όχημα εφόσον παραμένει ανατεθειμένο.
                setAssignedVehicle((previous) => {
                    if (previous === null) return null;

                    const updatedVehicle = vehicles.find((vehicle) => vehicle.id === previous.id);

                    if (updatedVehicle === undefined) return null;

                    return updatedVehicle;
                });
            } catch (requestError) {
                if (controller.signal.aborted) return;

                let errorMessage = "Could not load assigned vehicles.";

                if (requestError instanceof Error) {
                    errorMessage = requestError.message;
                }

                setDriverVehiclesError(errorMessage);
            } finally {
                if (!controller.signal.aborted) {
                    setIsLoadingDriverVehicles(false);
                }
            }
        }

        loadAssignedVehicles();

        return () => {
            controller.abort();
        };
    }, [token, hasRole]);

    useEffect(() => {
        // Συγχρονίζουμε το IMEI του tracking με το επιλεγμένο όχημα.
        if (assignedVehicle === null) {
            setVehicleImei(null);
            return;
        }

        setVehicleImei(assignedVehicle.device_imei);
    }, [assignedVehicle]);


    useEffect(() => {
      async function loadFleetManagerProfile() {
        try {
          const response = await fetch(
            "http://localhost:8004/api/v1/fleet-managers/me",
            {
              headers: {
                Authorization: `Bearer ${token}`,
              },
            }
          );

          if (!response.ok) {
            throw new Error(
              `Failed to load fleet manager profile: ${response.status}`
            );
          }

          const profile: FleetManagerProfileData = await response.json();

          setFleetManagerProfile(profile);
        } catch (requestError) {
          console.error(
            "Failed to load fleet manager profile:",
            requestError
          );
          setError("Could not load fleet manager profile.");
        }
      }

      if (token && hasRole("fleet_manager")) {
        loadFleetManagerProfile();
      }
    }, [token, hasRole]);

    useEffect(() => {
      async function loadFleetData() {
        try {
            const [vehiclesResponse, driversResponse] = await Promise.all([
                fetch(
                    "http://localhost:8004/api/v1/fleet-managers/me/vehicles",
                    {
                    headers: {
                      Authorization: `Bearer ${token}`,
                    },
                    }
                ),
                fetch(
                  "http://localhost:8004/api/v1/fleet-managers/me/drivers",
                  {
                    headers: {
                      Authorization: `Bearer ${token}`,
                    },
                  }
                ),
          ]);

          if (!vehiclesResponse.ok) {
            throw new Error(
              `Failed to load fleet vehicles: ${vehiclesResponse.status}`
            );
          }

          if (!driversResponse.ok) {
            throw new Error(
              `Failed to load fleet drivers: ${driversResponse.status}`
            );
          }

          const vehicles: Vehicle[] = await vehiclesResponse.json();
          const drivers: DriverProfileData[] = await driversResponse.json();

          setFleetVehicles(vehicles);
          setFleetDrivers(drivers);
        } catch (requestError) {
          console.error("Failed to load fleet data:", requestError);
          setError("Could not load fleet data.");
        }
      }

      if (token && hasRole("fleet_manager")) {
        loadFleetData();
      }
    }, [token, hasRole]);

        // Αντικαθιστούμε το ενημερωμένο όχημα στη λίστα του Fleet Manager.
    // Ενημερώνουμε τη λίστα και το επιλεγμένο όχημα tracking με τα νέα στοιχεία.
    function replaceFleetVehicleInList(updatedVehicle: Vehicle) {
        setFleetVehicles((previous) =>
            previous.map((vehicle) => {
                if (vehicle.id === updatedVehicle.id) return updatedVehicle;
                return vehicle;
            })
        );

                // Κλείνουμε το tracking όταν απενεργοποιείται το επιλεγμένο όχημα.
        setManagerTrackingVehicle((previous) => {
            if (previous !== null && previous.id === updatedVehicle.id) {
                if (updatedVehicle.status === "INACTIVE") return null;
                return updatedVehicle;
            }

            return previous;
        });
    }

        // Επιλέγουμε το όχημα για προβολή και για το κοινό tracking hook.
    function selectDriverVehicle(vehicleId: string) {
        const vehicle = driverVehicles.find((item) => item.id === vehicleId);

        if (vehicle === undefined) {
            setAssignedVehicle(null);
            setVehicleImei(null);
            return;
        }

        setAssignedVehicle(vehicle);
        setVehicleImei(vehicle.device_imei);
    }

    // Εμφανίζουμε την ίδια επιλογή οχήματος στις δύο ενότητες του Driver.
    function showDriverVehicleSelection() {
        if (isLoadingDriverVehicles) return <p>Loading assigned vehicles...</p>;
        if (driverVehiclesError !== "") return <p role="alert">{driverVehiclesError}</p>;
        if (driverVehicles.length === 0) return <p>No vehicles assigned to this Driver.</p>;

        let selectedVehicleId = "";

        if (assignedVehicle !== null) {
            selectedVehicleId = assignedVehicle.id;
        }

        return (
            <div>
                <label htmlFor="driver-selected-vehicle">Select Vehicle </label>
                <select id="driver-selected-vehicle" value={selectedVehicleId}
                        onChange={(event) => selectDriverVehicle(event.target.value)}>
                    <option value="">Select a vehicle</option>

                    {driverVehicles.map((vehicle) => (
                        <option key={vehicle.id} value={vehicle.id}>{vehicle.plate_number}</option>
                    ))}
                </select>
            </div>
        );
    }

        // Προσθέτουμε στη λίστα το νέο όχημα που επέστρεψε το backend.
    function addFleetVehicleToList(createdVehicle: Vehicle) {
        setFleetVehicles((previous) => [...previous, createdVehicle]);
    }



  return (
    <div className="app">
        <header className="app-header">
            <div>
                <h1>Smart Fleet Tracking</h1>
                <p>Logged in as: {username}</p>
                <p className="app-user-roles">Roles: {roles.join(", ")}</p>
            </div>


        <div className="app-header-actions">
            <DashboardNotifications/>
            <TokenTimer/>
            <button data-skip-session-refresh="true" onClick={logout}> Logout </button>
        </div>
        </header>

        <main className="app-content">


                       {
                           hasRole("driver") && (
               <section className="user-dashboard">
                   <div className="admin-layout">
                       <nav className="admin-sidebar" aria-label="Driver navigation">
                           <h2>Driver</h2>


                           <button type="button" aria-pressed={activeDriverSection === "profile"} onClick={() => setActiveDriverSection("profile")}> My Profile </button>
                           <button type="button" aria-pressed={activeDriverSection === "vehicle"} onClick={() => setActiveDriverSection("vehicle")}> My Vehicles </button>
                           <button type="button" aria-pressed={activeDriverSection === "tracking"} onClick={() => setActiveDriverSection("tracking")}> Live Tracking </button>
                       </nav>

                       <div className="admin-content">
                           {
                               error && (<p role="alert">{error}</p>)
                           }

                           {
                               activeDriverSection === "profile" && driverProfile !== null && (<DriverProfile profile={driverProfile}/>)
                           }

                           {
                               activeDriverSection === "vehicle" && (
                               <div>
                                   <h3>My Vehicles</h3>

                                   {isLoadingDriverVehicles && (<p>Loading assigned vehicles...</p>)}

                                   {driverVehiclesError !== "" && (
                                       <p role="alert">{driverVehiclesError}</p>
                                   )}

                                   {!isLoadingDriverVehicles && driverVehiclesError === "" && driverVehicles.length === 0 && (
                                       <p>No vehicles assigned to this Driver.</p>
                                   )}

                                   {!isLoadingDriverVehicles && driverVehiclesError === "" && (
                                       driverVehicles.map((vehicle) => (
                                           <MyVehicle key={vehicle.id} vehicle={vehicle}/>
                                       ))
                                   )}
                               </div>
                           )}

                           {
                               activeDriverSection === "tracking" && (
                               <div className="user-tracking">
                                   <h3>Live Tracking</h3>
                                   {
                                       showDriverVehicleSelection()
                                   }
                                   {
                                       latestPosition !== null && (
                                           <>
                                               <LatestPosition position={latestPosition}/>
                                               <LiveMap position={latestPosition}/>
                                           </>
                                       )
                                   }

                                   {
                                       latestPosition === null && (
                                           <p>
                                               {assignedVehicle === null && driverVehicles.length > 0 && (<p>Select a vehicle to start tracking.</p>)}

                                               {assignedVehicle !== null && latestPosition === null && (<p>No position received yet.</p>)}
                                           </p>
                                       )
                                   }
                               </div>
                           )}
                       </div>
                   </div>
               </section>
           )}
            {
                hasRole("fleet_manager") && (

                   <section className="user-dashboard">
                   <div className="admin-layout">
                       <nav className="admin-sidebar" aria-label="Fleet Manager navigation">
                           <h2>Fleet Manager</h2>

                           <button type="button" aria-pressed={activeManagerSection === "profile"} onClick={() => setActiveManagerSection("profile")}> My Profile </button>
                           <button type="button" aria-pressed={activeManagerSection === "vehicles"} onClick={() => setActiveManagerSection("vehicles")}> Fleet Vehicles </button>
                           <button type="button" aria-pressed={activeManagerSection === "drivers"} onClick={() => setActiveManagerSection("drivers")}> Fleet Drivers </button>
                           <button type="button" aria-pressed={activeManagerSection === "history"} onClick={() => setActiveManagerSection("history")}> Position History </button>
                       </nav>

                       <div className="admin-content">
                           {
                               error && (<p role="alert">{error}</p>)
                           }

                           {
                               activeManagerSection === "profile" && fleetManagerProfile !== null && (<FleetManagerProfile profile={fleetManagerProfile}/>)
                           }

                           {
                               activeManagerSection === "vehicles" && (<FleetVehicles vehicles={fleetVehicles} drivers={fleetDrivers}onTrackVehicle={setManagerTrackingVehicle} onVehicleUpdated={replaceFleetVehicleInList} onVehicleCreated={addFleetVehicleToList}/>)
                           }

                           {
                               activeManagerSection === "drivers" && ( <FleetDrivers drivers={fleetDrivers} vehicles={fleetVehicles} onTrackVehicle={setManagerTrackingVehicle}/>)
                           }
                           {activeManagerSection === "history" && (<PositionHistory vehicles={fleetVehicles} drivers={fleetDrivers}/>)}

                           {/* Το tracking παραμένει ορατό ανεξάρτητα από την επιλεγμένη ενότητα. */}
                           {
                               managerTrackingVehicle !== null && (
                                   <div className="user-tracking">
                                       <h3>GPS Tracking: {managerTrackingVehicle.plate_number}</h3>
                                       <p>Device IMEI: {managerTrackingVehicle.device_imei}</p>

                                       {
                                           managerLatestPosition !== null && (
                                               <>
                                                   <LatestPosition position={managerLatestPosition}/>
                                                   <LiveMap position={managerLatestPosition}/>
                                               </>
                                           )
                                       }

                                       {
                                           managerLatestPosition === null && (<p>No position received yet.</p>)
                                       }

                                       <button type="button" onClick={() => setManagerTrackingVehicle(null)}> Close Tracking </button>
                                   </div>
                               )
                           }

                       </div>
                   </div>
               </section>
           )}
            {
                hasRole("admin") && (<AdminDashboard/>)
            }
        </main>
    </div>
  );
}

export default App;