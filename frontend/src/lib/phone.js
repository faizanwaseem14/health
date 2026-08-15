/**
 * Turns whatever someone typed into a phone field into the E.164
 * format Firebase phone auth requires (e.g. "+15551234567"). Assumes
 * a US number when no country code is given, since that's this app's
 * only supported region today; a number that's already typed with a
 * leading "+" is trusted as international and passed through with
 * just its punctuation stripped.
 *
 * Returns null for anything that doesn't look like a real phone
 * number, rather than guessing.
 */
export function toE164(rawInput) {
  const trimmed = rawInput.trim();
  if (!trimmed) return null;

  if (trimmed.startsWith("+")) {
    const digits = trimmed.slice(1).replace(/\D/g, "");
    return digits.length >= 8 ? `+${digits}` : null;
  }

  const digits = trimmed.replace(/\D/g, "");
  if (digits.length === 10) return `+1${digits}`;
  if (digits.length === 11 && digits.startsWith("1")) return `+${digits}`;
  return null;
}
