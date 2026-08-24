import { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "../../components/Button/Button";
import { Card } from "../../components/Card/Card";
import { useAuth } from "../../context/AuthContext";
import { describeApiError } from "../../lib/authErrors";
import styles from "./Account.module.css";

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

function DangerZone() {
  return (
    <Card className={styles.card}>
      <h2 className={styles.cardHeading}>Danger zone</h2>
      <div className={styles.settingRow}>
        <div>
          <p className={styles.settingLabel}>Delete account</p>
          <p className={styles.settingHint}>
            Not available yet in the app. Contact support if you need your account and
            data removed.
          </p>
        </div>
        <Button type="button" variant="ghost" size="md" disabled>
          Delete account
        </Button>
      </div>
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
