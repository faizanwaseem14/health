/**
 * Turns a Firebase Auth error or a backend ApiError into plain,
 * friendly wording - nobody using this app should ever see a raw
 * "auth/invalid-verification-code" or a bare HTTP status number.
 */
const FIREBASE_MESSAGES = {
  "auth/invalid-phone-number": "That doesn't look like a valid phone number.",
  "auth/missing-phone-number": "Enter a phone number first.",
  "auth/too-many-requests":
    "Too many attempts from this device. Please wait a while and try again.",
  "auth/captcha-check-failed":
    "We couldn't verify you're not a robot. Please try again.",
  "auth/invalid-verification-code": "That code didn't match — try again.",
  "auth/code-expired": "That code has expired. Send a new one and try again.",
  "auth/network-request-failed":
    "We couldn't reach the sign-in service. Check your connection and try again.",
  "auth/popup-closed-by-user": "Sign-in window closed before finishing. Try again.",
  "auth/cancelled-popup-request":
    "Another sign-in attempt is already in progress.",
  "auth/popup-blocked":
    "Your browser blocked the sign-in popup. Allow popups for this site and try again.",
  "auth/account-exists-with-different-credential":
    "An account already exists with this email using a different sign-in method.",
};

export function describeFirebaseError(error) {
  if (error?.name === "TimeoutError") {
    return "This is taking longer than expected. Check your internet connection and try again.";
  }

  const message =
    FIREBASE_MESSAGES[error?.code] ??
    "Something went wrong signing you in. Please try again.";

  // In dev builds only, append Firebase's own error code so it's
  // visible right on the screen - no need to open DevTools to see
  // WHICH unmapped error this was. Dead-code-eliminated in production
  // (import.meta.env.DEV is a literal `false` there), so a real user
  // never sees this.
  if (import.meta.env.DEV && error?.code) {
    return `${message} (${error.code})`;
  }
  return message;
}

/**
 * Logs everything Firebase actually attached to an auth error - the
 * plain-language message shown on screen deliberately hides this, but
 * a raw "400 Bad Request" from identitytoolkit.googleapis.com is
 * useless for debugging on its own. Call this from every catch block
 * around a Firebase Auth call, dev or not - it's a console.error, so
 * it costs nothing in production and never reaches the UI either way.
 */
export function logFirebaseAuthError(context, error) {
  // eslint-disable-next-line no-console
  console.error(`[HealthVault] Firebase Auth error (${context}):`, {
    code: error?.code,
    message: error?.message,
    customData: error?.customData,
    raw: error,
  });
}

export function describeApiError(error) {
  if (error?.status === 429) {
    return "You've requested too many codes recently. Please wait a while and try again.";
  }
  if (error?.status === 401) {
    return "Your session has expired. Please sign in again.";
  }
  if (error?.status === 413) {
    return "That file is too large — HealthVault accepts files up to 25MB.";
  }
  if (error?.status === 415) {
    return "That doesn't look like a photo or PDF HealthVault can read — try a JPEG, PNG, HEIC, or PDF file.";
  }
  if (error?.status === 409) {
    return "That can't be retried right now — it may have already finished or started again.";
  }
  if (typeof error?.body?.detail === "string") {
    // Only a small, known set of backend messages are written for a
    // reader, not a developer (see app/core/errors.py) - safe to show
    // as-is, but everything else falls back to the generic message
    // below rather than risk surfacing something technical.
    return "Something went wrong. Please try again.";
  }
  return "We couldn't reach HealthVault's server. Please try again.";
}
