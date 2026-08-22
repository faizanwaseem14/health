import styles from "./StatusBadge.module.css";

const ICONS = {
  good: (
    <svg viewBox="0 0 20 20" width="16" height="16" fill="none" aria-hidden="true">
      <path
        d="M4 10.5l3.5 3.5L16 6"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  ),
  attention: (
    <svg viewBox="0 0 20 20" width="16" height="16" fill="none" aria-hidden="true">
      <path
        d="M10 3.5 17.5 16h-15L10 3.5Z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path d="M10 8.2v3.6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <circle cx="10" cy="14.2" r="1" fill="currentColor" />
    </svg>
  ),
  review: (
    <svg viewBox="0 0 20 20" width="16" height="16" fill="none" aria-hidden="true">
      <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="2" />
      <path d="M10 6.5v4l2.5 1.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  ),
  pending: (
    <svg viewBox="0 0 20 20" width="16" height="16" fill="none" aria-hidden="true">
      <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="2" />
      <circle cx="6.5" cy="10" r="0.9" fill="currentColor" />
      <circle cx="10" cy="10" r="0.9" fill="currentColor" />
      <circle cx="13.5" cy="10" r="0.9" fill="currentColor" />
    </svg>
  ),
  low: (
    <svg viewBox="0 0 20 20" width="16" height="16" fill="none" aria-hidden="true">
      <path
        d="M10 4v10.5M10 14.5 5.5 10M10 14.5 14.5 10"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  ),
};

/**
 * The one way status is ever shown in this app: an icon AND a word,
 * every time — color reinforces the meaning but is never the only
 * carrier of it, so the badge still communicates correctly for
 * colorblind readers or on a black-and-white printout.
 */
export function StatusBadge({ tone = "good", label, className = "" }) {
  return (
    <span className={`${styles.badge} ${styles[tone]} ${className}`}>
      <span className={styles.icon}>{ICONS[tone]}</span>
      <span>{label}</span>
    </span>
  );
}
