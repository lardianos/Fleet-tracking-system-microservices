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

      // Αποθηκεύουμε το IMEI ώστε να χρησιμοποιηθεί
      // στη συνέχεια από το WebSocket subscription.
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