import { useState } from "react";
import { useAuth } from "./auth/AuthContext";
import "./App.css";
import LatestPosition from "./components/LatestPosition";
import type { Position } from "./types/Position";
import LiveMap from "./components/LiveMap";

function App() {
  const { username, roles, hasRole, logout, token } = useAuth();

  const [latestPosition, setLatestPosition] = useState<Position | null>(null);
  // const [latestPosition, setLatestPosition] = useState<any>(null);
  // const [latestPosition, setLatestPosition] = useState<unknown>(null);
  const [error, setError] = useState("");

  async function loadLatestPosition() {
    try {
      setError("");

      const response = await fetch(
        "http://localhost:8004/api/v1/vehicles/123456789012345/latest-position",
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      const data = await response.json();

      setLatestPosition(data);
    } catch (requestError) {
      console.error("Failed to load latest position:", requestError);
      setError("Failed to load latest position.");
    }
  }

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

            <button onClick={loadLatestPosition}>
              Load latest position
            </button>

            {error && <p>{error}</p>}

            {latestPosition !== null && (
                <>
                    <LatestPosition position={latestPosition} />
                    <LiveMap position={latestPosition} />
                </>

            )}
              {/*{latestPosition !== null && (*/}
              {/*  <pre>*/}
              {/*      {JSON.stringify(latestPosition, null, 2)}*/}
              {/*  </pre>*/}
              {/*)}*/}
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