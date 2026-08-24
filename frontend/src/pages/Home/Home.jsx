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
      <span className={styles.reportName}>
        {report.display_name || report.original_filename}
      </span>
      <StatusBadge tone={tone} label={label} />
    </Link>
  );
}

const TrendsIcon = () => (
  <svg viewBox="0 0 20 20" width="18" height="18" fill="none" aria-hidden="true">
    <path
      d="M3 15.5 8 9l3.5 3.5L17 5"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const HistoryIcon = () => (
  <svg viewBox="0 0 20 20" width="18" height="18" fill="none" aria-hidden="true">
    <path
      d="M10 5.5v5l3 2M17 10a7 7 0 1 1-2.05-4.95"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path d="M17 4v3.5h-3.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

/**
 * The signed-in landing page: uploading a new report is the app's
 * primary action, so it's the first and largest thing here - not
 * tucked behind account settings (see Account.jsx for profile/sign-out/
 * account-only content). Quick access to history and trends sits right
 * below it, then a short preview of recent reports.
 */
export function Home() {
  const { primaryProfile, authFetch } = useAuth();
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

  const latestCompletedReport = reports?.find(
    (report) => report.job_status === "completed",
  );
  const recentReports = reports?.slice(0, 5) ?? [];

  return (
    <div className={`container ${styles.wrap}`}>
      <div className={styles.page}>
        <div>
          <h1 className={styles.heading}>
            Welcome{primaryProfile ? `, ${primaryProfile.full_name}` : ""}.
          </h1>
          <p className={styles.subheading}>
            Upload a lab report to get started, or pick up where you left off below.
          </p>
        </div>

        <Card className={styles.uploadCard}>
          <Button
            as={Link}
            to="/upload"
            variant="primary"
            size="lg"
            className={styles.uploadButton}
          >
            Upload a report
          </Button>
          <p className={styles.uploadHint}>
            A PDF or photo of any lab report - HealthVault extracts and explains the
            results for you.
          </p>
        </Card>

        <div className={styles.quickLinks}>
          <Link to="/history" className={styles.quickLink}>
            <HistoryIcon />
            <span>Report history</span>
          </Link>
          {latestCompletedReport ? (
            <Link
              to={`/reports/${latestCompletedReport.id}/trends`}
              className={styles.quickLink}
            >
              <TrendsIcon />
              <span>View trends</span>
            </Link>
          ) : (
            <span className={`${styles.quickLink} ${styles.quickLinkDisabled}`}>
              <TrendsIcon />
              <span>Trends (after your first report finishes)</span>
            </span>
          )}
        </div>

        <div className={styles.reportList}>
          <div className={styles.reportListHeader}>
            <h2 className={styles.reportListHeading}>Recent reports</h2>
            {reports?.length > 0 && (
              <Link to="/history" className={styles.historyLink}>
                See full history ↗
              </Link>
            )}
          </div>

          {reports === null && !reportsError && (
            <p className={styles.note}>Loading your reports…</p>
          )}
          {reportsError && <p className={styles.note}>{reportsError}</p>}
          {reports?.length === 0 && (
            <p className={styles.note}>
              You haven't uploaded any reports yet — start with the button above.
            </p>
          )}
          {recentReports.map((report) => (
            <ReportRow key={report.id} report={report} />
          ))}
        </div>
      </div>
    </div>
  );
}
