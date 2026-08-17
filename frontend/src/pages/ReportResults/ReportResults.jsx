import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Button } from "../../components/Button/Button";
import { Card } from "../../components/Card/Card";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import { useAuth } from "../../context/AuthContext";
import styles from "./ReportResults.module.css";

/**
 * Placeholder for the results screen (a later group builds the real
 * one: test values, plain-language explanations, trust indicators).
 * Exists now so "View results" from the processing screen leads
 * somewhere real instead of a dead end.
 */
export function ReportResults() {
  const { reportId } = useParams();
  const { authFetch } = useAuth();
  const [filename, setFilename] = useState(null);

  useEffect(() => {
    let cancelled = false;
    authFetch(`/reports/${reportId}`)
      .then((response) => {
        if (!cancelled) setFilename(response.data.original_filename);
      })
      .catch(() => {
        // Filename is a nice-to-have for this placeholder - if it
        // can't load, the generic heading below still makes sense.
      });
    return () => {
      cancelled = true;
    };
  }, [authFetch, reportId]);

  return (
    <div className={`container ${styles.wrap}`}>
      <Card className={styles.card}>
        <StatusBadge tone="good" label="Processed" />
        <h1 className={styles.heading}>
          {filename ? `Results for ${filename}` : "Your report is ready"}
        </h1>
        <p className={styles.intro}>
          The results screen — your test values, what they mean in plain
          language, and how trustworthy each reading is — is coming in
          the next part of HealthVault. Your report has already been
          processed and is saved safely.
        </p>
        <Button as={Link} to="/home" variant="secondary">
          Back to Home
        </Button>
      </Card>
    </div>
  );
}
