import { Button } from "../../components/Button/Button";
import { Card } from "../../components/Card/Card";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import { useAuth } from "../../context/AuthContext";
import styles from "./Home.module.css";

/**
 * A deliberately minimal "you're in" screen - upload and results
 * screens don't exist yet, so this just honestly confirms sign-in
 * worked, rather than pretending to be a finished dashboard.
 */
export function Home() {
  const { backendUser, primaryProfile, signOut } = useAuth();

  return (
    <div className={`container ${styles.wrap}`}>
      <Card className={styles.card}>
        <StatusBadge tone="good" label="Signed in" />
        <h1 className={styles.heading}>
          Welcome{primaryProfile ? `, ${primaryProfile.full_name}` : ""}.
        </h1>
        <p className={styles.detail}>
          Signed in with {backendUser?.phone_number ?? "your phone number"}.
        </p>
        <p className={styles.note}>
          Uploading reports and viewing results are coming in the next part
          of HealthVault — for now, this confirms your account is set up.
        </p>
        <Button variant="secondary" onClick={signOut}>
          Sign out
        </Button>
      </Card>
    </div>
  );
}
