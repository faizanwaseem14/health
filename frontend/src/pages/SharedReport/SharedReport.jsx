import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { LoadingScreen } from "../../components/LoadingScreen/LoadingScreen";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import { apiFetch } from "../../lib/apiClient";
import { describeResultFlag } from "../../lib/resultStatus";
import styles from "./SharedReport.module.css";

const ShieldIcon = () => (
  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" aria-hidden="true">
    <path
      d="M12 3.25 19.75 6.5V11.5C19.75 16.2 16.55 20.1 12 21.25C7.45 20.1 4.25 16.2 4.25 11.5V6.5L12 3.25Z"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinejoin="round"
    />
    <path
      d="M8.5 12 10.9 14.4 15.7 9.6"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

function SafetyFooter() {
  return (
    <p className={styles.safetyFooter}>
      <ShieldIcon />
      <span>
        This is a read-only summary shared from HealthVault. It describes what each test
        measures and what the report says — it never diagnoses or gives medical advice.
      </span>
    </p>
  );
}

function formatDate(iso) {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function formatValue(value, unit) {
  return unit ? `${value} ${unit}` : value;
}

/**
 * The doctor-facing view of a share link: GET /public/shares/:token,
 * no login, no HealthVault account - and never anything beyond exactly
 * what the share was scoped to (see app/sharing/service.py on the
 * backend). Every failure reason (unknown token, revoked, expired,
 * over its view limit) renders the SAME "no longer available" state -
 * deliberately never distinguishing which, matching the backend's own
 * uniform 404 for all four.
 */
export function SharedReport() {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [isUnavailable, setIsUnavailable] = useState(false);
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    apiFetch(`/public/shares/${token}`)
      .then((response) => {
        if (!cancelled) setData(response.data);
      })
      .catch((error) => {
        if (cancelled) return;
        if (error?.status === 404) {
          setIsUnavailable(true);
        } else {
          setLoadError("We couldn't load this shared report right now.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  if (isUnavailable) {
    return (
      <div className={`container ${styles.wrap}`}>
        <div className={styles.unavailable}>
          <h1 className={styles.heading}>This link is no longer available</h1>
          <p className={styles.intro}>
            It may have expired, been revoked by the person who shared it, or already been
            viewed the maximum number of times. Ask them to share a new link if you still
            need to see this report.
          </p>
          <Link to="/" className={styles.homeLink}>
            Go to HealthVault ↗
          </Link>
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className={`container ${styles.wrap}`}>
        <h1 className={styles.heading}>We couldn't load this shared report</h1>
        <p className={styles.intro}>{loadError}</p>
        <SafetyFooter />
      </div>
    );
  }

  if (data === null) {
    return <LoadingScreen message="Loading shared report…" />;
  }

  const reportName = data.report.display_name || data.report.original_filename;
  const reportDate = formatDate(data.report.report_date || data.report.created_at);

  return (
    <div className={`container ${styles.wrap}`}>
      <div className={styles.header}>
        <h1 className={styles.heading}>{reportName}</h1>
        {reportDate && <p className={styles.intro}>Report date: {reportDate}</p>}
        <p className={styles.sharedNote}>Shared with you via HealthVault, read-only.</p>
      </div>

      {data.results.length === 0 ? (
        <p className={styles.intro}>No test values were shared on this link.</p>
      ) : (
        <div className={styles.tableScroll}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Test</th>
                <th scope="col">Value</th>
                <th scope="col">Unit</th>
                <th scope="col">Reference range</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((result) => {
                const badge = describeResultFlag(result.flag);
                return (
                  <tr key={result.id}>
                    <th scope="row">{result.canonical_test_name || result.raw_test_name}</th>
                    <td className={styles.value}>{result.value}</td>
                    <td>{result.unit || "—"}</td>
                    <td>{result.reference_range_text || "—"}</td>
                    <td>
                      {badge ? (
                        <StatusBadge tone={badge.tone} label={badge.label} />
                      ) : (
                        <span className={styles.noStatus}>—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* A mobile-friendly restatement of the same table, one card per
          test - the table above stays the authoritative markup (sortable/
          scannable on a desktop), this is what a narrow phone screen
          actually shows (see .table/.cardList's max-width swap in CSS). */}
      <ul className={styles.cardList}>
        {data.results.map((result) => {
          const badge = describeResultFlag(result.flag);
          return (
            <li key={result.id} className={styles.card}>
              <div className={styles.cardHeader}>
                <span className={styles.cardTestName}>
                  {result.canonical_test_name || result.raw_test_name}
                </span>
                {badge ? (
                  <StatusBadge tone={badge.tone} label={badge.label} />
                ) : (
                  <span className={styles.noStatus}>—</span>
                )}
              </div>
              <span className={styles.cardValue}>
                {formatValue(result.value, result.unit)}
              </span>
              {result.reference_range_text && (
                <span className={styles.cardRange}>
                  Reference range: {formatValue(result.reference_range_text, result.unit)}
                </span>
              )}
            </li>
          );
        })}
      </ul>

      <SafetyFooter />
    </div>
  );
}
