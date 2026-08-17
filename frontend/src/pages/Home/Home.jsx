import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "../../components/Button/Button";
import { Card } from "../../components/Card/Card";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import { useAuth } from "../../context/AuthContext";
import { describeReportStatus } from "../../lib/reportStatus";
import styles from "./Home.module.css";

function ReportRow({ report }) {
  const { tone, label } = describeReportStatus(report);
  const destination =
    report.job_status === "completed"
      ? `/reports/${report.id}/results`
      : `/reports/${report.id}`;

  return (
    <Link to={destination} className={styles.reportRow}>
      <span className={styles.reportName}>{report.original_filename}</span>
      <StatusBadge tone={tone} label={label} />
    </Link>
  );
}

/**
 * The signed-in home base: confirms who's signed in, is the entry
 * point for uploading a new report, and lists reports already
 * uploaded so someone can jump back into one that's still processing
 * (results screens come in a later group - see ReportResults.jsx).
 */
export function Home() {
  const { backendUser, primaryProfile, authFetch, signOut } = useAuth();
  const [reports, setReports] = useState(null);
  const [reportsError, setReportsError] = useState(null);

  useEffect(() => {
    if (!primaryProfile) return undefined;
    let cancelled = false;

    authFetch(`/profiles/${primaryProfile.id}/reports`)
      .then((response) => {
        if (!cancelled) setReports(response.data);
      })
      .catch(() => {
        if (!cancelled) setReportsError("We couldn't load your reports right now.");
      });

    return () => {
      cancelled = true;
    };
  }, [authFetch, primaryProfile]);

  return (
    <div className={`container ${styles.wrap}`}>
      <Card className={styles.card}>
        <StatusBadge tone="good" label="Signed in" />
        <h1 className={styles.heading}>
          Welcome{primaryProfile ? `, ${primaryProfile.full_name}` : ""}.
        </h1>
        <p className={styles.detail}>
          Signed in with {backendUser?.email ?? backendUser?.phone_number ?? "your account"}.
        </p>

        <Button as={Link} to="/upload" variant="primary" className={styles.uploadButton}>
          Upload a lab report
        </Button>

        {reports === null && !reportsError && (
          <p className={styles.note}>Loading your reports…</p>
        )}
        {reportsError && <p className={styles.note}>{reportsError}</p>}
        {reports?.length === 0 && (
          <p className={styles.note}>
            You haven't uploaded any reports yet — start with the button
            above.
          </p>
        )}
        {reports?.length > 0 && (
          <div className={styles.reportList}>
            <h2 className={styles.reportListHeading}>Your reports</h2>
            {reports.map((report) => (
              <ReportRow key={report.id} report={report} />
            ))}
          </div>
        )}

        <Button variant="secondary" onClick={signOut}>
          Sign out
        </Button>
      </Card>
    </div>
  );
}
