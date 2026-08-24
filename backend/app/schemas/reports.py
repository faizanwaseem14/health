"""Request shapes for report-management routes (rename)."""

from pydantic import BaseModel, Field


class ReportRenamePayload(BaseModel):
    """The body the frontend sends to rename a report."""

    display_name: str = Field(..., min_length=1, max_length=200)
