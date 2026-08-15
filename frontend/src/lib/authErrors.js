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
};

export function describeFirebaseError(error) {
  return (
    FIREBASE_MESSAGES[error?.code] ??
    "Something went wrong signing you in. Please try again."
  );
}

export function describeApiError(error) {
  if (error?.status === 429) {
    return "You've requested too many codes recently. Please wait a while and try again.";
  }
  if (error?.status === 401) {
    return "Your session has expired. Please sign in again.";
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
