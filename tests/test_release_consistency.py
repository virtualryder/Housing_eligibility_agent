"""Review-5 — release-tag consistency gate.

Tag drift across docs was flagged in THREE consecutive external reviews ("which release is actually
supported?"). This test makes the class of defect unmergeable: the `RELEASE` file at the repo root is
the SINGLE SOURCE OF TRUTH for the current validated tag, and every deploy-facing reference must
match it. Cutting a new release = update `RELEASE`, run this test, fix what it names.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
TAG = (ROOT / "RELEASE").read_text(encoding="utf-8").strip()


def test_release_file_shape():
    assert re.fullmatch(r"v\d+\.\d+\.\d+(-[A-Za-z0-9.-]+)?", TAG), f"RELEASE malformed: {TAG!r}"


def test_every_checkout_instruction_matches_release():
    """Any `git checkout vX.Y.Z` in a tracked doc/generator must reference THE release."""
    offenders = []
    for p in [ROOT / "README.md", ROOT / "DEPLOYMENT-GUIDE.md", ROOT / "cdk" / "README.md",
              ROOT / "START-HERE.md", *(ROOT / "docs" / "generators").glob("*.js")]:
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            m = re.search(r"git checkout (v\d+\.\d+\.\d+[^\s`\"]*)", line)
            if m and m.group(1) != TAG:
                offenders.append(f"{p.name}:{i} says {m.group(1)}, RELEASE says {TAG}")
    assert not offenders, "stale deploy instructions:\n" + "\n".join(offenders)


def test_anchor_documents_name_the_release():
    """The four anchor docs must each explicitly carry the current tag."""
    for path, needle in (
        (ROOT / "README.md", f"releases/tag/{TAG}"),                    # supported-path banner link
        (ROOT / "VALIDATED_RELEASE.md", f"`{TAG}`"),                    # release table row
        (ROOT / "cdk" / "README.md", f"`{TAG}`"),                       # header statement
        (ROOT / "START-HERE.md", f"releases/tag/{TAG}"),                # entry page
    ):
        assert needle in path.read_text(encoding="utf-8"), \
            f"{path.name} does not reference the current release {TAG}"


def test_workflow_default_tag_matches_release():
    wf = (ROOT / ".github" / "workflows" / "release-validation.yml").read_text(encoding="utf-8")
    m = re.search(r'default: "(v\d+\.\d+\.\d+[^"]*)"', wf)
    assert m and m.group(1) == TAG, \
        f"release-validation.yml default tag {m.group(1) if m else 'MISSING'} != RELEASE {TAG}"


def test_no_other_version_posed_as_current():
    """No doc may tell the reader a DIFFERENT tag is 'the validated/supported release'."""
    pat = re.compile(r"(?:validated release tag|supported release|current validated release)[^.\n]{0,40}?(v\d+\.\d+\.\d+)", re.I)
    offenders = []
    for p in [ROOT / "README.md", ROOT / "DEPLOYMENT-GUIDE.md", ROOT / "cdk" / "README.md",
              ROOT / "START-HERE.md"]:
        for m in pat.finditer(p.read_text(encoding="utf-8")):
            if m.group(1) != TAG:
                offenders.append(f"{p.name}: claims {m.group(1)} is current; RELEASE says {TAG}")
    assert not offenders, "\n".join(offenders)
