import { RecaptchaVerifier, signInWithPhoneNumber, signInWithPopup } from "firebase/auth";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Button } from "../../components/Button/Button";
import { Card } from "../../components/Card/Card";
import { Input } from "../../components/Input/Input";
import { useAuth } from "../../context/AuthContext";
import { ApiError, apiFetch } from "../../lib/apiClient";
import {
  describeApiError,
  describeFirebaseError,
  logFirebaseAuthError,
} from "../../lib/authErrors";
import { auth, googleProvider, isFirebaseConfigured } from "../../lib/firebase";
import { toE164 } from "../../lib/phone";
import { withTimeout } from "../../lib/withTimeout";
import styles from "./Login.module.css";

const STEP_PHONE = "phone";
const STEP_CODE = "code";
// Generous, but finite - signInWithPhoneNumber depends on a
// third-party script (Google's reCAPTCHA) that can stall silently
// (no thrown error) if it's blocked or slow, instead of failing fast.
// Past this, we show a clear error instead of leaving the button
// stuck on "Sending code..." forever.
const FIREBASE_CALL_TIMEOUT_MS = 20_000;

// The official Google "G" mark, used exactly as Google's branding
// guidelines require for a sign-in button (unrecolored, on a neutral
// background) - not a HealthVault-styled icon.
function GoogleGlyph() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 20 20"
      aria-hidden="true"
      focusable="false"
    >
      <path
        fill="#4285F4"
        d="M19.6 10.23c0-.68-.06-1.36-.18-2.05H10v3.87h5.38a4.6 4.6 0 0 1-2 3.02v2.5h3.23c1.9-1.75 2.99-4.33 2.99-7.34Z"
      />
      <path
        fill="#34A853"
        d="M10 20c2.7 0 4.96-.89 6.62-2.42l-3.23-2.5c-.9.6-2.06.96-3.39.96-2.6 0-4.8-1.76-5.59-4.12H1.06v2.59A10 10 0 0 0 10 20Z"
      />
      <path
        fill="#FBBC05"
        d="M4.41 11.92A5.99 5.99 0 0 1 4.09 10c0-.67.11-1.31.32-1.92V5.49H1.06A10 10 0 0 0 0 10c0 1.61.39 3.14 1.06 4.51l3.35-2.59Z"
      />
      <path
        fill="#EA4335"
        d="M10 3.96c1.47 0 2.79.51 3.83 1.5l2.87-2.87C14.95.99 12.7 0 10 0A10 10 0 0 0 1.06 5.49l3.35 2.59C5.2 5.72 7.4 3.96 10 3.96Z"
      />
    </svg>
  );
}

export function Login() {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [step, setStep] = useState(STEP_PHONE);
  const [phoneInput, setPhoneInput] = useState("");
  const [codeInput, setCodeInput] = useState("");
  const [confirmationResult, setConfirmationResult] = useState(null);
  const [sentToNumber, setSentToNumber] = useState("");
  const [phoneError, setPhoneError] = useState(null);
  const [codeError, setCodeError] = useState(null);
  const [isSending, setIsSending] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);

  // Google sign-in is the primary method - phone OTP is kept working
  // underneath (so it's easy to re-promote later) but tucked behind
  // this toggle instead of shown by default.
  const [showPhoneForm, setShowPhoneForm] = useState(false);
  const [isGoogleSigningIn, setIsGoogleSigningIn] = useState(false);
  const [googleError, setGoogleError] = useState(null);

  const recaptchaContainerRef = useRef(null);
  const recaptchaVerifierRef = useRef(null);

  useEffect(() => {
    if (isAuthenticated) {
      const redirectTo = location.state?.from ?? "/home";
      navigate(redirectTo, { replace: true });
    }
  }, [isAuthenticated, location.state, navigate]);

  useEffect(() => {
    return () => {
      recaptchaVerifierRef.current?.clear();
    };
  }, []);

  // Builds a brand-new verifier for every send attempt, rather than
  // reusing one across attempts: a verifier that has already rendered
  // (or already failed) can silently interfere with a retry, and
  // explicitly awaiting render() here means any reCAPTCHA-side setup
  // failure surfaces as a thrown error right here - not as a mysterious
  // stall inside signInWithPhoneNumber.
  async function getRecaptchaVerifier() {
    recaptchaVerifierRef.current?.clear();
    recaptchaVerifierRef.current = new RecaptchaVerifier(
      auth,
      recaptchaContainerRef.current,
      { size: "invisible" },
    );
    await recaptchaVerifierRef.current.render();
    return recaptchaVerifierRef.current;
  }

  async function handleGoogleSignIn() {
    setGoogleError(null);
    setIsGoogleSigningIn(true);
    try {
      // No withTimeout here on purpose: unlike the phone flow, the wait
      // here is however long the person takes to pick an account in the
      // popup, not a network call that can silently stall - Firebase
      // itself already rejects promptly if the popup is blocked or
      // closed (auth/popup-blocked, auth/popup-closed-by-user).
      await signInWithPopup(auth, googleProvider);
      // AuthContext's onAuthStateChanged listener picks this up and
      // verifies it with our backend in the background - navigating now
      // is safe, the destination route shows a brief loading state
      // until that finishes (see RequireAuth).
      navigate("/home", { replace: true });
    } catch (error) {
      logFirebaseAuthError("google-sign-in", error);
      setGoogleError(describeFirebaseError(error));
    } finally {
      setIsGoogleSigningIn(false);
    }
  }

  async function handleSendCode(event) {
    event.preventDefault();
    setPhoneError(null);

    const e164Phone = toE164(phoneInput);
    if (!e164Phone) {
      setPhoneError("Enter a valid phone number, like (555) 123-4567.");
      return;
    }

    setIsSending(true);
    try {
      await apiFetch("/auth/otp/request", {
        method: "POST",
        body: { phone_number: e164Phone },
      });

      const verifier = await getRecaptchaVerifier();
      const result = await withTimeout(
        signInWithPhoneNumber(auth, e164Phone, verifier),
        FIREBASE_CALL_TIMEOUT_MS,
      );

      setConfirmationResult(result);
      setSentToNumber(e164Phone);
      setCodeInput("");
      setStep(STEP_CODE);
    } catch (error) {
      if (!(error instanceof ApiError)) {
        logFirebaseAuthError("send-code", error);
      }
      setPhoneError(
        error instanceof ApiError ? describeApiError(error) : describeFirebaseError(error),
      );
      // A failed attempt means the recaptcha widget was already used up -
      // drop it so the next attempt builds a fresh one.
      recaptchaVerifierRef.current?.clear();
      recaptchaVerifierRef.current = null;
    } finally {
      setIsSending(false);
    }
  }

  async function handleVerifyCode(event) {
    event.preventDefault();
    setCodeError(null);

    if (!/^\d{6}$/.test(codeInput.trim())) {
      setCodeError("Enter the 6-digit code we sent you.");
      return;
    }

    setIsVerifying(true);
    try {
      await withTimeout(
        confirmationResult.confirm(codeInput.trim()),
        FIREBASE_CALL_TIMEOUT_MS,
      );
      // AuthContext's onAuthStateChanged listener picks this up and
      // verifies it with our backend in the background - navigating
      // now is safe, the destination route shows a brief loading
      // state until that finishes (see RequireAuth).
      navigate("/home", { replace: true });
    } catch (error) {
      logFirebaseAuthError("verify-code", error);
      setCodeError(describeFirebaseError(error));
    } finally {
      setIsVerifying(false);
    }
  }

  function handleUseDifferentNumber() {
    setStep(STEP_PHONE);
    setCodeInput("");
    setCodeError(null);
    setConfirmationResult(null);
  }

  if (!isFirebaseConfigured) {
    return (
      <div className={`container ${styles.wrap}`}>
        <Card className={styles.card}>
          <h1 className={styles.heading}>Sign-in isn't set up yet</h1>
          <p className={styles.intro}>
            HealthVault needs a Firebase configuration to send sign-in codes.
            Add your Firebase project's values to <code>frontend/.env</code>{" "}
            and restart the app — see <code>frontend/README.md</code> for the
            exact steps.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className={`container ${styles.wrap}`}>
      <Card className={styles.card}>
        <h1 className={styles.heading}>Sign in to HealthVault</h1>

        <div className={styles.form}>
          <p className={styles.intro}>
            Sign in with your Google account — no password to remember.
          </p>
          <button
            type="button"
            className={styles.googleButton}
            onClick={handleGoogleSignIn}
            disabled={isGoogleSigningIn}
          >
            <GoogleGlyph />
            {isGoogleSigningIn ? "Signing in…" : "Continue with Google"}
          </button>
          {googleError && <p className={styles.googleError}>{googleError}</p>}
        </div>

        {!showPhoneForm && (
          <button
            type="button"
            className={styles.phoneToggle}
            onClick={() => setShowPhoneForm(true)}
          >
            Sign in with a phone number instead
          </button>
        )}

        {showPhoneForm && (
          <div className={styles.phoneSection}>
            <div className={styles.divider} role="separator" aria-label="or" />

            {step === STEP_PHONE && (
              <form onSubmit={handleSendCode} className={styles.form} noValidate>
                <p className={styles.intro}>
                  Enter your phone number and we'll text you a one-time code.
                </p>
                <Input
                  label="Phone number"
                  type="tel"
                  autoComplete="tel"
                  inputMode="tel"
                  placeholder="(555) 123-4567"
                  value={phoneInput}
                  onChange={(event) => setPhoneInput(event.target.value)}
                  error={phoneError}
                  disabled={isSending}
                />
                <Button type="submit" variant="secondary" disabled={isSending}>
                  {isSending ? "Sending code…" : "Send code"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setShowPhoneForm(false)}
                  disabled={isSending}
                >
                  Back to Google sign-in
                </Button>
              </form>
            )}

            {step === STEP_CODE && (
              <form onSubmit={handleVerifyCode} className={styles.form} noValidate>
                <p className={styles.intro}>
                  We sent a 6-digit code to {sentToNumber}. Enter it below to
                  finish signing in.
                </p>
                <Input
                  label="6-digit code"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  placeholder="123456"
                  maxLength={6}
                  value={codeInput}
                  onChange={(event) =>
                    setCodeInput(event.target.value.replace(/\D/g, "").slice(0, 6))
                  }
                  error={codeError}
                  disabled={isVerifying}
                />
                <Button type="submit" variant="secondary" disabled={isVerifying}>
                  {isVerifying ? "Checking code…" : "Verify code"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={handleUseDifferentNumber}
                  disabled={isVerifying}
                >
                  Use a different number
                </Button>
              </form>
            )}
          </div>
        )}
      </Card>

      {/* Invisible reCAPTCHA anchor - never shown to the reader, just
          required by Firebase to send the code (phone sign-in only). */}
      <div ref={recaptchaContainerRef} />
    </div>
  );
}
