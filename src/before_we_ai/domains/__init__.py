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
