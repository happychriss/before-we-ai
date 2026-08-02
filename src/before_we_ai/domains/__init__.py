"""Domain packs shipped with the product — the starting vocabulary, as data.

A domain pack is what turns this general machine into one that can search a
particular kind of landscape: business objects with definitions, the fields
they carry, the settlement path for each, and the families of question an
answer type covers. The *laws* of the domain are code (`checks/library.py`,
tagged with the domain); everything else is this YAML.

They live inside the package because they are **shipped**: `pip install` must
bring the finance pack with it, and the planned `discover(root)` onboarding
hands a new project one of these to start from. A project's own guide is a
different thing — the customer's data, pointed at by `llm.domain_guide_file`
in their `before-ai.yaml`, and it lives in their project.

That the guide is "data, never code" is a rule about its *format*, not its
location: nothing here is Python, and the product reads these files exactly
the way it reads a customer's.
"""

from importlib.resources import files
from pathlib import Path


def packaged(name: str) -> Path:
    """The path of a shipped domain pack, e.g. ``packaged("finance")``."""
    return Path(str(files(__package__) / f"{name}.yaml"))


def available() -> list[str]:
    """Every shipped pack, by the name a config may use."""
    return sorted(p.stem for p in Path(str(files(__package__))).glob("*.yaml"))


def resolve_guide(declared: str, root: Path | None = None) -> Path:
    """What ``llm.domain_guide_file`` points at — a pack name or a path.

    A bare name (``finance``) means the pack we ship; anything with a
    separator or a suffix is the customer's own file, resolved against
    their project. **A real file always wins**: if a project happens to
    contain `finance` on disk, that is theirs and we do not shadow it.

    The two are deliberately not the same kind of thing. A shipped pack is
    our vocabulary, versioned with the code; a project guide is the
    customer's data, and `discover(root)` hands a new project one of ours
    to start from precisely so they can then make it their own.
    """
    path = Path(declared)
    candidate = path if path.is_absolute() or root is None else root / path
    if candidate.is_file():
        return candidate
    if path.suffix or len(path.parts) > 1:
        return candidate  # meant as a path; let the caller report it missing
    bundled = packaged(declared)
    return bundled if bundled.is_file() else candidate
