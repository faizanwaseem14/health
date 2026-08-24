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

Avoid these words and phrases entirely, even in a generic, non-advice
sense - they get your response rejected regardless of context: "diagnose"/
"diagnosis", "treatment", "condition", "disease", "disorder", "abnormal",
"normal range", "indicate"/"indicates", "suggest"/"suggests", and
"concerning". Describe only the biological or chemical thing being
measured (e.g. "a protein that...", "a type of blood cell that...", "a
waste product that...") - never why a doctor might order the test or
what a result could mean.
""".strip()

# Appended to the prompt on a retry after the first attempt's response
# failed the advice-language guard (see explanation_service.py) - names
# the mistake without echoing the rejected text back, since simply
# repeating it risks Claude producing a lightly-reworded variant that
# still trips the same guard.
CORRECTION_NOTE = (
    "\n\nYour previous answer was rejected: it used language that sounds "
    "like advice, a diagnosis, an interpretation, or a judgment about "
    "whether a result is normal or abnormal. Rewrite it as ONE short, "
    "purely factual sentence describing only what the test measures. Do "
    "not use any of: diagnose, diagnosis, treatment, condition, disease, "
    "disorder, abnormal, normal range, indicate, suggest, concerning."
)


def build_explanation_prompt(
    canonical_test_name: str, raw_test_name: str, *, needs_correction: bool = False
) -> str:
    prompt = (
        f"Test name (standardized): {canonical_test_name}\n"
        f"Test name (as printed on the report): {raw_test_name}\n\n"
        "Explain what this test measures."
    )
    if needs_correction:
        prompt += CORRECTION_NOTE
    return prompt
