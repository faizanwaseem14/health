import { RecaptchaVerifier, signInWithPhoneNumber } from "firebase/auth";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Button } from "../../components/Button/Button";
import { Card } from "../../components/Card/Card";
import { Input } from "../../components/Input/Input";
import { useAuth } from "../../context/AuthContext";
import { ApiError, apiFetch } from "../../lib/apiClient";
import { describeApiError, describeFirebaseError } from "../../lib/authErrors";
import { auth, isFirebaseConfigured } from "../../lib/firebase";
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

  function getRecaptchaVerifier() {
    if (!recaptchaVerifierRef.current) {
      recaptchaVerifierRef.current = new RecaptchaVerifier(
        auth,
        recaptchaContainerRef.current,
        { size: "invisible" },
      );
    }
    return recaptchaVerifierRef.current;
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

      const verifier = getRecaptchaVerifier();
      const result = await withTimeout(
        signInWithPhoneNumber(auth, e164Phone, verifier),
        FIREBASE_CALL_TIMEOUT_MS,
      );

      setConfirmationResult(result);
      setSentToNumber(e164Phone);
      setCodeInput("");
      setStep(STEP_CODE);
    } catch (error) {
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

        {step === STEP_PHONE && (
          <form onSubmit={handleSendCode} className={styles.form} noValidate>
            <p className={styles.intro}>
              Enter your phone number and we'll text you a one-time code — no
              password to remember.
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
            <Button type="submit" variant="primary" disabled={isSending}>
              {isSending ? "Sending code…" : "Send code"}
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
            <Button type="submit" variant="primary" disabled={isVerifying}>
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
      </Card>

      {/* Invisible reCAPTCHA anchor - never shown to the reader, just
          required by Firebase to send the code. */}
      <div ref={recaptchaContainerRef} />
    </div>
  );
}
