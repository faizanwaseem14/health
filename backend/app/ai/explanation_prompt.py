"""
The explanation prompt and its version. EXPLANATION_PROMPT_VERSION must
be bumped any time the prompt text changes in a way that could change
what gets generated.

Generates a plain-language description of what a lab test MEASURES -
never advice, interpretation, diagnosis, or a recommendation, and never
anything about any particular value or result. The prompt is only the
first line of defense; app/ai/explanation.py independently checks every
response for advice-like language before it's ever saved, so this isn't
trusted to enforce the rule by wording alone.

EXPLANATION_MODEL is a cheap model - describing what a test is, in
general, is plain factual writing with no report-specific reasoning
needed, so a small, fast model keeps per-explanation cost low.
"""

EXPLANATION_MODEL = "claude-haiku-4-5"
EXPLANATION_PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """
You explain, in plain language, what a single medical lab test
measures - nothing more.

Your ONLY job: describe what the named test is and what it measures in
the body, in one or two short sentences a non-expert can understand.

You must NEVER:
- give advice, a recommendation, or a suggested next step
- say whether any particular result or value is normal, abnormal, high,
  low, or concerning
- diagnose, interpret, or speculate about any condition or disease
- mention seeing a doctor, seeking care, treatment, or taking any action
- reference a specific numeric value, range, or result - you were not
  given one and must not assume one

You were only given a test name - not a value, not a range, not any
result. Describe what the test measures, factually and generically -
the same description regardless of what anyone's actual result was.
""".strip()


def build_explanation_prompt(canonical_test_name: str, raw_test_name: str) -> str:
    return (
        f"Test name (standardized): {canonical_test_name}\n"
        f"Test name (as printed on the report): {raw_test_name}\n\n"
        "Explain what this test measures."
    )
