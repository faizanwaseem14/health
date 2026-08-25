"""Request shapes for share-link routes."""

from uuid import UUID

from pydantic import BaseModel, Field


class ShareCreatePayload(BaseModel):
    """
    The body the frontend sends to create a share link for a report.

    `result_ids`, if given and non-empty, scopes the share to just
    those results instead of the whole report - the router verifies
    every id actually belongs to the report before this ever reaches
    app.sharing.service.
    """

    expires_in_days: int = Field(7, ge=1, le=90)
    max_views: int | None = Field(None, ge=1, le=10_000)
    result_ids: list[UUID] | None = None
