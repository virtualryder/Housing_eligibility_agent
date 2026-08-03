"""Shared test setup.

The control plane is no longer copied into this repo. `governed-core` is a PINNED, HASH-VERIFIED
dependency (see requirements-core.txt), and importing it puts the packaged `controls/` and
`connector/` directories on sys.path. That preserves the flat-import contract the tool handlers rely
on (`import evidence`, `import identity`) — the same contract that holds at deploy time, when the
bundler stages those modules flat beside each handler.

Order matters. `governed_core` goes on the path FIRST; `tests/toolkit.py` then inserts this repo's
own `lib/controls` ahead of it, so an agent-specific module (mask_pii, provenance, signoff_register,
workflow_guards, sanitized, case_store, ingest_case, tenancy) shadows the packaged one if a name ever
collides. `tests/test_core_dependency.py` asserts that every such shadow is a DECLARED domain
override, because a silent shadow would reintroduce exactly the drift the dependency exists to
prevent.

Also set the provenance signing secret ONCE, before any test module is imported, so every module
signs and verifies with the same key (assess_housing_eligibility's P0-3 provenance gate is
HMAC-based). conftest is imported by pytest ahead of collection, so the value is stable regardless of
test file order.
"""
import os

os.environ.setdefault("PROVENANCE_SECRET", "p0-unit-provenance-secret")

# Imported for the side effect: this is what makes `import evidence` resolve to the pinned package.
import governed_core  # noqa: E402,F401  (must precede any flat control-plane import)

CORE_CONTROLS = governed_core.controls_dir()
