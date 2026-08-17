/**
 * Turns a report's raw backend status (report.status + its latest
 * job's job_status - see GET /reports/:id) into what a reader should
 * actually see: a short label and a <StatusBadge> tone. One place, so
 * the Home list and the processing screen never drift apart on wording.
 *
 * report.status alone isn't enough: a job stuck at "review_required"
 * leaves report.status at "processing" (see backend app/jobs/service.py),
 * so job_status is checked first.
 */
export function describeReportStatus({ status, job_status: jobStatus }) {
  switch (jobStatus) {
    case "review_required":
      return { tone: "review", label: "Needs a quick review" };
    case "completed":
      return { tone: "good", label: "Done" };
    case "failed":
      return { tone: "attention", label: "Couldn't process" };
    case "cancelled":
      return { tone: "attention", label: "Cancelled" };
    case "processing":
      return { tone: "pending", label: "Processing" };
    case "queued":
      return { tone: "pending", label: "Waiting to start" };
    default:
      break;
  }

  // No job row at all yet (shouldn't normally happen - every upload
  // creates one - but report.status is the honest fallback).
  if (status === "processed") return { tone: "good", label: "Done" };
  if (status === "failed") return { tone: "attention", label: "Couldn't process" };
  return { tone: "pending", label: "Waiting to start" };
}

/** Whether a report's processing has reached a state that stops polling. */
export function isReportStatusTerminal(jobStatus) {
  return (
    jobStatus === "completed" ||
    jobStatus === "failed" ||
    jobStatus === "cancelled" ||
    jobStatus === "review_required"
  );
}
