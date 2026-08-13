"""
Test-name knowledge: resolving the messy, inconsistent test names
printed on real lab reports (and the AI's own best-guess canonical
name for them) against the `test_aliases` table - the single
authoritative mapping from raw spelling/format variants to one
standard canonical name.

This is prototype-level knowledge: app/test_names/seed_data.py seeds a
small STARTER set of common aliases, not an exhaustive medical
catalog. A full LOINC-based import is deliberately deferred to deploy
stage - see seed_data.py's docstring for exactly how that swap works
without touching anything else in this package or its callers.
"""
