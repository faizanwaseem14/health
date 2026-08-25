import { useEffect, useState } from "react";
import { Button } from "../../components/Button/Button";
import { Input } from "../../components/Input/Input";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import { useAuth } from "../../context/AuthContext";
import { describeApiError } from "../../lib/authErrors";
import { describeShareStatus } from "../../lib/shareStatus";
import styles from "./SharePanel.module.css";

const EXPIRY_OPTIONS = [
  { days: 3, label: "3 days" },
  { days: 7, label: "7 days" },
  { days: 14, label: "14 days" },
  { days: 30, label: "30 days" },
  { days: 90, label: "90 days" },
];

function formatDateTime(iso) {
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function shareUrlFor(token) {
  return `${window.location.origin}/shared/${token}`;
}

function ViewsLabel({ share }) {
  if (share.max_views == null) {
    return <span>{share.access_count} view{share.access_count === 1 ? "" : "s"}</span>;
  }
  return (
    <span>
      {share.access_count} / {share.max_views} views
    </span>
  );
}

/** One existing share: status, expiry, views, revoke, and an
 * expand-on-demand access history (view timestamps). */
function ShareRow({ share, onRevoke }) {
  const { authFetch } = useAuth();
  const [isRevoking, setIsRevoking] = useState(false);
  const [isConfirmingRevoke, setIsConfirmingRevoke] = useState(false);
  const [error, setError] = useState(null);
  const [accesses, setAccesses] = useState(null);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);

  const { tone, label } = describeShareStatus(share.status);
  const isRevocable = share.status === "active";

  async function handleRevoke() {
    setIsRevoking(true);
    setError(null);
    try {
      await onRevoke(share.id);
    } catch (revokeError) {
      setError(describeApiError(revokeError));
    } finally {
      setIsRevoking(false);
      setIsConfirmingRevoke(false);
    }
  }

  async function toggleHistory() {
    if (isHistoryOpen) {
      setIsHistoryOpen(false);
      return;
    }
    setIsHistoryOpen(true);
    if (accesses === null) {
      try {
        const response = await authFetch(`/shares/${share.id}/accesses`);
        setAccesses(response.data);
      } catch {
        setAccesses([]);
      }
    }
  }

  return (
    <li className={styles.shareRow}>
      <div className={styles.shareRowMain}>
        <div className={styles.shareRowInfo}>
          <StatusBadge tone={tone} label={label} />
          <span className={styles.shareMeta}>
            Expires {formatDateTime(share.expires_at)} · <ViewsLabel share={share} />
          </span>
        </div>
        <div className={styles.shareRowActions}>
          <Button
            type="button"
            variant="ghost"
            size="md"
            onClick={toggleHistory}
          >
            {isHistoryOpen ? "Hide access history" : "Access history"}
          </Button>
          {isRevocable && !isConfirmingRevoke && (
            <Button
              type="button"
              variant="ghost"
              size="md"
              onClick={() => setIsConfirmingRevoke(true)}
            >
              Revoke
            </Button>
          )}
        </div>
      </div>

      {isConfirmingRevoke && (
        <div className={styles.confirmBox}>
          <p className={styles.confirmText}>
            Revoke this link? Anyone with it will be denied immediately - this can't be
            undone.
          </p>
          <div className={styles.confirmActions}>
            <Button
              type="button"
              variant="accent"
              size="md"
              onClick={handleRevoke}
              disabled={isRevoking}
            >
              {isRevoking ? "Revoking…" : "Yes, revoke"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="md"
              onClick={() => setIsConfirmingRevoke(false)}
              disabled={isRevoking}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}

      {error && <p className={styles.error}>{error}</p>}

      {isHistoryOpen && (
        <div className={styles.history}>
          {accesses === null && <p className={styles.historyNote}>Loading…</p>}
          {accesses?.length === 0 && (
            <p className={styles.historyNote}>Nobody has opened this link yet.</p>
          )}
          {accesses && accesses.length > 0 && (
            <ul className={styles.historyList}>
              {accesses.map((access, index) => (
                <li key={index} className={styles.historyItem}>
                  {formatDateTime(access.accessed_at)}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </li>
  );
}

/**
 * Share management for one report: create a new share link (whole
 * report, or a chosen subset of its results), see every share already
 * created for it with live status, revoke one, and check who's opened
 * it. All the actual security guarantees (unguessable token, atomic
 * expiry/revocation/view-limit enforcement) live on the backend - see
 * app/sharing/service.py - this is purely the management UI for them.
 */
export function SharePanel({ reportId, results }) {
  const { authFetch } = useAuth();
  const [shares, setShares] = useState(null);
  const [loadError, setLoadError] = useState(null);

  const [isCreating, setIsCreating] = useState(false);
  const [expiresInDays, setExpiresInDays] = useState(7);
  const [maxViews, setMaxViews] = useState("");
  const [isScoped, setIsScoped] = useState(false);
  const [selectedResultIds, setSelectedResultIds] = useState(() => new Set());
  const [createError, setCreateError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [justCreatedUrl, setJustCreatedUrl] = useState(null);
  const [copyNote, setCopyNote] = useState(null);

  useEffect(() => {
    let cancelled = false;
    authFetch(`/reports/${reportId}/shares`)
      .then((response) => {
        if (!cancelled) setShares(response.data);
      })
      .catch((error) => {
        if (!cancelled) setLoadError(describeApiError(error));
      });
    return () => {
      cancelled = true;
    };
  }, [authFetch, reportId]);

  function toggleResultSelected(resultId) {
    setSelectedResultIds((current) => {
      const next = new Set(current);
      if (next.has(resultId)) {
        next.delete(resultId);
      } else {
        next.add(resultId);
      }
      return next;
    });
  }

  async function handleRevoke(shareId) {
    const response = await authFetch(`/shares/${shareId}`, { method: "DELETE" });
    setShares((current) =>
      current.map((share) => (share.id === shareId ? response.data : share)),
    );
  }

  async function handleCreate(event) {
    event.preventDefault();
    setCreateError(null);

    if (isScoped && selectedResultIds.size === 0) {
      setCreateError("Choose at least one result to share, or share the whole report.");
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await authFetch(`/reports/${reportId}/shares`, {
        method: "POST",
        body: {
          expires_in_days: expiresInDays,
          max_views: maxViews.trim() ? Number(maxViews.trim()) : null,
          result_ids: isScoped ? [...selectedResultIds] : null,
        },
      });
      setShares((current) => [response.data, ...(current ?? [])]);
      setJustCreatedUrl(shareUrlFor(response.data.share_token));
      setIsCreating(false);
      setMaxViews("");
      setIsScoped(false);
      setSelectedResultIds(new Set());
    } catch (error) {
      setCreateError(describeApiError(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCopy(url) {
    try {
      await navigator.clipboard.writeText(url);
      setCopyNote("Link copied.");
    } catch {
      setCopyNote(null);
    }
  }

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <h2 className={styles.heading}>Share with a doctor</h2>
        {!isCreating && (
          <Button type="button" variant="primary" size="md" onClick={() => setIsCreating(true)}>
            New share link
          </Button>
        )}
      </div>
      <p className={styles.intro}>
        Anyone with the link can see a read-only summary - no HealthVault account needed.
        You control how long it lasts and how many times it can be opened, and you can
        revoke it at any time.
      </p>

      {justCreatedUrl && (
        <div className={styles.newLinkBox}>
          <p className={styles.newLinkLabel}>Share this link:</p>
          <div className={styles.newLinkRow}>
            <code className={styles.newLinkUrl}>{justCreatedUrl}</code>
            <Button
              type="button"
              variant="secondary"
              size="md"
              onClick={() => handleCopy(justCreatedUrl)}
            >
              Copy
            </Button>
          </div>
          {copyNote && <p className={styles.copyNote}>{copyNote}</p>}
        </div>
      )}

      {isCreating && (
        <form className={styles.form} onSubmit={handleCreate} noValidate>
          <div className={styles.field}>
            <label htmlFor="share-expiry" className={styles.label}>
              Link expires after
            </label>
            <select
              id="share-expiry"
              className={styles.select}
              value={expiresInDays}
              onChange={(event) => setExpiresInDays(Number(event.target.value))}
              disabled={isSubmitting}
            >
              {EXPIRY_OPTIONS.map((option) => (
                <option key={option.days} value={option.days}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <Input
            label="View limit"
            hint="Optional - leave blank for unlimited views"
            type="number"
            min="1"
            inputMode="numeric"
            value={maxViews}
            onChange={(event) => setMaxViews(event.target.value)}
            disabled={isSubmitting}
          />

          <label className={styles.checkboxRow}>
            <input
              type="checkbox"
              checked={isScoped}
              onChange={(event) => setIsScoped(event.target.checked)}
              disabled={isSubmitting}
            />
            <span>Share only specific results, not the whole report</span>
          </label>

          {isScoped && (
            <ul className={styles.resultList}>
              {results.map((result) => (
                <li key={result.id}>
                  <label className={styles.checkboxRow}>
                    <input
                      type="checkbox"
                      checked={selectedResultIds.has(result.id)}
                      onChange={() => toggleResultSelected(result.id)}
                      disabled={isSubmitting}
                    />
                    <span>{result.canonical_test_name || result.raw_test_name}</span>
                  </label>
                </li>
              ))}
            </ul>
          )}

          {createError && <p className={styles.error}>{createError}</p>}

          <div className={styles.formActions}>
            <Button type="submit" variant="primary" size="md" disabled={isSubmitting}>
              {isSubmitting ? "Creating…" : "Create share link"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="md"
              onClick={() => setIsCreating(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
          </div>
        </form>
      )}

      <div className={styles.list}>
        <h3 className={styles.listHeading}>Active and past shares</h3>
        {loadError && <p className={styles.error}>{loadError}</p>}
        {shares === null && !loadError && <p className={styles.note}>Loading…</p>}
        {shares?.length === 0 && (
          <p className={styles.note}>No share links created for this report yet.</p>
        )}
        {shares?.length > 0 && (
          <ul className={styles.shareList}>
            {shares.map((share) => (
              <ShareRow key={share.id} share={share} onRevoke={handleRevoke} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
