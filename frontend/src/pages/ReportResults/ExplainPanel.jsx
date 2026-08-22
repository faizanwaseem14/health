import { useEffect, useState } from "react";
import { Button } from "../../components/Button/Button";
import { Input } from "../../components/Input/Input";
import { describeApiError } from "../../lib/authErrors";
import styles from "./ExplainPanel.module.css";

function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatValue(value, unit) {
  return unit ? `${value} ${unit}` : value;
}

/**
 * The entire "tap to understand" surface, by design: what the test
 * measures (fetched on demand - the backend's own advice-language
 * guard keeps this to plain description, never diagnosis, interpretation,
 * or "what your result means"), and two actions. Nothing here ever
 * characterizes whether a value is good or bad - that's for a doctor.
 */
export function ExplainPanel({
  result,
  onRequestExplanation,
  isExplanationLoading,
  onCorrect,
}) {
  const [showTrendNote, setShowTrendNote] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(result.value);
  const [editReason, setEditReason] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  useEffect(() => {
    if (!result.explanation) {
      onRequestExplanation(result.id);
    }
    // Fetch once per result shown, not on every re-render this panel
    // happens to take (e.g. after saving a correction).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result.id]);

  function startEditing() {
    setEditValue(result.value);
    setEditReason("");
    setSaveError(null);
    setIsEditing(true);
  }

  async function handleSaveCorrection(event) {
    event.preventDefault();
    const trimmed = editValue.trim();
    if (!trimmed || trimmed === result.value) {
      setIsEditing(false);
      return;
    }

    setIsSaving(true);
    setSaveError(null);
    try {
      await onCorrect(result.id, {
        field_name: "value",
        new_value: trimmed,
        reason: editReason.trim() || undefined,
      });
      setIsEditing(false);
    } catch (error) {
      setSaveError(describeApiError(error));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className={styles.panel}>
      <h3 className={styles.heading}>What is this?</h3>
      {result.explanation ? (
        <p className={styles.explanation}>{result.explanation}</p>
      ) : isExplanationLoading ? (
        <p className={styles.loading}>Getting an explanation…</p>
      ) : (
        <p className={styles.unavailable}>
          We couldn't generate an explanation for this test right now.
        </p>
      )}

      <div className={styles.actions}>
        <Button type="button" variant="ghost" size="md" onClick={() => setShowTrendNote(true)}>
          See trend over time
        </Button>
        {!isEditing && (
          <Button type="button" variant="ghost" size="md" onClick={startEditing}>
            Fix this value
          </Button>
        )}
      </div>

      {showTrendNote && (
        <p className={styles.comingSoon}>
          Trends aren't available yet - once you've uploaded more reports, you'll be able to see
          this value over time here.
        </p>
      )}

      {isEditing && (
        <form className={styles.editForm} onSubmit={handleSaveCorrection} noValidate>
          <p className={styles.originalNote}>
            As extracted: <strong>{formatValue(result.value, result.unit)}</strong>
          </p>
          <Input
            label="Correct value"
            value={editValue}
            onChange={(event) => setEditValue(event.target.value)}
            disabled={isSaving}
          />
          <Input
            label="Reason"
            hint="Optional - e.g. “OCR misread a digit”"
            value={editReason}
            onChange={(event) => setEditReason(event.target.value)}
            disabled={isSaving}
          />
          {saveError && <p className={styles.saveError}>{saveError}</p>}
          <div className={styles.editActions}>
            <Button type="submit" variant="primary" size="md" disabled={isSaving}>
              {isSaving ? "Saving…" : "Save correction"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="md"
              onClick={() => setIsEditing(false)}
              disabled={isSaving}
            >
              Cancel
            </Button>
          </div>
        </form>
      )}

      {result.corrections.length > 0 && (
        <div className={styles.history}>
          <h4 className={styles.historyHeading}>Correction history</h4>
          <ul className={styles.historyList}>
            {result.corrections.map((correction) => (
              <li key={correction.id} className={styles.historyItem}>
                <p>
                  Changed from <strong>{correction.previous_value ?? "(blank)"}</strong> to{" "}
                  <strong>{correction.new_value}</strong>
                </p>
                {correction.reason && <p className={styles.historyReason}>{correction.reason}</p>}
                <p className={styles.historyDate}>{formatDate(correction.created_at)}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
