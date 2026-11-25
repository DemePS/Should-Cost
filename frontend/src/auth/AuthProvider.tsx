/**
 * v1 auth stub — no sign-in (see docs/auth-later.md). Mirrors the backend's
 * should_cost/auth.py: a single insertion point (`useAuth()`) every screen that would
 * eventually need the signed-in user calls, so adding Entra ID later means replacing
 * this provider's internals, not every call site.
 */
import { createContext, useContext, type ReactNode } from "react";

interface AuthState {
  isAuthenticated: true; // always true in v1 — AUTH_ENABLED=false backend-side too
  displayName: string;
}

const AuthContext = createContext<AuthState>({ isAuthenticated: true, displayName: "Anonymous (no sign-in in v1)" });

export function AuthProvider({ children }: { children: ReactNode }) {
  // Later: wrap with an Entra ID provider (e.g. @azure/msal-react) here, and derive
  // the real AuthState from its account info instead of this constant.
  return <AuthContext.Provider value={{ isAuthenticated: true, displayName: "Anonymous (no sign-in in v1)" }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  return useContext(AuthContext);
}
