// Small, purpose-drawn icons for the value-prop strip. Kept separate
// from StatusBadge's icons — these describe FEATURES, not a result's
// status, so they intentionally don't borrow the status color
// language (that palette is reserved for real result states).

export function IconFolder() {
  return (
    <svg viewBox="0 0 32 32" width="28" height="28" fill="none" aria-hidden="true">
      <path
        d="M4 10a2 2 0 0 1 2-2h6.2l2.4 2.6H26a2 2 0 0 1 2 2V23a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V10Z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconCheckShield() {
  return (
    <svg viewBox="0 0 32 32" width="28" height="28" fill="none" aria-hidden="true">
      <path
        d="M16 4.5 27 8.5v7.2c0 7-4.6 12.7-11 14.8-6.4-2.1-11-7.8-11-14.8V8.5L16 4.5Z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path
        d="M11 16.3l3.4 3.4L21.5 12.6"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconBook() {
  return (
    <svg viewBox="0 0 32 32" width="28" height="28" fill="none" aria-hidden="true">
      <path
        d="M6 7c3-1.3 6.6-1.3 10 0v18c-3.4-1.3-7-1.3-10 0V7Z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path
        d="M26 7c-3-1.3-6.6-1.3-10 0v18c3.4-1.3 7-1.3 10 0V7Z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconLock() {
  return (
    <svg viewBox="0 0 32 32" width="28" height="28" fill="none" aria-hidden="true">
      <rect
        x="7"
        y="14.5"
        width="18"
        height="13"
        rx="2.5"
        stroke="currentColor"
        strokeWidth="2"
      />
      <path
        d="M11 14.5v-4a5 5 0 0 1 10 0v4"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <circle cx="16" cy="20.5" r="1.6" fill="currentColor" />
    </svg>
  );
}
