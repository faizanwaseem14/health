"""
Append-only audit logging: records WHO did WHAT, WHEN, and FROM WHERE -
never WHAT DATA they saw.

This is the one place in the whole app allowed to write to audit_log.
There is deliberately no update/delete function here - and the database
itself refuses UPDATE or DELETE on this table (see the Alembic
migration that adds an append-only trigger), so even a bug elsewhere in
the app can't quietly rewrite history.

HOW WE KEEP HEALTH DATA OUT, STRUCTURALLY (not just by promising to be
careful): record_audit_event() has no field that accepts free-form text
- no "details", "value", "content", or "notes" parameter for someone to
be tempted to stuff a lab result into. `action` and `resource_type` must
both come from small, fixed, reviewed vocabularies below - if it's not
already on the list, this function refuses to log it rather than
silently accepting arbitrary text.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import AuditLog

# Every kind of event we actually log. Add to this list in a code review
# when a new feature needs a new action - never let a caller invent one
# on the fly (that's exactly how something like a health value could
# sneak in disguised as an "action").
ALLOWED_ACTIONS = {
    "login",
    "view_own_profile",
    "view_profile",
    "upload_report",
    "view_report",
    "download_report",
    "view_result",
    "create_share",
    "revoke_share",
    "otp_request",
    "recovery_attempt",
    "generate_recovery_code",
}

# Every kind of ROW an action can be about - just a table name, never a
# description of what's actually in that row.
ALLOWED_RESOURCE_TYPES = {
    "user",
    "profile",
    "report",
    "result",
    "correction",
    "explanation",
    "job",
    "share",
}


def record_audit_event(
    db: Session,
    *,
    action: str,
    ip_address: str,
    user_id: UUID | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    """
    Records one audit log entry. Call this from anywhere a user reads or
    writes their data - a route, a background job, anywhere.

    `action` must be one of ALLOWED_ACTIONS and `resource_type` (if
    given) must be one of ALLOWED_RESOURCE_TYPES - both raise ValueError
    otherwise. This isn't red tape: it's what makes it structurally
    impossible to log a health value here, since there's no field that
    accepts arbitrary text in the first place.
    """
    if action not in ALLOWED_ACTIONS:
        raise ValueError(
            f"Unknown action {action!r} - add it to ALLOWED_ACTIONS in "
            "app/core/audit.py if this is a real event type, not a mistake."
        )
    if resource_type is not None and resource_type not in ALLOWED_RESOURCE_TYPES:
        raise ValueError(
            f"Unknown resource_type {resource_type!r} - add it to "
            "ALLOWED_RESOURCE_TYPES in app/core/audit.py if this is a real "
            "resource type, not a mistake."
        )

    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
