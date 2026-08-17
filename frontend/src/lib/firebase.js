/**
 * Initializes the Firebase client SDK for phone sign-in - config comes
 * from the frontend's own env file (see .env.example), never
 * hardcoded, so pointing this build at a different Firebase project is
 * a config change, not a code change.
 *
 * This is the CLIENT side of login: it talks to Firebase directly to
 * send/verify the OTP text message. The backend never sees the phone
 * number or the code - only the signed ID token this produces once
 * sign-in succeeds (see src/context/AuthContext.jsx).
 */
import { initializeApp } from "firebase/app";
import { GoogleAuthProvider, getAuth } from "firebase/auth";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

// Required for phone sign-in to work at all. If any of these are
// missing (a fresh checkout before frontend/.env is filled in, or a
// typo), we deliberately do NOT let Firebase throw and take down the
// whole app (including the public landing page, which has nothing to
// do with sign-in) - see isFirebaseConfigured below, checked by
// AuthContext and the Login screen before anything touches `auth`.
const REQUIRED_CONFIG_KEYS = ["apiKey", "authDomain", "projectId", "appId"];

export const isFirebaseConfigured = REQUIRED_CONFIG_KEYS.every((key) =>
  Boolean(firebaseConfig[key]),
);

export const auth = isFirebaseConfigured
  ? getAuth(initializeApp(firebaseConfig))
  : null;

// Google sign-in is the primary login method (see src/pages/Login/Login.jsx)
// - a single shared provider instance, same pattern as `auth` above.
// signInWithPopup/signInWithRedirect don't depend on reCAPTCHA at all,
// which is why this replaced phone OTP as the default: phone sign-in's
// reCAPTCHA step turned out to be unreliable on localhost depending on
// how a given Firebase project has reCAPTCHA Enterprise configured (see
// the phone sign-in code, kept in place but no longer the default).
export const googleProvider = isFirebaseConfigured ? new GoogleAuthProvider() : null;
