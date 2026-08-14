import { createContext, useContext, useMemo, useState } from "react";

const AuthContext = createContext(null);

/**
 * Placeholder for real auth (phone OTP login comes in a later step of
 * Day 3). Nothing here talks to the backend yet — this just gives the
 * rest of the app a stable shape to build against (`user`,
 * `isAuthenticated`, `signOut`) so screens built next don't need to be
 * rewired later.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: user !== null,
      // Real sign-in will replace this; kept here only so callers have
      // a stable function reference to build against.
      signOut: () => setUser(null),
    }),
    [user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside an <AuthProvider>.");
  }
  return context;
}
