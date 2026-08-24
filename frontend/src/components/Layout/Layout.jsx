import { Link, Outlet } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { ThemeToggle } from "../../theme/ThemeToggle";
import { Logo } from "../Logo/Logo";
import styles from "./Layout.module.css";

export function Layout() {
  const { isAuthenticated } = useAuth();

  return (
    <div className={styles.shell}>
      <a href="#main-content" className={styles.skipLink}>
        Skip to main content
      </a>

      <header className={styles.header}>
        <div className={`container ${styles.headerInner}`}>
          <Link to="/" className={styles.logoLink} aria-label="HealthVault home">
            <Logo />
          </Link>
          <div className={styles.headerActions}>
            {isAuthenticated ? (
              <>
                <Link to="/home" className={styles.accountLink}>
                  Home
                </Link>
                <Link to="/account" className={styles.accountLink}>
                  My account
                </Link>
              </>
            ) : (
              <Link to="/login" className={styles.accountLink}>
                Sign in
              </Link>
            )}
            <ThemeToggle />
          </div>
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
