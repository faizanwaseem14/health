"""
Secure, revocable share links: a report - or a chosen subset of its
results - exposed read-only at /public/shares/{token}, with no
HealthVault account or login required. See app/routers/shares.py for
the routes that call into this module.

Three properties this module exists to guarantee, all enforced here
(never left to the router to remember):
  1. The token is genuinely unguessable (secrets.token_urlsafe, not a
     sequential id or anything derived from guessable data).
  2. A share is valid ONLY while it's unrevoked, unexpired, and under
     its view limit - and resolving a token checks all three AND
     records the view atomically in one statement, so two nearly-
     simultaneous requests against the last remaining view can't both
     get through (see resolve_share_access).
  3. A share exposes exactly the report/results it was scoped to at
     creation time - never anything else, and never another user's
     data (ownership of the report being shared is the router's job,
     via require_owned_row(Report), before this module is ever called).
"""

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, update
from sqlalchemy.orm import Session

from app.database import commit_with_retry
from app.models import Report, Result, Share, ShareResult

# 32 random bytes, base64url-encoded -> a 43-character token. Not
# sequential, not derived from the report/profile/user id or the
# current time - guessing one is not meaningfully different from
# guessing a random 256-bit value.
_TOKEN_BYTES = 32


class ShareUnavailableError(Exception):
    """
    Raised by resolve_share_access for every reason a token might not
    currently work: it doesn't exist, it was revoked, it's expired, or
    it's already been viewed max_views times. Deliberately ONE
    exception for all four - the router turns this into one uniform
    "this link is no longer available" response, since telling a
    stranger with a URL WHICH of those is true isn't this endpoint's
    call to make (e.g. distinguishing "expired" from "never existed"
    would let someone confirm a token used to be real).
    """


def generate_share_token() -> str:
    return secrets.token_urlsafe(_TOKEN_BYTES)


def create_share(
    db: Session,
    *,
    profile_id: uuid.UUID,
    report_id: uuid.UUID,
    shared_by_user_id: uuid.UUID,
    expires_in_days: int,
    max_views: int | None,
    result_ids: list[uuid.UUID] | None,
) -> Share:
    """
    Creates a new share for `report_id`, scoped to `result_ids` if
    given (the caller must have already verified every id in
    `result_ids` actually belongs to this report - this function trusts
    that and just links them).

    The share's id, token, and expiry are all computed ONCE, before the
    retry loop, and the ORM rows are built fresh from those fixed
    values on every attempt (never a `db.flush()`-then-reuse pattern
    mid-retry) - the same "redoable closure" shape as every other
    commit_with_retry call in this app, for the same reason: a
    rollback() before a retry discards a not-yet-committed row
    regardless of whether it was already flushed.
    """
    share_id = uuid.uuid4()
    token = generate_share_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

    def mutate():
        db.add(
            Share(
                id=share_id,
                profile_id=profile_id,
                report_id=report_id,
                shared_by_user_id=shared_by_user_id,
                share_token=token,
                expires_at=expires_at,
                max_views=max_views,
            )
        )
        for result_id in result_ids or []:
            db.add(ShareResult(id=uuid.uuid4(), share_id=share_id, result_id=result_id))

    commit_with_retry(db, mutate)
    return db.get(Share, share_id)


def resolve_share_access(db: Session, token: str) -> Share:
    """
    The one gate every public share view goes through: atomically
    checks the token resolves to a share that's unrevoked, unexpired,
    and under its view limit, and - in that SAME UPDATE - increments
    access_count. Postgres re-evaluates the WHERE clause against the
    row's true current state as it applies the row lock, so if two
    requests race for the last remaining view, only one UPDATE can
    match and return a row; the other sees zero rows updated and gets
    ShareUnavailableError, exactly as if it had arrived a moment later
    after the limit was already reached.

    Raises ShareUnavailableError if the token doesn't exist or the
    share isn't currently viewable - see that class's docstring for why
    this never says which.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        update(Share)
        .where(
            Share.share_token == token,
            Share.revoked_at.is_(None),
            Share.expires_at > now,
            or_(Share.max_views.is_(None), Share.access_count < Share.max_views),
        )
        .values(access_count=Share.access_count + 1)
        .returning(Share.id)
    )

    matched_id_holder: dict = {}

    def mutate():
        matched_id_holder["id"] = db.execute(stmt).scalar_one_or_none()

    commit_with_retry(db, mutate)

    share_id = matched_id_holder.get("id")
    if share_id is None:
        raise ShareUnavailableError()
    return db.get(Share, share_id)


@dataclass
class SharedReportData:
    report: Report
    results: list[Result]


def get_shared_report_data(db: Session, share: Share) -> SharedReportData:
    """
    Exactly the data `share` was scoped to at creation time - the
    report, and either every one of its results (no share_results rows
    for this share) or only the specific ones chosen (share_results
    present) - never anything from another report.
    """
    report = db.get(Report, share.report_id)

    scoped_result_ids = {
        row.result_id
        for row in db.query(ShareResult.result_id).filter(
            ShareResult.share_id == share.id
        )
    }

    query = db.query(Result).filter(Result.report_id == share.report_id)
    if scoped_result_ids:
        query = query.filter(Result.id.in_(scoped_result_ids))
    results = query.order_by(Result.created_at).all()

    return SharedReportData(report=report, results=results)
