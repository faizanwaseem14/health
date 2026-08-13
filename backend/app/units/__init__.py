"""
Unit conversion: computing a DERIVED value in a different, genuinely
compatible unit - alongside the original printed value/unit, never
replacing them. See app/units/conversion.py for the actual conversion
math and app/units/service.py for how it's applied to a report's
results (using the canonical test catalog's default_unit as the
target - see app/test_names/).
"""
