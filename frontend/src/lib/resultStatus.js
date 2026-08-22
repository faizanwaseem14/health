/**
 * Turns a result's raw backend flag ("low" | "normal" | "high" | null -
 * see GET /reports/:id/results) into a <StatusBadge> tone + label.
 * Never color alone: every label spells out the word AND (for high/low)
 * an arrow, on top of the badge's own icon+color - three independent
 * signals for the same meaning.
 *
 * flag is null whenever the report itself didn't print enough to
 * compute one (no numeric range, non-numeric value) - that's not
 * treated as "normal", it's treated as "nothing to compare against".
 */
export function describeResultFlag(flag) {
  switch (flag) {
    case "high":
      return { tone: "attention", label: "↑ High" };
    case "low":
      // A distinct tone from "high" on purpose - amber for both would
      // mean color (and only color) was the one thing telling a
      // colorblind reader "above range" from "below range" apart.
      return { tone: "low", label: "↓ Low" };
    case "normal":
      return { tone: "good", label: "✓ Normal" };
    default:
      return null;
  }
}

/**
 * Trust status is a SEPARATE dimension from the medical flag above:
 * it's about how confident the extraction itself was, not whether the
 * value is medically concerning. "trusted" is deliberately understated
 * (a small confirmation, not a big badge) - "review_required" is the
 * state worth calling out.
 */
export function describeTrustStatus(trustStatus) {
  if (trustStatus === "review_required") {
    return { tone: "review", label: "Needs a quick review" };
  }
  return { tone: "good", label: "Trusted" };
}

/**
 * A calm, plain-language gloss for why a result needs review - the
 * backend's own trust_check_notes (e.g. "confidence 0.62 is below the
 * 0.70 threshold") is accurate but written for debugging, not for a
 * reader. Falls back to a generic reassurance for note shapes this
 * doesn't recognize, rather than ever showing raw internals as the
 * primary message.
 */
export function describeReviewReason(trustCheckNotes) {
  const notes = (trustCheckNotes ?? "").toLowerCase();
  if (notes.includes("confidence")) {
    return "We're less confident than usual about this reading - it's worth double-checking against the original report.";
  }
  if (notes.includes("evidence") || notes.includes("ocr")) {
    return "We couldn't fully match this value back to the original scanned text - worth a quick look.";
  }
  return "Something about this reading needs a closer look before we'd call it fully trustworthy.";
}
