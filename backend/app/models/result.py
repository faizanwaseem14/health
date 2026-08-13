"""
The `results` table: one row per individual test value extracted from a
report (e.g. "Hemoglobin: 13.5 g/dL"). Populated by AI extraction (see
app/ai/service.py) from a report's stored OCR evidence.
"""

import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Result(Base):
    __tablename__ = "results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Which job's AI extraction produced this row - useful for
    # debugging a specific run; kept even if that job row is later
    # deleted. Mirrors ocr_words.job_id.
    job_id = Column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    # Links this raw test name to a standardized name (see test_alias.py).
    # Nullable because that matching happens later, not at upload time.
    test_alias_id = Column(
        UUID(as_uuid=True),
        ForeignKey("test_aliases.id", ondelete="SET NULL"),
        nullable=True,
    )

    # The test name exactly as it was printed on the report.
    raw_test_name = Column(String, nullable=False)
    # The AI's own best standard/common name for the same test (e.g.
    # "Hemoglobin" for a raw "HGB") - a plain text guess, not a match
    # against test_aliases (test_alias_id above is the deterministic
    # link for that).
    canonical_test_name = Column(String, nullable=True)

    # The value as printed, kept as text so we never lose information
    # (e.g. "Negative", "13.5", "<0.1").
    value = Column(String, nullable=False)
    # The same value parsed into a number when possible, so later
    # features can do math/graphing without re-parsing text every time.
    value_numeric = Column(Numeric, nullable=True)

    unit = Column(String, nullable=True)

    reference_range_low = Column(Numeric, nullable=True)
    reference_range_high = Column(Numeric, nullable=True)
    # For ranges that aren't a simple low-high pair, e.g. "Negative" or
    # "< 5.0", exactly as printed.
    reference_range_text = Column(String, nullable=True)

    # The date printed for this specific result, exactly as printed
    # (formats vary too much across labs to safely parse into a real
    # Date column - kept as text, same reasoning as `value` above).
    result_date = Column(String, nullable=True)
    # The lab/facility name printed on the report, if any.
    lab_name = Column(String, nullable=True)
    # The AI's own confidence (0.0-1.0) in this extraction - separate
    # from any OCR word's confidence, which lives on ocr_words instead.
    ai_confidence = Column(Numeric, nullable=True)

    # ------------------------------------------------------------------
    # IMPORTANT - read before touching this field:
    #
    # `flag` must ONLY ever be set by our own deterministic status-
    # calculation code (plain code comparing `value_numeric` against
    # `reference_range_low` / `reference_range_high`), which is built on
    # a LATER day. It must NEVER be:
    #   - set by an AI/LLM,
    #   - hardcoded,
    #   - guessed or inferred from anything other than the report's own
    #     printed numbers.
    #
    # Allowed values are only "low", "normal", "high" (see the CHECK
    # constraint below) - and only when the report gives us enough
    # printed information to calculate it. We do NOT invent a "critical"
    # status the lab didn't print; if a report only ever prints those
    # three words, that's all this column will ever hold.
    # ------------------------------------------------------------------
    flag = Column(String, nullable=True)

    # ------------------------------------------------------------------
    # The "trust chain" (app/trust/): every extracted row is run through
    # a set of structural checks (does its value actually appear in its
    # own OCR evidence, is the value/range/unit well-formed, is the AI's
    # confidence high enough) BEFORE anything downstream is allowed to
    # treat it as real data. "trusted" means it passed every check;
    # "review_required" means it failed at least one - and defaults to
    # "review_required" (fail-closed) until the checks actually run, so
    # a row is never accidentally treated as trusted just because
    # nothing got around to checking it yet.
    # ------------------------------------------------------------------
    trust_status = Column(String, nullable=False, default="review_required")
    # Which check failed and why, e.g. "confidence 0.62 is below the
    # 0.80 threshold" - null when trust_status is "trusted".
    trust_check_notes = Column(Text, nullable=True)

    # ------------------------------------------------------------------
    # Unit conversion (app/units/): a DERIVED value, computed by plain
    # code from `value`/`unit` above, expressed in the canonical test
    # catalog's standard unit for this test (app/test_names/) - never
    # the AI's opinion, never a substance-specific/medical conversion.
    #
    # These are ADDITIVE, not authoritative: `value`/`unit` above are
    # always the original, exactly-as-printed source of truth and are
    # NEVER overwritten by conversion. converted_value_numeric/
    # converted_unit stay None whenever no default unit is known for
    # this test, no unit was printed, the printed unit already matches
    # the default, or the two units aren't a genuinely compatible pair
    # with a well-defined conversion factor - nothing here ever forces
    # or guesses a conversion.
    # ------------------------------------------------------------------
    converted_value_numeric = Column(Numeric, nullable=True)
    converted_unit = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "flag IN ('low', 'normal', 'high')", name="ck_results_flag_valid_values"
        ),
        CheckConstraint(
            "trust_status IN ('trusted', 'review_required')",
            name="ck_results_trust_status_valid_values",
        ),
    )

    report = relationship("Report", back_populates="results")
    ocr_word_links = relationship(
        "ResultOcrWord", back_populates="result", cascade="all, delete-orphan"
    )
