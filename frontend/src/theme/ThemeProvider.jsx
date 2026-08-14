import { createContext, useContext, useEffect, useMemo, useState } from "react";

const STORAGE_KEY = "healthvault:theme";
const THEMES = ["light", "dark"];

const ThemeContext = createContext(null);

function readStoredTheme() {
  if (typeof window === "undefined") return "light";
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return THEMES.includes(stored) ? stored : "light";
  } catch {
    // Private browsing / storage disabled — fall back quietly, this
    // is a nice-to-have persistence, not a required feature.
    return "light";
  }
}

/**
 * Provides the current theme ("light" | "dark") and a way to change
 * it, to the whole app. Light is always the default for a first-time
 * visitor — we deliberately do NOT read the OS's prefers-color-scheme
 * here, so switching to dark is always an explicit choice. Once a
 * visitor does choose, that choice is remembered (localStorage) and
 * used on every later visit.
 */
export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(readStoredTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // Ignore — persistence is best-effort.
    }
  }, [theme]);

  const value = useMemo(
    () => ({
      theme,
      setTheme: (next) => setThemeState(THEMES.includes(next) ? next : "light"),
      toggleTheme: () =>
        setThemeState((current) => (current === "light" ? "dark" : "light")),
    }),
    [theme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used inside a <ThemeProvider>.");
  }
  return context;
}
