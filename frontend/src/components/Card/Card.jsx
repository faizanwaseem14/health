import styles from "./Card.module.css";

export function Card({ as = "div", className = "", ...props }) {
  const Component = as;
  return <Component className={`${styles.card} ${className}`} {...props} />;
}
