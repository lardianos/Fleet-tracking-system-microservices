import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import keycloak from "../keycloak";
import { expireSession, handleTokenExpiration, isSessionExpired, readAccessToken, refreshTokenForUserAction } from "./session";

interface AuthContextType {
    username: string;
    roles: string[];
    token: string;
    hasRole: (role: string) => boolean;
    logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
    children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
    const [token, setToken] = useState(readAccessToken);
    const [sessionExpired, setSessionExpired] = useState(false);
    const [sessionError, setSessionError] = useState("");

    let username = "";
    let rolesText = "[]";

    const tokenData = keycloak.tokenParsed;

    if (tokenData !== undefined) {
        if (typeof tokenData.preferred_username === "string") {
            username = tokenData.preferred_username;
        }

        if (tokenData.realm_access !== undefined) {
            rolesText = JSON.stringify(tokenData.realm_access.roles);
        }
    }

    // Η λίστα παραμένει σταθερή όταν ανανεώνεται το token χωρίς αλλαγή ρόλων.
    const roles = useMemo<string[]>(() => JSON.parse(rolesText), [rolesText]);

    const hasRole = useCallback((role: string): boolean => {
        return roles.includes(role);
    }, [roles]);

    const logout = useCallback(() => {
        void keycloak.logout({ redirectUri: window.location.origin });
    }, []);

    useEffect(() => {
        let isActive = true;

        function updateTokenState() {
            setToken(readAccessToken());
            setSessionError("");
        }

        function showExpiredSession() {
            setSessionExpired(true);
            setToken("");
        }

        function renewSessionAfterAction(event: Event) {
            const target = event.target;

            if (!(target instanceof Element)) return;

            // Το Logout και η νέα σύνδεση δεν χρειάζονται ανανέωση token.
            if (target.closest("[data-skip-session-refresh]") !== null) return;

            let isUserAction = false;

            if (event.type === "click") {
                isUserAction = target.closest(
                    "button, a[href], input[type='button'], input[type='submit'], input[type='checkbox'], input[type='radio']"
                ) !== null;
            } else if (event.type === "change") {
                isUserAction = target.matches("select, input, textarea");
            } else if (event.type === "submit") {
                isUserAction = target instanceof HTMLFormElement;
            }

            if (!isUserAction) return;

            // Δεν αφήνουμε ενέργεια να εκτελεστεί μετά τη λήξη λόγω αδράνειας.
            if (isSessionExpired()) {
                event.preventDefault();
                event.stopImmediatePropagation();
                expireSession();
                return;
            }

            void refreshTokenForUserAction().catch((error: unknown) => {
                if (!isActive) return;

                console.error("Could not renew session after user action:", error);
                setSessionError("Could not renew your session. Check your connection and try again.");
            });
        }

        const previousExpirationCallback = keycloak.onTokenExpired;
        keycloak.onTokenExpired = handleTokenExpiration;

        window.addEventListener("session-token-updated", updateTokenState);
        window.addEventListener("session-expired", showExpiredSession);

        // Χρησιμοποιούμε capture ώστε η ανανέωση να ξεκινά πριν από το onClick του React.
        window.addEventListener("click", renewSessionAfterAction, true);
        window.addEventListener("change", renewSessionAfterAction, true);
        window.addEventListener("submit", renewSessionAfterAction, true);

        if (isSessionExpired()) {
            expireSession();
            showExpiredSession();
        }

        return () => {
            isActive = false;
            keycloak.onTokenExpired = previousExpirationCallback;

            window.removeEventListener("session-token-updated", updateTokenState);
            window.removeEventListener("session-expired", showExpiredSession);
            window.removeEventListener("click", renewSessionAfterAction, true);
            window.removeEventListener("change", renewSessionAfterAction, true);
            window.removeEventListener("submit", renewSessionAfterAction, true);
        };
    }, []);

    function signInAgain() {
        // Καθαρίζουμε την τοπική ταυτότητα πριν ξεκινήσει νέα σύνδεση.
        keycloak.clearToken();
        void keycloak.login({ redirectUri: window.location.origin });
    }

    if (sessionExpired) {
        return (
            <div className="app-content">
                <p role="alert">Your session has expired due to inactivity. Please sign in again.</p>
                <button type="button" data-skip-session-refresh onClick={signInAgain}> Sign in again </button>
            </div>
        );
    }

    return (
        <AuthContext.Provider value={{ username, roles, token, hasRole, logout }}>
            {sessionError !== "" && (<p role="alert">{sessionError}</p>)}
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const authContext = useContext(AuthContext);

    if (authContext === undefined) {
        throw new Error("useAuth must be used inside AuthProvider");
    }

    return authContext;
}