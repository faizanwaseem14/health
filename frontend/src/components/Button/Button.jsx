import { forwardRef } from "react";
import styles from "./Button.module.css";

/**
 * The one button component every screen should use. `as="a"` renders
 * an anchor styled identically to a <button> (for anchor links like
 * the hero's "see how it works"), so visual language never drifts
 * between the two.
 */
export const Button = forwardRef(function Button(
  { variant = "primary", size = "lg", as = "button", className = "", ...props },
  ref,
) {
  const Component = as;
  const classes = [styles.button, styles[variant], styles[size], className]
    .filter(Boolean)
    .join(" ");

  return <Component ref={ref} className={classes} {...props} />;
});
