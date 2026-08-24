import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import { describeResultFlag } from "../../lib/resultStatus";
import styles from "./TrendChart.module.css";

function formatShortDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// Keeps a tick label short without hiding real precision: an integer
// stays an integer, anything else gets exactly one decimal place -
// never more, so labels like "98.427182" (a floating-point artifact of
// the min/max/margin math below, not a real reading) can't appear.
function formatTick(value) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
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
const HEIGHT = 240;
const PAD_LEFT = 46;
const PAD_RIGHT = 16;
const PAD_TOP = 16;
const PAD_BOTTOM = 32;
const TICK_COUNT = 4;
const POINT_RADIUS = 3.5;

/**
 * A test's value over time - a thin line through every genuinely
 * comparable point (see app/trends/service.py for what "comparable"
 * means). Deliberately a plain, mostly-monochrome chart: an in-range
 * point is a small neutral dot, an out-of-range point is a small amber
 * triangle (pointing toward "high" or "low"), so direction+shape - not
 * a rainbow of hues - is what a colorblind reader relies on. The
 * legend below repeats every point as plain text + a real
 * <StatusBadge>, which is the authoritative, fully accessible version
 * of the same data the chart draws visually.
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

  const plotWidth = WIDTH - PAD_LEFT - PAD_RIGHT;
  const plotHeight = HEIGHT - PAD_TOP - PAD_BOTTOM;

  function xFor(index) {
    if (points.length === 1) return PAD_LEFT + plotWidth / 2;
    return PAD_LEFT + (index / (points.length - 1)) * plotWidth;
  }
  function yFor(value) {
    return PAD_TOP + (1 - (value - min) / (max - min)) * plotHeight;
  }

  const linePath = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${xFor(index)} ${yFor(point.value)}`)
    .join(" ");

  const ticks = Array.from({ length: TICK_COUNT + 1 }, (_, i) => {
    const value = min + ((max - min) * i) / TICK_COUNT;
    return { value, y: yFor(value) };
  });

  return (
    <div className={styles.wrap}>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className={styles.svg}
        role="img"
        aria-label={`Trend chart with ${points.length} data points`}
      >
        {ticks.map((tick) => (
          <g key={tick.value}>
            <line
              x1={PAD_LEFT}
              x2={WIDTH - PAD_RIGHT}
              y1={tick.y}
              y2={tick.y}
              className={styles.gridline}
            />
            <text x={PAD_LEFT - 8} y={tick.y} textAnchor="end" className={styles.axisLabel}>
              {formatTick(tick.value)}
            </text>
          </g>
        ))}

        {range && (
          <rect
            x={PAD_LEFT}
            y={yFor(range.high)}
            width={plotWidth}
            height={Math.max(0, yFor(range.low) - yFor(range.high))}
            className={styles.rangeBand}
          />
        )}

        <path d={linePath} className={styles.line} fill="none" />

        {points.map((point, index) => {
          const badge = describeResultFlag(point.flag);
          const isOutOfRange = point.flag === "high" || point.flag === "low";
          const x = xFor(index);
          const y = yFor(point.value);
          return (
            <g key={`${point.report_id}-${index}`}>
              {point.flag === "high" ? (
                <polygon
                  points={`${x},${y - 6} ${x - 5.5},${y + 4.5} ${x + 5.5},${y + 4.5}`}
                  className={styles.markerOutOfRange}
                />
              ) : point.flag === "low" ? (
                <polygon
                  points={`${x},${y + 6} ${x - 5.5},${y - 4.5} ${x + 5.5},${y - 4.5}`}
                  className={styles.markerOutOfRange}
                />
              ) : (
                <circle
                  cx={x}
                  cy={y}
                  r={POINT_RADIUS}
                  className={isOutOfRange ? styles.markerOutOfRange : styles.markerInRange}
                />
              )}
              <text
                x={x}
                y={HEIGHT - PAD_BOTTOM + 20}
                textAnchor="middle"
                className={styles.axisLabel}
              >
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

      <ul className={styles.legendKey}>
        <li className={styles.legendKeyItem}>
          <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
            <circle cx="6" cy="6" r="4" className={styles.markerInRange} />
          </svg>
          <span>In range</span>
        </li>
        <li className={styles.legendKeyItem}>
          <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
            <polygon points="6,1 1,10 11,10" className={styles.markerOutOfRange} />
          </svg>
          <span>Out of range</span>
        </li>
      </ul>

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
