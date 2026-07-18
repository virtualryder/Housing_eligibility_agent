"""Shared test setup. Set the provenance signing secret ONCE, before any test module is imported, so
every module signs and verifies with the same key (assess_housing_eligibility's P0-3 provenance gate
is HMAC-based). conftest is imported by pytest ahead of collection, so the value is stable regardless of
test file order."""
import os

os.environ.setdefault("PROVENANCE_SECRET", "p0-unit-provenance-secret")
