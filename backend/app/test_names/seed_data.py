"""
A small STARTER set of common test-name aliases - deliberately not
exhaustive. This is prototype-level test-name knowledge: enough common
variants to make the catalog useful today, structured so it's trivial
to extend and easy to replace wholesale later.

Extending this list is exactly that: add another dict to SEED_ALIASES
below and re-run `python -m app.test_names.seed` (see seed.py) - it's
an upsert keyed by raw_name, so running it again after adding entries
is always safe and never creates duplicates.

Replacing this list with a full LOINC-based catalog later needs no
changes anywhere else in the app: LOINC import would populate the
exact same `test_aliases` table shape (raw_name / canonical_name /
category / default_unit) via a different loader, and
app/test_names/resolver.py would keep working unchanged - it only ever
reads from the table, never from this file directly.

default_unit here is the UNIT this catalog considers standard for that
canonical test (used by app/units/ to compute a derived, clearly-
labeled converted value alongside the original - see
app/units/service.py). It is NOT a reference range and never implies
one; nothing here says what a "normal" value is for any test.
"""

SEED_ALIASES: list[dict[str, str | None]] = [
    # --- Hemoglobin ---
    {
        "raw_name": "Hemoglobin",
        "canonical_name": "Hemoglobin",
        "category": "Hematology",
        "default_unit": "g/dL",
    },
    {
        "raw_name": "Haemoglobin",
        "canonical_name": "Hemoglobin",
        "category": "Hematology",
        "default_unit": "g/dL",
    },
    {
        "raw_name": "HGB",
        "canonical_name": "Hemoglobin",
        "category": "Hematology",
        "default_unit": "g/dL",
    },
    {
        "raw_name": "Hgb",
        "canonical_name": "Hemoglobin",
        "category": "Hematology",
        "default_unit": "g/dL",
    },
    # --- White blood cell count ---
    {
        "raw_name": "White Blood Cell Count",
        "canonical_name": "White Blood Cell Count",
        "category": "Hematology",
        "default_unit": "x10^3/uL",
    },
    {
        "raw_name": "White Blood Cells",
        "canonical_name": "White Blood Cell Count",
        "category": "Hematology",
        "default_unit": "x10^3/uL",
    },
    {
        "raw_name": "WBC",
        "canonical_name": "White Blood Cell Count",
        "category": "Hematology",
        "default_unit": "x10^3/uL",
    },
    # --- Platelet count ---
    {
        "raw_name": "Platelet Count",
        "canonical_name": "Platelet Count",
        "category": "Hematology",
        "default_unit": "x10^3/uL",
    },
    {
        "raw_name": "Platelets",
        "canonical_name": "Platelet Count",
        "category": "Hematology",
        "default_unit": "x10^3/uL",
    },
    {
        "raw_name": "PLT",
        "canonical_name": "Platelet Count",
        "category": "Hematology",
        "default_unit": "x10^3/uL",
    },
    # --- Glucose ---
    {
        "raw_name": "Glucose",
        "canonical_name": "Glucose",
        "category": "Chemistry",
        "default_unit": "mg/dL",
    },
    {
        "raw_name": "Blood Glucose",
        "canonical_name": "Glucose",
        "category": "Chemistry",
        "default_unit": "mg/dL",
    },
    {
        "raw_name": "Gluc",
        "canonical_name": "Glucose",
        "category": "Chemistry",
        "default_unit": "mg/dL",
    },
    # --- Total cholesterol ---
    {
        "raw_name": "Total Cholesterol",
        "canonical_name": "Total Cholesterol",
        "category": "Chemistry",
        "default_unit": "mg/dL",
    },
    {
        "raw_name": "Cholesterol, Total",
        "canonical_name": "Total Cholesterol",
        "category": "Chemistry",
        "default_unit": "mg/dL",
    },
    {
        "raw_name": "Total Chol",
        "canonical_name": "Total Cholesterol",
        "category": "Chemistry",
        "default_unit": "mg/dL",
    },
    # --- Creatinine ---
    {
        "raw_name": "Creatinine",
        "canonical_name": "Creatinine",
        "category": "Chemistry",
        "default_unit": "mg/dL",
    },
    {
        "raw_name": "Creat",
        "canonical_name": "Creatinine",
        "category": "Chemistry",
        "default_unit": "mg/dL",
    },
]
