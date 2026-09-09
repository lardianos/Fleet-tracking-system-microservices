import { useEffect, useState } from "react";
import { useAuth } from "./auth/AuthContext";
import "./App.css";
import LatestPosition from "./components/LatestPosition";
import type { Position } from "./types/Position";
import LiveMap from "./components/LiveMap";

function App() {
  const { username, roles, hasRole, logout, token } = useAuth();

  // Κρατάει την τελευταία γνωστή θέση του οχήματος.
  // Αρχικά είναι null μέχρι να ολοκληρωθεί το πρώτο REST request.
  const [latestPosition, setLatestPosition] = useState<Position | null>(null);

  // Κρατάει πιθανό μήνυμα σφάλματος από το REST request.
  const [error, setError] = useState("");

  const [vehicleImei, setVehicleImei] = useState<string | null>(null);

  // Κρατάει τα στοιχεία του authenticated driver.
  const [driverProfile, setDriverProfile] = useState<DriverProfile | null>(null);

  // Κρατάει ολόκληρο το vehicle ώστε να μπορούμε
  // να εμφανίσουμε και τα στοιχεία του στο dashboard.

  const [assignedVehicle, setAssignedVehicle] = useState<Vehicle | null>(null);

  interface Vehicle {
    id: string;
    plate_number: string;
    brand: string;
    model: string;
    year: number;
    device_imei: string;
    driver_id: string | null;
    fleet_id: string | null;
    status: string;
  }

  interface DriverProfile {
    id: string;
    driver_id: string;
    keycloak_user_id: string;
    first_name: string;
    last_name: string;
    date_of_birth: string | null;
    identity_card_number: string | null;
    tax_id: string | null;
    phone_number: string | null;
    email: string | null;
    license_number: string | null;
    license_category: string | null;
    license_expiry_date: string | null;
    hire_date: string | null;
    fleet_id: string | null;
    department_id: string | null;
    status: string;
  }


  // async function loadLatestPosition() {
  //   try {
  //     setError("");
  //
  //     const response = await fetch(
  //       "http://localhost:8004/api/v1/vehicles/123456789012345/latest-position",
  //       {
  //         headers: {
  //           Authorization: `Bearer ${token}`,
  //         },
  //       }
  //     );
  //
  //     if (!response.ok) {
  //       throw new Error(`Request failed with status ${response.status}`);
  //     }
  //
  //     const data: Position = await response.json();
  //
  //     setLatestPosition(data);
  //   } catch (requestError) {
  //     console.error("Failed to load latest position:", requestError);
  //     setError("Failed to load latest position.");
  //   }
  // }
  //
  // // Το REST request εκτελείται μία φορά όταν φορτώνει το component.
  // // Έτσι παίρνουμε την τελευταία γνωστή θέση πριν ξεκινήσουν
  // // αργότερα οι live ενημερώσεις μέσω WebSocket.
  // // useEffect(() => {
  // //   loadLatestPosition();
  // // }, []);
useEffect(() => {
  async function loadDriverProfile() {
    try {
      setError("");

      // Ζητάμε το Driver Profile του authenticated χρήστη.
      // Το API Gateway βρίσκει το σωστό profile από το JWT sub.
      const response = await fetch(
        "http://localhost:8004/api/v1/drivers/me",
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error(
          `Failed to load driver profile: ${response.status}`
        );
      }

      const profile: DriverProfile = await response.json();

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
        "http://localhost:8004/api/v1/drivers/me/vehicles",
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error(
          `Failed to load driver vehicles: ${response.status}`
        );
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

  if (token) {
    loadMyVehicle();
  }
}, [token]);
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
      <div>
        <h3>My Profile</h3>

        <p>Name: {driverProfile.first_name} {driverProfile.last_name}</p>
        <p>Email: {driverProfile.email ?? "-"}</p>
        <p>Phone: {driverProfile.phone_number ?? "-"}</p>
        <p>Driver ID: {driverProfile.driver_id}</p>
        <p>License: {driverProfile.license_number ?? "-"}</p>
        <p>License Category: {driverProfile.license_category ?? "-"}</p>
        <p>License Expiry: {driverProfile.license_expiry_date ?? "-"}</p>
        <p>Status: {driverProfile.status}</p>
        <p>Tax ID: {driverProfile.tax_id}</p>

      </div>
    )}

    {assignedVehicle && (
      <div>
        <h3>My Vehicle</h3>

        <p>Plate: {assignedVehicle.plate_number}</p>
        <p>Brand: {assignedVehicle.brand}</p>
        <p>Model: {assignedVehicle.model}</p>
        <p>Year: {assignedVehicle.year}</p>
        <p>Status: {assignedVehicle.status}</p>
        <p>IMEI: {assignedVehicle.device_imei}</p>
      </div>
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
            <p>Fleet management functionality will be displayed here.</p>
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