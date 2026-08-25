/**
 * Turns a share's backend status ("active" | "revoked" | "expired" |
 * "exhausted" - see app/routers/shares.py's _share_status) into a
 * <StatusBadge> tone + label, the same icon+word+color pattern every
 * other status in this app uses.
 */
export function describeShareStatus(status) {
  switch (status) {
    case "active":
      return { tone: "good", label: "Active" };
    case "revoked":
      return { tone: "attention", label: "Revoked" };
    case "expired":
      return { tone: "pending", label: "Expired" };
    case "exhausted":
      return { tone: "pending", label: "View limit reached" };
    default:
      return { tone: "pending", label: status };
  }
}
