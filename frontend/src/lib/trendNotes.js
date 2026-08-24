/**
 * The ONE factual sentence a trend panel is allowed to show about a
 * test's latest value - a fixed template keyed only off `flag` (the
 * backend's own deterministic value-vs-printed-range calculation),
 * never anything generated. No diagnosis, no advice, no interpretation
 * of what it might mean - it only ever restates what the report itself
 * already says, in plain words. Returns null for "normal" (or an
 * unknown flag): nothing worth calling out.
 */
export function describeLatestValueNote(testName, flag) {
  if (flag === "high") {
    return `Your most recent ${testName} is above the range on your report.`;
  }
  if (flag === "low") {
    return `Your most recent ${testName} is below the range on your report.`;
  }
  return null;
}
