import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import { describeResultFlag } from "../../lib/resultStatus";
import styles from "./TrendChart.module.css";

const TONE_COLOR_VAR = {
  good: "var(--color-status-good-fg)",
  attention: "var(--color-status-attention-fg)",
  low: "var(--color-status-low-fg)",
};
const DEFAULT_COLOR_VAR = "var(--color-status-pending-fg)";

function formatShortDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// Only a strict "NUMBER - NUMBER" range can be drawn as a band - same
// shape the backend's own calculate_status() requires (see
// app/trust/status.py). Anything else (comparator notation, "Negative",
// a range the report simply didn't print) just isn't drawn - never a
// guessed band.
function parseStrictRange(text) {
  if (!text) return null;
  const match = text.trim().match(/^([\d.]+)\s*-\s*([\d.]+)$/);
  if (!match) return null;
  const low = Number(match[1]);
  const high = Number(match[2]);
  if (Number.isNaN(low) || Number.isNaN(high) || low >= high) return null;
  return { low, high };
}

const WIDTH = 640;
const HEIGHT = 220;
const PAD_X = 28;
const PAD_TOP = 20;
const PAD_BOTTOM = 36;

/**
 * A test's value over time - a line through every genuinely comparable
 * point (see app/trends/service.py for what "comparable" means), each
 * marked normal (circle), high (triangle pointing up), or low (triangle
 * pointing down), always in the tone + shape pair StatusBadge itself
 * uses - color is never the only signal. The legend below repeats
 * every point as plain text + a real <StatusBadge>, which is the
 * authoritative, fully accessible version of the same data the chart
 * draws visually.
 */
export function TrendChart({ points, referenceRangeText }) {
  const range = parseStrictRange(referenceRangeText);
  const values = points.map((point) => point.value);
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (range) {
    min = Math.min(min, range.low);
    max = Math.max(max, range.high);
  }
  if (min === max) {
    min -= 1;
    max += 1;
  }
  const margin = (max - min) * 0.15;
  min -= margin;
  max += margin;

  const plotWidth = WIDTH - PAD_X * 2;
  const plotHeight = HEIGHT - PAD_TOP - PAD_BOTTOM;

  function xFor(index) {
    if (points.length === 1) return PAD_X + plotWidth / 2;
    return PAD_X + (index / (points.length - 1)) * plotWidth;
  }
  function yFor(value) {
    return PAD_TOP + (1 - (value - min) / (max - min)) * plotHeight;
  }

  const linePath = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${xFor(index)} ${yFor(point.value)}`)
    .join(" ");

  return (
    <div className={styles.wrap}>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className={styles.svg}
        role="img"
        aria-label={`Trend chart with ${points.length} data points`}
      >
        {range && (
          <rect
            x={PAD_X}
            y={yFor(range.high)}
            width={plotWidth}
            height={Math.max(0, yFor(range.low) - yFor(range.high))}
            className={styles.rangeBand}
          />
        )}
        <path d={linePath} className={styles.line} fill="none" />
        {points.map((point, index) => {
          const badge = describeResultFlag(point.flag);
          const colorVar = badge ? TONE_COLOR_VAR[badge.tone] : DEFAULT_COLOR_VAR;
          const x = xFor(index);
          const y = yFor(point.value);
          return (
            <g key={`${point.report_id}-${index}`}>
              {point.flag === "high" ? (
                <polygon
                  points={`${x},${y - 8} ${x - 7},${y + 6} ${x + 7},${y + 6}`}
                  style={{ fill: colorVar }}
                />
              ) : point.flag === "low" ? (
                <polygon
                  points={`${x},${y + 8} ${x - 7},${y - 6} ${x + 7},${y - 6}`}
                  style={{ fill: colorVar }}
                />
              ) : (
                <circle cx={x} cy={y} r={6} style={{ fill: colorVar }} />
              )}
              <text x={x} y={HEIGHT - PAD_BOTTOM + 20} textAnchor="middle" className={styles.axisLabel}>
                {formatShortDate(point.date)}
              </text>
              <title>
                {formatShortDate(point.date)}: {point.raw_value} {point.raw_unit ?? ""}
                {badge ? ` (${badge.label})` : ""}
              </title>
            </g>
          );
        })}
      </svg>

      <ul className={styles.legend}>
        {points.map((point, index) => {
          const badge = describeResultFlag(point.flag);
          return (
            <li key={`${point.report_id}-${index}`} className={styles.legendRow}>
              <span className={styles.legendDate}>{formatShortDate(point.date)}</span>
              <span className={styles.legendValue}>
                {point.raw_value} {point.raw_unit ?? ""}
              </span>
              {badge && <StatusBadge tone={badge.tone} label={badge.label} />}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
