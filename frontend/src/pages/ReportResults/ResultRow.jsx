import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../../components/Button/Button";
import { Input } from "../../components/Input/Input";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import { describeApiError } from "../../lib/authErrors";
import {
  describeResultFlag,
  describeReviewReason,
  describeTrustStatus,
} from "../../lib/resultStatus";
import styles from "./ResultRow.module.css";

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
 * One extracted result, collapsed to test name + value + status by
 * default. Expanding it (tap anywhere on the summary) reveals its
 * explanation (fetched on demand - see ReportResults.jsx), why it
 * needs review if it does, a way to correct the value, that value's
 * full correction history, and a link to see exactly where it came
 * from in the original report.
 */
export function ResultRow({
  result,
  reportId,
  isExpanded,
  onToggleExpand,
  onRequestExplanation,
  isExplanationLoading,
  onCorrect,
}) {
  const navigate = useNavigate();
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(result.value);
  const [editReason, setEditReason] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const flagBadge = describeResultFlag(result.flag);
  const trustBadge = describeTrustStatus(result.trust_status);

  async function handleExpandClick() {
    onToggleExpand();
    if (!isExpanded && !result.explanation) {
      await onRequestExplanation(result.id);
    }
  }

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

  function handleViewInOriginal() {
    navigate(`/reports/${reportId}/ocr`, {
      state: { highlightWordIds: result.ocr_word_ids },
    });
  }

  return (
    <li className={styles.row}>
      <button
        type="button"
        className={styles.summary}
        onClick={handleExpandClick}
        aria-expanded={isExpanded}
      >
        <span className={styles.testName}>
          {result.canonical_test_name || result.raw_test_name}
        </span>
        <span className={styles.valueGroup}>
          <span className={styles.value}>{formatValue(result.value, result.unit)}</span>
          {flagBadge && <StatusBadge tone={flagBadge.tone} label={flagBadge.label} />}
        </span>
      </button>

      {isExpanded && (
        <div className={styles.details}>
          {result.reference_range_text && (
            <p className={styles.rangeNote}>
              Reference range: {formatValue(result.reference_range_text, result.unit)}
            </p>
          )}
          {result.converted_value_numeric != null && result.converted_unit && (
            <p className={styles.rangeNote}>
              Also equal to {result.converted_value_numeric} {result.converted_unit}
            </p>
          )}

          <div className={styles.trustLine}>
            {result.ai_confidence != null && (
              <span className={styles.confidence}>
                {Math.round(result.ai_confidence * 100)}% confidence
              </span>
            )}
            <StatusBadge tone={trustBadge.tone} label={trustBadge.label} />
          </div>
          {result.trust_status === "review_required" && (
            <details className={styles.reviewDetails}>
              <summary>Why does this need review?</summary>
              <p>{describeReviewReason(result.trust_check_notes)}</p>
              {result.trust_check_notes && (
                <p className={styles.technicalNote}>{result.trust_check_notes}</p>
              )}
            </details>
          )}

          <div className={styles.explanationSection}>
            {result.explanation ? (
              <p className={styles.explanationText}>{result.explanation}</p>
            ) : isExplanationLoading ? (
              <p className={styles.explanationLoading}>Getting an explanation…</p>
            ) : (
              <p className={styles.explanationUnavailable}>
                We couldn't generate an explanation for this test right now.
              </p>
            )}
          </div>

          {result.ocr_word_ids.length > 0 && (
            <Button type="button" variant="ghost" size="md" onClick={handleViewInOriginal}>
              View in original report
            </Button>
          )}

          {!isEditing ? (
            <Button type="button" variant="ghost" size="md" onClick={startEditing}>
              Fix this value
            </Button>
          ) : (
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
              <h3 className={styles.historyHeading}>Correction history</h3>
              <ul className={styles.historyList}>
                {result.corrections.map((correction) => (
                  <li key={correction.id} className={styles.historyItem}>
                    <p>
                      Changed from{" "}
                      <strong>{correction.previous_value ?? "(blank)"}</strong> to{" "}
                      <strong>{correction.new_value}</strong>
                    </p>
                    {correction.reason && (
                      <p className={styles.historyReason}>{correction.reason}</p>
                    )}
                    <p className={styles.historyDate}>{formatDate(correction.created_at)}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </li>
  );
}
