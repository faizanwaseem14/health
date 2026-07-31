"""
Importing this package registers every table with `Base.metadata` (from
app.database), which is what Alembic (Task 8) will read to generate
migrations. Anywhere else in the app that needs a model should import it
from here, e.g. `from app.models import User`.
"""

from app.models.audit_log import AuditLog
from app.models.correction import Correction
from app.models.explanation import Explanation
from app.models.job import Job
from app.models.otp_attempt import OtpAttempt
from app.models.profile import Profile
from app.models.report import Report
from app.models.result import Result
from app.models.share import Share
from app.models.test_alias import TestAlias
from app.models.user import User

__all__ = [
    "AuditLog",
    "Correction",
    "Explanation",
    "Job",
    "OtpAttempt",
    "Profile",
    "Report",
    "Result",
    "Share",
    "TestAlias",
    "User",
]
