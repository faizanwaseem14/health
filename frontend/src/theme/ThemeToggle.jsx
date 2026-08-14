import { useTheme } from "./ThemeProvider";
import styles from "./ThemeToggle.module.css";

/**
 * A single, clearly-labeled light/dark switch. Deliberately NOT an
 * icon-only control — an icon rides along, but the accessible name
 * and the visible label both say exactly what pressing it does, in
 * line with "no tiny icon-only controls" for readability.
 */
export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      type="button"
      className={styles.toggle}
      onClick={toggleTheme}
      aria-pressed={isDark}
    >
      <span className={styles.icon} aria-hidden="true">
        {isDark ? (
          <svg viewBox="0 0 24 24" fill="none" width="20" height="20">
            <path
              d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z"
              fill="currentColor"
            />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" fill="none" width="20" height="20">
            <circle cx="12" cy="12" r="4.5" fill="currentColor" />
            <g stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
              <path d="M12 2.5v2.2M12 19.3v2.2M21.5 12h-2.2M4.7 12H2.5" />
              <path d="M18.4 5.6l-1.6 1.6M7.2 16.8l-1.6 1.6M18.4 18.4l-1.6-1.6M7.2 7.2 5.6 5.6" />
            </g>
          </svg>
        )}
      </span>
      <span>{isDark ? "Dark mode" : "Light mode"}</span>
    </button>
  );
}
