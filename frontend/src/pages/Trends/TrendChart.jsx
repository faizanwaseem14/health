import styles from "./TrendChart.module.css";

const SEVERITY_LABEL = {
  normal: "Normal",
  out: "Out of range",
  severe: "Well out of range",
};

const SEVERITY_MARKER_CLASS = {
  normal: "markerNormal",
  out: "markerOut",
  severe: "markerSevere",
};

// A point more than this far past the printed bound (as a fraction of
// the range's own width) counts as "well out of range" rather than
// just "out of range" - the midpoint of the "20-30% past the bound"
// this chart's design calls for.
const SEVERE_THRESHOLD_FRACTION = 0.25;

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

// Only a strict "NUMBER - NUMBER" range can be drawn or classified
// against - same shape the backend's own calculate_status() requires
// (see app/trust/status.py). Anything else (comparator notation,
// "Negative", a range the report simply didn't print) just isn't drawn
// - never a guessed range.
function parseStrictRange(text) {
  if (!text) return null;
  const match = text.trim().match(/^([\d.]+)\s*-\s*([\d.]+)$/);
  if (!match) return null;
  const low = Number(match[1]);
  const high = Number(match[2]);
  if (Number.isNaN(low) || Number.isNaN(high) || low >= high) return null;
  return { low, high };
}

// Classifies one point against the printed range: "normal" (inside
// it), "out" (past a bound), or "severe" (far enough past it - see
// SEVERE_THRESHOLD_FRACTION). Without a parseable numeric range, falls
// back to the backend's own high/low/normal flag - which can say
// "out", never "severe", since that distinction needs real numbers.
function classifySeverity(point, range) {
  if (range) {
    const span = range.high - range.low;
    if (point.value < range.low) {
      const pastBy = range.low - point.value;
      return span > 0 && pastBy > span * SEVERE_THRESHOLD_FRACTION ? "severe" : "out";
    }
    if (point.value > range.high) {
      const pastBy = point.value - range.high;
      return span > 0 && pastBy > span * SEVERE_THRESHOLD_FRACTION ? "severe" : "out";
    }
    return "normal";
  }
  return point.flag === "high" || point.flag === "low" ? "out" : "normal";
}

// A smooth curve through every point (Catmull-Rom converted to cubic
// Bezier segments) instead of straight polyline segments - purely a
// rendering choice, the data itself is never altered or interpolated.
function buildSmoothLinePath(pts) {
  if (pts.length < 2) return "";
  if (pts.length === 2) {
    return `M ${pts[0].x} ${pts[0].y} L ${pts[1].x} ${pts[1].y}`;
  }
  const d = [`M ${pts[0].x} ${pts[0].y}`];
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] ?? p2;
    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;
    d.push(`C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`);
  }
  return d.join(" ");
}

const WIDTH = 640;
const HEIGHT = 240;
const PAD_LEFT = 46;
const PAD_RIGHT = 16;
const PAD_TOP = 20;
const PAD_BOTTOM = 32;
const TICK_COUNT = 4;
const POINT_RADIUS = 4;

/**
 * A test's value over time - a smooth teal line through every
 * genuinely comparable point (see app/trends/service.py for what
 * "comparable" means), each the same small filled circle - status is
 * carried by COLOR alone (teal = normal, orange = out of range, red =
 * well out of range), explained in the plain-word key below the chart
 * rather than by a second visual channel like shape. The printed
 * range (when the report's own range text is a plain "low - high") is
 * marked with two light dashed lines, never a filled band.
 */
export function TrendChart({ points, referenceRangeText }) {
  const range = parseStrictRange(referenceRangeText);
  const unit = points.find((point) => point.raw_unit)?.raw_unit ?? "";

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

  const plottedPoints = points.map((point, index) => ({
    x: xFor(index),
    y: yFor(point.value),
    point,
    severity: classifySeverity(point, range),
  }));

  const linePath = buildSmoothLinePath(plottedPoints);

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
          <g>
            <line
              x1={PAD_LEFT}
              x2={WIDTH - PAD_RIGHT}
              y1={yFor(range.high)}
              y2={yFor(range.high)}
              className={styles.rangeLine}
            />
            <text
              x={WIDTH - PAD_RIGHT}
              y={yFor(range.high) - 6}
              textAnchor="end"
              className={styles.rangeLabel}
            >
              {formatTick(range.high)} {unit}
            </text>
            <line
              x1={PAD_LEFT}
              x2={WIDTH - PAD_RIGHT}
              y1={yFor(range.low)}
              y2={yFor(range.low)}
              className={styles.rangeLine}
            />
            <text
              x={WIDTH - PAD_RIGHT}
              y={yFor(range.low) + 14}
              textAnchor="end"
              className={styles.rangeLabel}
            >
              {formatTick(range.low)} {unit}
            </text>
          </g>
        )}

        <path d={linePath} className={styles.line} fill="none" />

        {plottedPoints.map(({ x, y, point, severity }, index) => (
          <g key={`${point.report_id}-${index}`}>
            <circle
              cx={x}
              cy={y}
              r={POINT_RADIUS}
              className={styles[SEVERITY_MARKER_CLASS[severity]]}
            />
            <text
              x={x}
              y={HEIGHT - PAD_BOTTOM + 20}
              textAnchor={
                index === 0 ? "start" : index === plottedPoints.length - 1 ? "end" : "middle"
              }
              className={styles.axisLabel}
            >
              {formatShortDate(point.date)}
            </text>
            <title>
              {formatShortDate(point.date)}: {point.raw_value} {point.raw_unit ?? ""} (
              {SEVERITY_LABEL[severity]})
            </title>
          </g>
        ))}
      </svg>

      <div className={styles.colorKey}>
        <h4 className={styles.colorKeyHeading}>What the colors mean</h4>
        <ul className={styles.colorKeyList}>
          <li className={styles.colorKeyItem}>
            <span className={`${styles.dot} ${styles.dotNormal}`} aria-hidden="true" />
            <span>
              <strong>Normal</strong> — within the range printed on your report
              {range ? ` (${formatTick(range.low)}-${formatTick(range.high)} ${unit})` : ""}.
            </span>
          </li>
          <li className={styles.colorKeyItem}>
            <span className={`${styles.dot} ${styles.dotOut}`} aria-hidden="true" />
            <span>
              <strong>Out of range</strong> — above or below your report's range.
            </span>
          </li>
          <li className={styles.colorKeyItem}>
            <span className={`${styles.dot} ${styles.dotSevere}`} aria-hidden="true" />
            <span>
              <strong>Well out of range</strong> — far above or below your report's range.
            </span>
          </li>
        </ul>
      </div>
    </div>
  );
}
