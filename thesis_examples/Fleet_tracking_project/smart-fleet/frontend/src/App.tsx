import { useAuth } from "./auth/AuthContext";
import "./App.css";

function App() {
  const { username, roles, hasRole, logout } = useAuth();

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
            <p>Driver functionality will be displayed here.</p>
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