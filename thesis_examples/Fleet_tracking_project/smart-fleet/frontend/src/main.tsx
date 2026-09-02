import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.tsx";
import keycloak from "./keycloak";
import { AuthProvider } from "./auth/AuthContext";

console.log("MAIN.TSX LOADED");

keycloak
  .init({
    onLoad: "login-required",
    pkceMethod: "S256",
  })
  .then((authenticated) => {
    if (!authenticated) {
      return;
    }

    console.log("Username:", keycloak.tokenParsed?.preferred_username);
    console.log("Roles:", keycloak.tokenParsed?.realm_access?.roles);

    createRoot(document.getElementById("root")!).render(
      <StrictMode>
        <AuthProvider>
          <App />
        </AuthProvider>
      </StrictMode>
    );
  })
  .catch((error) => {
    console.error("Keycloak initialization failed:", error);
  });