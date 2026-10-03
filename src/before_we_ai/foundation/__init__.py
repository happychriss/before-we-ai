"""Foundation documents: domain knowledge a person signs, a machine applies.

Experimental, and deliberately outside the model-facing packages: nothing
in here is proposed, bound or judged by a model.
"""

from before_we_ai.foundation.apply import Applied, apply, retire
from before_we_ai.foundation.laws import Binding, LawResult, evaluate
from before_we_ai.foundation.reader import (
    Foundation,
    NotAFoundationDocument,
    Rule,
    Tolerance,
    read_foundation,
)

__all__ = [
    "Applied",
    "Binding",
    "Foundation",
    "LawResult",
    "NotAFoundationDocument",
    "Rule",
    "Tolerance",
    "apply",
    "evaluate",
    "read_foundation",
    "retire",
]
