import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Button } from "../../components/Button/Button";
import { Card } from "../../components/Card/Card";
import { LoadingScreen } from "../../components/LoadingScreen/LoadingScreen";
import { ProcessingAnimation } from "../../components/ProcessingAnimation/ProcessingAnimation";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import { useAuth } from "../../context/AuthContext";
import { describeApiError } from "../../lib/authErrors";
import { describeReportStatus, isReportStatusTerminal } from "../../lib/reportStatus";
import styles from "./Processing.module.css";

const POLL_INTERVAL_MS = 3000;

/**
 * Watches one report's processing job until it reaches a final state.
 * Safe to leave and come back to: every mount just re-fetches the
 * report's current status from the backend (the job itself runs
 * server-side regardless of whether anyone's looking at this screen).
 */
export function Processing() {
  const { reportId } = useParams();
  const { authFetch } = useAuth();
  const navigate = useNavigate();

  const [report, setReport] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [retryError, setRetryError] = useState(null);
  const pollTimerRef = useRef(null);
  const isMountedRef = useRef(true);

  const fetchStatus = useCallback(async () => {
    try {
      const response = await authFetch(`/reports/${reportId}`);
      setReport(response.data);
      setLoadError(null);
      return response.data;
    } catch (error) {
      setLoadError(describeApiError(error));
      return null;
    }
  }, [authFetch, reportId]);

  // Polls until the job reaches a terminal state, then stops on its
  // own - reused for both the initial load and after a retry, since
  // retrying puts the job back into "queued" and needs the same
  // watch-until-done loop. Both call sites share isMountedRef so a
  // retry-then-immediately-navigate-away can't leave a stray timer
  // calling setState after this screen is gone.
  const startPolling = useCallback(async () => {
    async function poll() {
      const data = await fetchStatus();
      if (!isMountedRef.current) return;
      if (data && !isReportStatusTerminal(data.job_status)) {
        pollTimerRef.current = setTimeout(poll, POLL_INTERVAL_MS);
      }
    }
    poll();
  }, [fetchStatus]);

  useEffect(() => {
    isMountedRef.current = true;
    startPolling();
    return () => {
      isMountedRef.current = false;
      clearTimeout(pollTimerRef.current);
    };
  }, [startPolling]);

  async function handleRetry() {
    setIsRetrying(true);
    setRetryError(null);
    try {
      await authFetch(`/reports/${reportId}/retry`, { method: "POST" });
      clearTimeout(pollTimerRef.current);
      startPolling();
    } catch (error) {
      setRetryError(describeApiError(error));
    } finally {
      setIsRetrying(false);
    }
  }

  if (loadError && !report) {
    return (
      <div className={`container ${styles.wrap}`}>
        <Card className={styles.card}>
          <h1 className={styles.heading}>We couldn't find that report</h1>
          <p className={styles.intro}>{loadError}</p>
          <Button variant="secondary" onClick={() => navigate("/home")}>
            Back to Home
          </Button>
        </Card>
      </div>
    );
  }

  if (!report) {
    return <LoadingScreen message="Checking on your report…" />;
  }

  const { tone, label } = describeReportStatus(report);
  const jobStatus = report.job_status;
  const stillWorking = jobStatus === "queued" || jobStatus === "processing" || jobStatus == null;

  return (
    <div className={`container ${styles.wrap}`}>
      <Card className={styles.card}>
        <div className={styles.header}>
          <h1 className={styles.heading}>{report.original_filename}</h1>
          <StatusBadge tone={tone} label={label} />
        </div>

        {stillWorking && <ProcessingAnimation />}

        {jobStatus === "review_required" && (
          <div className={styles.stateSection}>
            <p className={styles.intro}>
              A couple of things on this report need a closer look before
              we show you results — that's normal for a scan that's hard
              to read clearly, and doesn't mean anything is wrong with
              your file. We'll let you know once it's ready.
            </p>
            <Button variant="secondary" onClick={() => navigate("/home")}>
              Back to Home
            </Button>
          </div>
        )}

        {jobStatus === "completed" && (
          <div className={styles.stateSection}>
            <p className={styles.intro}>
              Your report has been processed. Here's what we found.
            </p>
            <Button variant="primary" onClick={() => navigate(`/reports/${reportId}/results`)}>
              View results
            </Button>
          </div>
        )}

        {jobStatus === "failed" && (
          <div className={styles.stateSection}>
            <p className={styles.intro}>
              Something went wrong while processing this report. Your
              file is safe — nothing was lost — and you can try
              processing it again.
            </p>
            {report.job_error_message && (
              <p className={styles.technicalDetail}>{report.job_error_message}</p>
            )}
            {retryError && <p className={styles.retryError}>{retryError}</p>}
            <Button variant="primary" onClick={handleRetry} disabled={isRetrying}>
              {isRetrying ? "Retrying…" : "Try again"}
            </Button>
          </div>
        )}

        {stillWorking && (
          <Link to="/home" className={styles.homeLink}>
            Safe to leave — this will keep processing in the background
          </Link>
        )}
      </Card>
    </div>
  );
}
