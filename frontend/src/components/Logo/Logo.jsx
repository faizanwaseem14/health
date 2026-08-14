import styles from "./Logo.module.css";

/**
 * The HealthVault mark: concentric rings, like a vault dial and a
 * tree's growth rings at once — layers of records, kept and grown
 * over time, safely closed. It's also the source shape for the
 * ContourMotif background pattern, so the header mark and the hero
 * background read as one family, not two unrelated decorations.
 */
export function Mark({ size = 36 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      role="img"
      aria-label="HealthVault"
      className={styles.mark}
    >
      <circle cx="24" cy="24" r="21" className={styles.ringOuter} strokeWidth="2.5" />
      <circle cx="24" cy="24" r="14" className={styles.ringMid} strokeWidth="2.5" />
      <circle cx="24" cy="24" r="5.5" className={styles.ringCore} />
    </svg>
  );
}

export function Logo({ size = 36, withWordmark = true }) {
  return (
    <span className={styles.lockup}>
      <Mark size={size} />
      {withWordmark && <span className={styles.wordmark}>HealthVault</span>}
    </span>
  );
}
