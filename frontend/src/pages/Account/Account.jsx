import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "../../components/Button/Button";
import { Card } from "../../components/Card/Card";
import { Input } from "../../components/Input/Input";
import { useAuth } from "../../context/AuthContext";
import { describeApiError } from "../../lib/authErrors";
import styles from "./Account.module.css";

const DELETE_CONFIRMATION_WORD = "DELETE";

function formatDateOfBirth(iso) {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function ProfileDetails() {
  const { backendUser, primaryProfile } = useAuth();

  const rows = [
    { label: "Name", value: primaryProfile?.full_name },
    { label: "Date of birth", value: formatDateOfBirth(primaryProfile?.date_of_birth) },
    { label: "Sex", value: primaryProfile?.sex },
    { label: "Blood type", value: primaryProfile?.blood_type },
    { label: "Phone", value: backendUser?.phone_number },
    { label: "Email", value: backendUser?.email },
  ].filter((row) => row.value);

  return (
    <Card className={styles.card}>
      <h2 className={styles.cardHeading}>Profile</h2>
      <dl className={styles.detailList}>
        {rows.map((row) => (
          <div key={row.label} className={styles.detailRow}>
            <dt className={styles.detailLabel}>{row.label}</dt>
            <dd className={styles.detailValue}>{row.value}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

/**
 * A one-time-reveal backup recovery code (app/auth/recovery.py on the
 * backend) - lets someone sign back in if they ever lose access to
 * their phone. Generating a new code invalidates any earlier one, so
 * this asks for confirmation before it does that a second time.
 */
function RecoveryCodeSetting() {
  const { authFetch } = useAuth();
  const [revealedCode, setRevealedCode] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [confirming, setConfirming] = useState(false);

  async function handleGenerate() {
    setIsGenerating(true);
    setError(null);
    try {
      const response = await authFetch("/auth/recovery/generate", { method: "POST" });
      setRevealedCode(response.data.recovery_code);
      setConfirming(false);
    } catch (generateError) {
      setError(describeApiError(generateError));
    } finally {
      setIsGenerating(false);
    }
  }

  return (
    <Card className={styles.card}>
      <h2 className={styles.cardHeading}>Account settings</h2>
      <div className={styles.settingRow}>
        <div>
          <p className={styles.settingLabel}>Backup recovery code</p>
          <p className={styles.settingHint}>
            Use this to sign back in if you ever lose access to your phone.
          </p>
        </div>
        {!confirming && !revealedCode && (
          <Button
            type="button"
            variant="secondary"
            size="md"
            onClick={() => setConfirming(true)}
          >
            Generate code
          </Button>
        )}
      </div>

      {confirming && (
        <div className={styles.confirmBox}>
          <p className={styles.confirmText}>
            Generating a new code makes any earlier recovery code stop working. Continue?
          </p>
          <div className={styles.confirmActions}>
            <Button
              type="button"
              variant="primary"
              size="md"
              onClick={handleGenerate}
              disabled={isGenerating}
            >
              {isGenerating ? "Generating…" : "Yes, generate"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="md"
              onClick={() => setConfirming(false)}
              disabled={isGenerating}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}

      {revealedCode && (
        <div className={styles.codeBox}>
          <p className={styles.codeLabel}>
            Save this now - it's shown only once and won't be shown again.
          </p>
          <code className={styles.code}>{revealedCode}</code>
        </div>
      )}

      {error && <p className={styles.error}>{error}</p>}
    </Card>
  );
}

/**
 * Permanently deletes the account and everything under it - see
 * DELETE /auth/me on the backend for the full cascade (every profile,
 * report, result, correction, explanation, OCR evidence, job, and
 * share link this account owns). Typing the confirmation word is
 * deliberately required, not just a second click - this is the one
 * action in the whole app that can't be undone by contacting support,
 * since there's nothing left to restore.
 */
function DangerZone() {
  const { authFetch, signOut } = useAuth();
  const navigate = useNavigate();
  const [isConfirming, setIsConfirming] = useState(false);
  const [confirmationText, setConfirmationText] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState(null);

  const canConfirm = confirmationText.trim() === DELETE_CONFIRMATION_WORD;

  function startConfirming() {
    setConfirmationText("");
    setError(null);
    setIsConfirming(true);
  }

  async function handleDelete(event) {
    event.preventDefault();
    if (!canConfirm) return;

    setIsDeleting(true);
    setError(null);
    try {
      await authFetch("/auth/me", { method: "DELETE" });
      await signOut();
      navigate("/", { replace: true });
    } catch (deleteError) {
      setError(describeApiError(deleteError));
      setIsDeleting(false);
    }
  }

  return (
    <Card className={styles.card}>
      <h2 className={styles.cardHeading}>Danger zone</h2>
      <div className={styles.settingRow}>
        <div>
          <p className={styles.settingLabel}>Delete account</p>
          <p className={styles.settingHint}>
            Permanently deletes your account and everything in it - every profile,
            report, and result. This can't be undone.
          </p>
        </div>
        {!isConfirming && (
          <Button type="button" variant="ghost" size="md" onClick={startConfirming}>
            Delete account
          </Button>
        )}
      </div>

      {isConfirming && (
        <form className={styles.deleteConfirmBox} onSubmit={handleDelete} noValidate>
          <p className={styles.confirmText}>
            This deletes your account and every report, result, and correction under it,
            right now, for good - there is no way to get it back afterward. Type{" "}
            <strong>{DELETE_CONFIRMATION_WORD}</strong> to confirm.
          </p>
          <Input
            label={`Type ${DELETE_CONFIRMATION_WORD} to confirm`}
            value={confirmationText}
            onChange={(event) => setConfirmationText(event.target.value)}
            disabled={isDeleting}
            autoComplete="off"
          />
          {error && <p className={styles.error}>{error}</p>}
          <div className={styles.confirmActions}>
            <Button
              type="submit"
              variant="accent"
              size="md"
              disabled={!canConfirm || isDeleting}
            >
              {isDeleting ? "Deleting…" : "Permanently delete my account"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="md"
              onClick={() => setIsConfirming(false)}
              disabled={isDeleting}
            >
              Cancel
            </Button>
          </div>
        </form>
      )}
    </Card>
  );
}

/**
 * Account-only content: who you are, and account-level settings and
 * sign-out - never the upload flow or anything about a specific report
 * (that's Home.jsx and History.jsx).
 */
export function Account() {
  const { signOut } = useAuth();

  return (
    <div className={`container ${styles.wrap}`}>
      <div className={styles.page}>
        <h1 className={styles.heading}>My account</h1>

        <ProfileDetails />
        <RecoveryCodeSetting />
        <DangerZone />

        <Button variant="secondary" onClick={signOut} className={styles.signOutButton}>
          Sign out
        </Button>

        <Link to="/home" className={styles.homeLink}>
          Back to Home
        </Link>
      </div>
    </div>
  );
}
