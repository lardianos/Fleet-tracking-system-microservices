import { useEffect, useState } from "react";
import { useAuth } from "./auth/AuthContext";
import "./App.css";

import type { Position } from "./types/Position";
import type { Vehicle } from "./types/Vehicle";
import type { DriverProfile as DriverProfileData } from "./types/DriverProfile";
import type {  FleetManagerProfile as FleetManagerProfileData } from "./types/FleetManagerProfile";
import LatestPosition from "./components/LatestPosition";
import LiveMap from "./components/LiveMap";
import DriverProfile from "./components/DriverProfile";
import MyVehicle from "./components/MyVehicle";
import FleetManagerProfile from "./components/FleetManagerProfile";
import FleetVehicles from "./components/FleetVehicles";
import FleetDrivers from "./components/FleetDrivers";

function App() {

    const { username, roles, hasRole, logout, token } = useAuth();
    // Κρατάει την τελευταία γνωστή θέση του οχήματος.
    // Αρχικά είναι null μέχρι να ολοκληρωθεί το πρώτο REST request.
    const [latestPosition, setLatestPosition] = useState<Position | null>(null);

    // Κρατάει πιθανό μήνυμα σφάλματος από το REST request.
    const [error, setError] = useState("");

    const [vehicleImei, setVehicleImei] = useState<string | null>(null);

    // Κρατάει τα στοιχεία του authenticated driver.
    const [driverProfile, setDriverProfile] = useState<DriverProfileData | null>(null);

    // Κρατάει ολόκληρο το vehicle ώστε να μπορούμε
    // να εμφανίσουμε και τα στοιχεία του στο dashboard.

    const [assignedVehicle, setAssignedVehicle] = useState<Vehicle | null>(null);

    // Κρατάει το business profile του authenticated Fleet Manager.
    const [fleetManagerProfile, setFleetManagerProfile] = useState< FleetManagerProfileData | null>(null);

    // Κρατάει όλα τα vehicles του fleet που διαχειρίζεται ο manager.
    const [fleetVehicles, setFleetVehicles] = useState<Vehicle[]>([]);

    // Κρατάει όλους τους drivers του fleet που διαχειρίζεται ο manager.
    const [fleetDrivers, setFleetDrivers] = useState<DriverProfileData[]>([]);

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
    async function loadMyVehicle() {
        try {

            // Καθαρίζουμε προηγούμενο μήνυμα σφάλματος.
            setError("");

            // Ζητάμε τα vehicles που αντιστοιχούν
            // στον authenticated χρήστη.
            const response = await fetch(
                "http://localhost:8004/api/v1/drivers/me/vehicles", { headers: { Authorization: `Bearer ${token}`, }, } );

            if (!response.ok) {
                throw new Error(
                    `Failed to load driver vehicles: ${response.status}`);
            }

            const vehicles: Vehicle[] = await response.json();

            // Αν δεν υπάρχει ανατεθειμένο vehicle,
            // δεν μπορούμε να ξεκινήσουμε live tracking.
            if (vehicles.length === 0) {
                setError("No vehicle is assigned to this driver.");
                return;
            }

            // Προς το παρόν χρησιμοποιούμε το πρώτο vehicle.
            const vehicle = vehicles[0];

            console.log("Assigned vehicle:", vehicle);

            // Αποθηκεύουμε ολόκληρο το vehicle για να εμφανίσουμε
            // τα στοιχεία του στο Driver Dashboard.
            setAssignedVehicle(vehicle);

            // Αποθηκεύουμε ξεχωριστά το IMEI γιατί χρησιμοποιείται
            // από το WebSocket subscription.
            setVehicleImei(vehicle.device_imei);
        } catch (requestError) {
          console.error("Failed to load assigned vehicle:", requestError);
          setError("Could not load assigned vehicle.");
        }
    }

    if (token && hasRole("driver")) {
        loadMyVehicle();
    }
}, [token, hasRole]);

useEffect(() => {
    if (!vehicleImei) {
        return;
    }
    // Δημιουργούμε μία WebSocket σύνδεση με το WebSocket Gateway.
    const socket = new WebSocket("ws://localhost:8003/ws");
    // Μόλις ανοίξει η σύνδεση, κάνουμε subscribe στο συγκεκριμένο όχημα.
    socket.onopen = () => {
    console.log("WebSocket connected");

    socket.send(
    JSON.stringify({
        action: "subscribe",
        imei: vehicleImei,
      })
    );
  };
    // Κάθε φορά που το WebSocket Gateway στέλνει νέο μήνυμα,
    // ελέγχουμε αν πρόκειται για live ενημέρωση θέσης.
    socket.onmessage = (event) => {
  const message = JSON.parse(event.data);

  console.log("WebSocket message:", message);

  // Η αρχική τελευταία γνωστή θέση έρχεται μαζί
  // με την επιβεβαίωση του subscription.
  if (message.type === "subscribed" && message.latest_position) {
    const position: Position = message.latest_position;
    setLatestPosition(position);
  }

  // Οι επόμενες θέσεις έρχονται live από το Kafka
  // μέσω του WebSocket Gateway.
  if (message.type === "position.updated") {
    const position: Position = message.data;
    setLatestPosition(position);
  }
};
    socket.onerror = (event) => {
    console.error("WebSocket error:", event);
  };
    socket.onclose = () => {
    console.log("WebSocket disconnected");
  };

    // Όταν το component καταστραφεί, κλείνουμε σωστά τη σύνδεση
    // ώστε να μη μείνει ανοιχτό WebSocket χωρίς λόγο.
    return () => {
        socket.close();
    };
}, [vehicleImei]);

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

  return (
    <div className="app">
      <header className="app-header">
          <div>
              <h1>Smart Fleet Tracking</h1>
              <p>Logged in as: {username}</p>
          </div>

          <button onClick={logout}>
              Logout
          </button>
      </header>

      <main className="app-content">
          <section>
              <h2>User access</h2>
              <p>Roles: {roles.join(", ")}</p>
          </section>

          {hasRole("driver") && (
              <section>
                  <h2>Driver Dashboard</h2>
                  {error && <p>{error}</p>}

                  {driverProfile && (
                      <DriverProfile profile={driverProfile} />
                  )}

                  {assignedVehicle && (
                      <MyVehicle vehicle={assignedVehicle} />
                  )}

                  {latestPosition !== null && (
                      <>
                          <LatestPosition position={latestPosition} />
                          <LiveMap position={latestPosition} />
                      </>
                  )}
              </section>
          )}
         {hasRole("fleet_manager") && (
  <section>
    <h2>Fleet Manager Dashboard</h2>

    {error && <p>{error}</p>}

    {fleetManagerProfile && (
      <FleetManagerProfile profile={fleetManagerProfile} />
    )}

    <FleetVehicles vehicles={fleetVehicles} />

    <FleetDrivers drivers={fleetDrivers} />
  </section>
)}
          {hasRole("admin") && (
              <section>
                <h2>Admin Dashboard</h2>
                <p>Administration functionality will be displayed here.</p>
              </section>
          )}
      </main>
    </div>
  );
}

export default App;