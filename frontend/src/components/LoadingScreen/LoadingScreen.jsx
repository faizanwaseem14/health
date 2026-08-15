import styles from "./LoadingScreen.module.css";

export function LoadingScreen({ message = "Loading…" }) {
  return (
    <div className={`container ${styles.wrap}`} role="status" aria-live="polite">
      <span className={styles.spinner} aria-hidden="true" />
      <p className={styles.message}>{message}</p>
    </div>
  );
}
