"""
A reusable "ownership guard": given a row from one of our tables and the
logged-in user, proves that row actually belongs to that user before a
route is allowed to read or write it.

Health records fan out through several tables - a report belongs to a
profile, a result belongs to a report, a correction belongs to a result,
and so on - so "do you own this row" often means walking up a chain of
foreign keys to find out which user ultimately owns it. Rather than
writing that chain-walking logic again in every route, each model
registers ONE small function here ("given this row, who owns it?"), and
every route reuses the same `require_owned_row` dependency.
"""

from typing import Callable, TypeVar
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_db
from app.models import (
    Correction,
    Explanation,
    Job,
    Profile,
    Report,
    Result,
    Share,
    User,
)

ModelT = TypeVar("ModelT")


def _owner_of_profile(db: Session, row: Profile) -> UUID | None:
    return row.user_id


def _owner_of_report(db: Session, row: Report) -> UUID | None:
    return db.query(Profile.user_id).filter(Profile.id == row.profile_id).scalar()


def _owner_of_result(db: Session, row: Result) -> UUID | None:
    return (
        db.query(Profile.user_id)
        .join(Report, Report.profile_id == Profile.id)
        .filter(Report.id == row.report_id)
        .scalar()
    )


def _owner_of_correction(db: Session, row: Correction) -> UUID | None:
    return (
        db.query(Profile.user_id)
        .join(Report, Report.profile_id == Profile.id)
        .join(Result, Result.report_id == Report.id)
        .filter(Result.id == row.result_id)
        .scalar()
    )


def _owner_of_job(db: Session, row: Job) -> UUID | None:
    return (
        db.query(Profile.user_id)
        .join(Report, Report.profile_id == Profile.id)
        .filter(Report.id == row.report_id)
        .scalar()
    )


def _owner_of_explanation(db: Session, row: Explanation) -> UUID | None:
    # An explanation belongs to EITHER a result OR a whole report - use
    # whichever one is actually set.
    if row.result_id is not None:
        return (
            db.query(Profile.user_id)
            .join(Report, Report.profile_id == Profile.id)
            .join(Result, Result.report_id == Report.id)
            .filter(Result.id == row.result_id)
            .scalar()
        )
    if row.report_id is not None:
        return (
            db.query(Profile.user_id)
            .join(Report, Report.profile_id == Profile.id)
            .filter(Report.id == row.report_id)
            .scalar()
        )
    return None


def _owner_of_share(db: Session, row: Share) -> UUID | None:
    return row.shared_by_user_id


# Every model a user can own rows in registers its "who owns this row?"
# function here. Adding ownership support for a new table later is: add
# one small function above, then one line here - never touch the guard
# itself or any route that already uses it.
_OWNER_RESOLVERS: dict[type, Callable[[Session, object], UUID | None]] = {
    Profile: _owner_of_profile,
    Report: _owner_of_report,
    Result: _owner_of_result,
    Correction: _owner_of_correction,
    Job: _owner_of_job,
    Explanation: _owner_of_explanation,
    Share: _owner_of_share,
}


def require_owned_row(model: type[ModelT]) -> Callable[..., ModelT]:
    """
    Returns a reusable FastAPI dependency that fetches `model` by its
    `row_id` path parameter, and blocks access unless the logged-in user
    owns it.

    Use it on any route like:
        @app.get("/reports/{row_id}")
        def get_report(report: Report = Depends(require_owned_row(Report))):
            ...

    We return 404 - not 403 - for someone else's row, on purpose: that
    way, trying random IDs can't even reveal whether a row exists at
    all, only whether it's YOURS.
    """

    def dependency(
        row_id: UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> ModelT:
        row = db.get(model, row_id)

        owner_user_id = None
        if row is not None:
            resolver = _OWNER_RESOLVERS.get(model)
            if resolver is None:
                raise RuntimeError(
                    f"No ownership resolver registered for {model.__name__} - "
                    "add one to app.auth.ownership before using require_owned_row."
                )
            owner_user_id = resolver(db, row)

        if row is None or owner_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Not found."
            )

        return row

    return dependency
