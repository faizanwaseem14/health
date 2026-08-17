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
import { getAuth } from "firebase/auth";

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

// DEV-ONLY: asks Firebase to skip the reCAPTCHA challenge for phone
// sign-in against a "phone number for testing" configured in Firebase
// console (console -> Authentication -> Sign-in method -> Phone).
//
// This is Firebase's own documented flag for exactly that case - but
// it's a REQUEST, not a guarantee: if the underlying Firebase project
// is enrolled in Google's newer reCAPTCHA-based phone-auth abuse
// protection (increasingly the default for projects created after
// 2023) and that reCAPTCHA integration itself isn't fully configured,
// the backend can still reject the request before this flag ever gets
// consulted - that shows up as the SDK logging "Failed to initialize
// reCAPTCHA Enterprise config..." and a 400 from
// identitytoolkit.googleapis.com's sendVerificationCode, regardless of
// this flag. See src/pages/Login/Login.jsx's error handling, which
// logs Firebase's actual error code/message to the console specifically
// so that case is diagnosable instead of a bare "400".
//
// import.meta.env.DEV is Vite's own "am I running `npm run dev`" flag
// - it's `false` (and this whole branch is dead-code-eliminated) in a
// production build, so this can never end up disabled for real users.
if (isFirebaseConfigured && import.meta.env.DEV) {
  auth.settings.appVerificationDisabledForTesting = true;
}
