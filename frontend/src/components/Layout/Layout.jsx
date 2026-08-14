import { Outlet } from "react-router-dom";
import { Logo } from "../Logo/Logo";
import { ThemeToggle } from "../../theme/ThemeToggle";
import styles from "./Layout.module.css";

export function Layout() {
  return (
    <div className={styles.shell}>
      <a href="#main-content" className={styles.skipLink}>
        Skip to main content
      </a>

      <header className={styles.header}>
        <div className={`container ${styles.headerInner}`}>
          <Logo />
          <ThemeToggle />
        </div>
      </header>

      <main id="main-content" className={styles.main}>
        <Outlet />
      </main>

      <footer className={styles.footer}>
        <div className={`container ${styles.footerInner}`}>
          <Logo size={24} />
          <p className={styles.footerNote}>
            © {new Date().getFullYear()} HealthVault. Your records stay private and yours.
          </p>
        </div>
      </footer>
    </div>
  );
}
