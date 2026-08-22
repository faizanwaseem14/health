import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import { describeResultFlag, describeTrustStatus } from "../../lib/resultStatus";
import { ExplainPanel } from "./ExplainPanel";
import styles from "./TestCard.module.css";

function formatValue(value, unit) {
  return unit ? `${value} ${unit}` : value;
}

/**
 * One test result: name, the reference range exactly as printed
 * (small, muted), the value (large), and its status badge. Tapping it
 * (or tapping the matching region on the report image - see
 * ReportPanel.jsx) opens the "what is this?" panel inline below;
 * selection itself is owned by ReportResults so both sides stay linked.
 */
export function TestCard({
  result,
  isSelected,
  onSelect,
  onRequestExplanation,
  isExplanationLoading,
  onCorrect,
}) {
  const flagBadge = describeResultFlag(result.flag);
  const trustBadge = describeTrustStatus(result.trust_status);
  const needsReview = result.trust_status === "review_required";

  return (
    <li
      id={`test-card-${result.id}`}
      className={`${styles.card} ${isSelected ? styles.cardSelected : ""}`}
    >
      <button
        type="button"
        className={styles.summary}
        onClick={() => onSelect(result.id)}
        aria-expanded={isSelected}
        aria-controls={`explain-panel-${result.id}`}
      >
        <span className={styles.info}>
          <span className={styles.testName}>
            {result.canonical_test_name || result.raw_test_name}
          </span>
          {result.reference_range_text && (
            <span className={styles.range}>
              Reference range: {formatValue(result.reference_range_text, result.unit)}
            </span>
          )}
          {needsReview && (
            <StatusBadge
              tone={trustBadge.tone}
              label={trustBadge.label}
              className={styles.reviewBadge}
            />
          )}
        </span>
        <span className={styles.valueGroup}>
          <span className={styles.value}>{formatValue(result.value, result.unit)}</span>
          {flagBadge && <StatusBadge tone={flagBadge.tone} label={flagBadge.label} />}
        </span>
      </button>

      {isSelected && (
        <div id={`explain-panel-${result.id}`}>
          <ExplainPanel
            result={result}
            onRequestExplanation={onRequestExplanation}
            isExplanationLoading={isExplanationLoading}
            onCorrect={onCorrect}
          />
        </div>
      )}
    </li>
  );
}
