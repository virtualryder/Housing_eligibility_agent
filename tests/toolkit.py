"""Test helper: load a governed tool's handler by name, from the agent tools or shared controls."""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
AGENT_TOOLS = ROOT / "agents" / "housing-assistance" / "tools"
CONTROLS = ROOT / "lib" / "controls"

# Make shared control modules importable by plain name (e.g. `import provenance` inside a tool handler),
# mirroring how they are bundled into each Lambda zip at deploy time.
for _p in (str(CONTROLS), str(AGENT_TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def load(name):
    for base in (AGENT_TOOLS, CONTROLS):
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
