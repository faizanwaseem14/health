import { forwardRef, useId } from "react";
import styles from "./Input.module.css";

const WarningIcon = () => (
  <svg viewBox="0 0 20 20" width="18" height="18" fill="none" aria-hidden="true">
    <path
      d="M10 3.5 17.5 16h-15L10 3.5Z"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinejoin="round"
    />
    <path d="M10 8.2v3.6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    <circle cx="10" cy="14.2" r="1" fill="currentColor" />
  </svg>
);

/**
 * A labeled text input every form in the app should use: a visible
 * label above the field (never a placeholder standing in for one), a
 * generous tap target, and an error message that's always shown with
 * BOTH an icon and text, never color alone.
 */
export const Input = forwardRef(function Input(
  { label, hint, error, id, ...props },
  ref,
) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const hintId = hint ? `${inputId}-hint` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;

  return (
    <div className={styles.field}>
      <label htmlFor={inputId} className={styles.label}>
        {label}
      </label>
      {hint && (
        <p id={hintId} className={styles.hint}>
          {hint}
        </p>
      )}
      <input
        id={inputId}
        ref={ref}
        className={`${styles.input} ${error ? styles.inputError : ""}`}
        aria-describedby={[hintId, errorId].filter(Boolean).join(" ") || undefined}
        aria-invalid={error ? "true" : undefined}
        {...props}
      />
      {error && (
        <p id={errorId} className={styles.error}>
          <WarningIcon />
          <span>{error}</span>
        </p>
      )}
    </div>
  );
});
