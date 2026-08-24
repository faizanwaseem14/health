import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "../../components/Button/Button";
import { Input } from "../../components/Input/Input";
import { LoadingScreen } from "../../components/LoadingScreen/LoadingScreen";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import { useAuth } from "../../context/AuthContext";
import { describeApiError } from "../../lib/authErrors";
import { describeReportStatus } from "../../lib/reportStatus";
import styles from "./History.module.css";

function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/**
 * One report: its name (or renamed label), upload date, and processing
 * status, all as a single link into that report - plus Rename/Delete,
 * which sit outside the link so tapping them never triggers navigation.
 */
function ReportHistoryRow({ report, onRename, onDelete }) {
  const displayName = report.display_name || report.original_filename;
  const { tone, label } = describeReportStatus(report);
  const destination =
    report.job_status === "completed"
      ? `/reports/${report.id}/results`
      : `/reports/${report.id}`;

  const [isRenaming, setIsRenaming] = useState(false);
  const [nameDraft, setNameDraft] = useState(displayName);
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);

  function startRenaming() {
    setNameDraft(displayName);
    setError(null);
    setIsRenaming(true);
  }

  async function handleSaveRename(event) {
    event.preventDefault();
    const trimmed = nameDraft.trim();
    if (!trimmed || trimmed === displayName) {
      setIsRenaming(false);
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      await onRename(report.id, trimmed);
      setIsRenaming(false);
    } catch (renameError) {
      setError(describeApiError(renameError));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleConfirmDelete() {
    setIsSaving(true);
    setError(null);
    try {
      await onDelete(report.id);
      // No finally-reset here on success: the row is about to be
      // removed from the list entirely by the parent.
    } catch (deleteError) {
      setError(describeApiError(deleteError));
      setIsSaving(false);
    }
  }

  return (
    <li className={styles.row}>
      <Link to={destination} className={styles.rowMain}>
        <span className={styles.name}>{displayName}</span>
        <span className={styles.meta}>
          <span className={styles.date}>{formatDate(report.created_at)}</span>
          <StatusBadge tone={tone} label={label} />
        </span>
      </Link>

      {isRenaming && (
        <form className={styles.inlineForm} onSubmit={handleSaveRename} noValidate>
          <Input
            label="Report name"
            value={nameDraft}
            onChange={(event) => setNameDraft(event.target.value)}
            disabled={isSaving}
          />
          <div className={styles.actions}>
            <Button type="submit" variant="primary" size="md" disabled={isSaving}>
              {isSaving ? "Saving…" : "Save"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="md"
              onClick={() => setIsRenaming(false)}
              disabled={isSaving}
            >
              Cancel
            </Button>
          </div>
        </form>
      )}

      {isConfirmingDelete && (
        <div className={styles.inlineForm}>
          <p className={styles.confirmText}>
            Delete this report and everything extracted from it? This can't be undone.
          </p>
          <div className={styles.actions}>
            <Button
              type="button"
              variant="accent"
              size="md"
              onClick={handleConfirmDelete}
              disabled={isSaving}
            >
              {isSaving ? "Deleting…" : "Yes, delete"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="md"
              onClick={() => setIsConfirmingDelete(false)}
              disabled={isSaving}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}

      {!isRenaming && !isConfirmingDelete && (
        <div className={styles.actions}>
          <Button type="button" variant="ghost" size="md" onClick={startRenaming}>
            Rename
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="md"
            onClick={() => setIsConfirmingDelete(true)}
          >
            Delete
          </Button>
        </div>
      )}

      {error && <p className={styles.error}>{error}</p>}
    </li>
  );
}

/**
 * Every report the signed-in profile has uploaded, most recent first -
 * open one to jump back into it, or rename/delete it from here without
 * leaving the list.
 */
export function History() {
  const { primaryProfile, authFetch } = useAuth();
  const [reports, setReports] = useState(null);
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    if (!primaryProfile) return undefined;
    let cancelled = false;

    authFetch(`/profiles/${primaryProfile.id}/reports`)
      .then((response) => {
        if (!cancelled) setReports(response.data);
      })
      .catch((error) => {
        if (!cancelled) setLoadError(describeApiError(error));
      });

    return () => {
      cancelled = true;
    };
  }, [authFetch, primaryProfile]);

  async function handleRename(reportId, displayName) {
    const response = await authFetch(`/reports/${reportId}`, {
      method: "PATCH",
      body: { display_name: displayName },
    });
    setReports((current) =>
      current.map((report) => (report.id === reportId ? response.data : report)),
    );
  }

  async function handleDelete(reportId) {
    await authFetch(`/reports/${reportId}`, { method: "DELETE" });
    setReports((current) => current.filter((report) => report.id !== reportId));
  }

  if (loadError) {
    return (
      <div className={`container ${styles.wrap}`}>
        <h1 className={styles.heading}>Report history</h1>
        <p className={styles.error}>{loadError}</p>
        <Link to="/home" className={styles.homeLink}>
          Back to Home
        </Link>
      </div>
    );
  }

  if (reports === null) {
    return <LoadingScreen message="Loading your reports…" />;
  }

  return (
    <div className={`container ${styles.wrap}`}>
      <h1 className={styles.heading}>Report history</h1>
      <p className={styles.intro}>Every report you've uploaded, most recent first.</p>

      {reports.length === 0 ? (
        <p className={styles.note}>
          You haven't uploaded any reports yet.{" "}
          <Link to="/upload" className={styles.inlineLink}>
            Upload one
          </Link>
          .
        </p>
      ) : (
        <ul className={styles.list}>
          {reports.map((report) => (
            <ReportHistoryRow
              key={report.id}
              report={report}
              onRename={handleRename}
              onDelete={handleDelete}
            />
          ))}
        </ul>
      )}

      <Link to="/home" className={styles.homeLink}>
        Back to Home
      </Link>
    </div>
  );
}
