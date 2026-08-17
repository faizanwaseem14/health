import { useEffect, useState } from "react";
import styles from "./ProcessingAnimation.module.css";

const DEFAULT_MESSAGES = [
  "Reading your report…",
  "Finding the numbers…",
  "Checking them against normal ranges…",
  "Double-checking everything's accurate…",
  "Almost there…",
];

const MESSAGE_INTERVAL_MS = 3200;

/**
 * The processing screen's "we're working on it" visual - built around
 * the vault-dial rings from the logo/ContourMotif, turning slowly as
 * if HealthVault is unlocking the report, rather than a plain spinner.
 * Reassuring messages cycle underneath so a long wait still feels like
 * progress, not a stall.
 *
 * The rings' motion is purely decorative; a screen reader gets the
 * cycling message via aria-live instead (see role="status" below).
 */
export function ProcessingAnimation({ messages = DEFAULT_MESSAGES }) {
  const [messageIndex, setMessageIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setMessageIndex((current) => (current + 1) % messages.length);
    }, MESSAGE_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [messages.length]);

  return (
    <div className={styles.wrap}>
      <div className={styles.dial} aria-hidden="true">
        <svg viewBox="0 0 200 200" className={styles.ring}>
          <circle
            cx="100"
            cy="100"
            r="88"
            stroke="var(--color-brand)"
            strokeWidth="2"
            opacity="0.18"
            fill="none"
          />
          <circle
            cx="100"
            cy="100"
            r="66"
            stroke="var(--color-accent)"
            strokeWidth="2"
            opacity="0.28"
            fill="none"
          />
          <circle
            cx="100"
            cy="100"
            r="44"
            stroke="var(--color-brand)"
            strokeWidth="2.5"
            opacity="0.45"
            fill="none"
            strokeDasharray="6 10"
          />
        </svg>
        <span className={styles.pulse} />
        <span className={styles.mark}>💚</span>
      </div>

      <p className={styles.message} role="status" aria-live="polite">
        {messages[messageIndex]}
      </p>
    </div>
  );
}
