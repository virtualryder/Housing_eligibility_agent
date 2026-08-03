"""Test helper: load a governed tool's handler by name, from the agent tools, this agent's domain
controls, or the pinned governance core."""
import importlib.util
import pathlib
import sys

import governed_core

ROOT = pathlib.Path(__file__).resolve().parents[1]
AGENT_TOOLS = ROOT / "agents" / "housing-assistance" / "tools"
# The core controls come from the PINNED governed-core package, not from a copy in this repo.
# lib/controls now holds only this agent's domain-shaped modules, and it is searched FIRST so a
# declared domain override wins — the same precedence the Lambda bundler uses at deploy time.
CONTROLS = ROOT / "lib" / "controls"
CORE_CONTROLS = pathlib.Path(governed_core.controls_dir())

# Make control modules importable by plain name (e.g. `import provenance` inside a tool handler),
# mirroring how they are bundled into each Lambda zip at deploy time. Importing governed_core already
# put the packaged controls on sys.path; these inserts put the agent's own modules ahead of them.
for _p in (str(CONTROLS), str(AGENT_TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def load(name):
    for base in (AGENT_TOOLS, CONTROLS, CORE_CONTROLS):
        p = base / f"{name}.py"
        if p.exists():
            spec = importlib.util.spec_from_file_location(name, p)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            return m
    raise FileNotFoundError(name)


def call(name, event):
    return load(name).handler(event, None)


def make_sanitized_ref(text="[REDACTED:NAME] household of 4, income 40000, county 0603799999"):
    """Mint a GENUINE mask_pii-style sanitized_ref (P0-1) for tests, as the JSON string it crosses the
    gateway as. Requires PROVENANCE_SECRET in env (set by the test modules before import)."""
    import json
    import sanitized
    return json.dumps(sanitized.mint_ref(text, engine="comprehend:DetectPiiEntities", entities_masked=1))
