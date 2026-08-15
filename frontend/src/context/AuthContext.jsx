import { onAuthStateChanged, signOut as firebaseSignOut } from "firebase/auth";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { auth, isFirebaseConfigured } from "../lib/firebase";
import { apiFetch } from "../lib/apiClient";

const AuthContext = createContext(null);

/**
 * The single source of truth for "who's signed in, and have they set
 * up a profile yet" - every screen that needs to know either of those
 * things reads it from here, instead of re-fetching it themselves.
 *
 * `status` moves through exactly these states:
 *   "loading"    - checking whether a previous session is still valid
 *   "signed-out" - no one is signed in
 *   "signed-in"  - a real person, verified by both Firebase AND our
 *                  own backend (see resolveSession below)
 */
export function AuthProvider({ children }) {
  const [status, setStatus] = useState("loading");
  const [firebaseUser, setFirebaseUser] = useState(null);
  const [backendUser, setBackendUser] = useState(null);
  const [profiles, setProfiles] = useState(null); // null = not loaded yet
  const [profilesLoading, setProfilesLoading] = useState(false);
  const [sessionError, setSessionError] = useState(null);

  // Attaches the current person's Firebase ID token to a backend call.
  // Every screen that needs to talk to the backend after login should
  // use this instead of calling apiFetch directly.
  const authFetch = useCallback(
    async (path, options = {}) => {
      if (!firebaseUser) {
        throw new Error("authFetch called with no signed-in user.");
      }
      const token = await firebaseUser.getIdToken();
      return apiFetch(path, {
        ...options,
        headers: { ...options.headers, Authorization: `Bearer ${token}` },
      });
    },
    [firebaseUser],
  );

  const refreshProfiles = useCallback(async () => {
    if (!firebaseUser) return;
    setProfilesLoading(true);
    try {
      const response = await apiFetch("/profiles", {
        headers: { Authorization: `Bearer ${await firebaseUser.getIdToken()}` },
      });
      setProfiles(response.data);
    } catch {
      // A profiles fetch failing shouldn't sign anyone out - screens
      // that need `profiles` handle it still being null.
      setProfiles(null);
    } finally {
      setProfilesLoading(false);
    }
  }, [firebaseUser]);

  useEffect(() => {
    if (!isFirebaseConfigured) {
      // frontend/.env is missing its Firebase values - nothing to
      // subscribe to. Login shows its own clear explanation rather
      // than the rest of the app silently pretending sign-in works.
      setStatus("signed-out");
      return undefined;
    }

    // Fires immediately with whatever session Firebase already has
    // persisted (or null), then again on every future sign-in/out.
    const unsubscribe = onAuthStateChanged(auth, async (nextFirebaseUser) => {
      setFirebaseUser(nextFirebaseUser);
      setSessionError(null);

      if (nextFirebaseUser === null) {
        setBackendUser(null);
        setProfiles(null);
        setStatus("signed-out");
        return;
      }

      try {
        const token = await nextFirebaseUser.getIdToken();
        // Verifies the token with our OWN backend and resolves/creates
        // the matching user row - a Firebase sign-in alone isn't
        // "signed in" as far as the rest of the app is concerned until
        // this succeeds too.
        const meResponse = await apiFetch("/auth/me", {
          headers: { Authorization: `Bearer ${token}` },
        });
        setBackendUser(meResponse.data);

        const profilesResponse = await apiFetch("/profiles", {
          headers: { Authorization: `Bearer ${token}` },
        });
        setProfiles(profilesResponse.data);

        setStatus("signed-in");
      } catch {
        setSessionError(
          "We couldn't reach HealthVault's server to finish signing you in.",
        );
        setStatus("signed-out");
      }
    });

    return unsubscribe;
  }, []);

  const signOut = useCallback(async () => {
    await firebaseSignOut(auth);
    // onAuthStateChanged above handles clearing state once Firebase
    // confirms the sign-out.
  }, []);

  const value = useMemo(
    () => ({
      status,
      isAuthenticated: status === "signed-in",
      firebaseUser,
      backendUser,
      profiles,
      profilesLoading,
      hasProfile: Array.isArray(profiles) && profiles.length > 0,
      primaryProfile: Array.isArray(profiles) && profiles.length > 0 ? profiles[0] : null,
      sessionError,
      authFetch,
      refreshProfiles,
      signOut,
    }),
    [
      status,
      firebaseUser,
      backendUser,
      profiles,
      profilesLoading,
      sessionError,
      authFetch,
      refreshProfiles,
      signOut,
    ],
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
