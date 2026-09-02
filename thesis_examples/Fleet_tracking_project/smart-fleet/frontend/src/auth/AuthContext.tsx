import { createContext, useContext, type ReactNode } from "react";
import keycloak from "../keycloak";

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
  const username = keycloak.tokenParsed?.preferred_username ?? "";

  const roles = keycloak.tokenParsed?.realm_access?.roles ?? [];

  const token = keycloak.token ?? "";

  function hasRole(role: string): boolean {
    return roles.includes(role);
  }

  function logout() {
    keycloak.logout({
      redirectUri: window.location.origin,
    });
  }

  return (
    <AuthContext.Provider
      value={{
        username,
        roles,
        token,
        hasRole,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const authContext = useContext(AuthContext);

  if (!authContext) {
    throw new Error("useAuth must be used inside AuthProvider");
  }

  return authContext;
}