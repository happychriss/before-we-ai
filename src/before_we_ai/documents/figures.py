"""Reading numbers out of a quote without inventing agreement.

``500.000`` is five hundred thousand to a German writer and five hundred
to an English one, and a document rarely says which it is. The tempting
move is to pick the reading that matches whatever we were hoping to
confirm — which is how a corroboration engine quietly becomes a
confirmation engine.

So a literal with two plausible readings is reported as having two, and
the multi-anchor rule refuses to count it. Recording the ambiguity costs
one anchor; hiding it costs the meaning of every anchor.
"""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from before_we_ai.core.enums import AnchorMatch

# A run of digits with optional grouping separators and an optional
# fractional tail. Currency words and symbols around it are not our
# business — the number is. The lookarounds keep labels out: the 3 in
# "Q3" is a quarter, not a figure, and reading it as one would let any
# heading full of period labels look like a document full of numbers.
_LITERAL = re.compile(r"(?<![A-Za-z\d])-?\d[\d.,]*\d(?![A-Za-z])"
                      r"|(?<![A-Za-z\d])-?\d(?![A-Za-z])")


@dataclass(frozen=True)
class Figure:
    """One numeric literal as written, with every reading it supports."""

    literal: str
    readings: tuple[Decimal, ...]

    @property
    def ambiguous(self) -> bool:
        return len(self.readings) > 1

    @property
    def value(self) -> Decimal | None:
        """The single reading, when there is exactly one."""
        return self.readings[0] if len(self.readings) == 1 else None


def _read(literal: str, separator: str, decimal_point: str) -> Decimal | None:
    """Read the literal under one grouping convention, or not at all."""
    body = literal.lstrip("-")
    sign = -1 if literal.startswith("-") else 1

    whole, point, fraction = body.rpartition(decimal_point)
    if not point:
        whole, fraction = body, ""
    if decimal_point in whole or separator in fraction:
        return None  # a second decimal point, or grouping after it

    digits = whole.replace(separator, "")
    if not digits.isdigit() or (fraction and not fraction.isdigit()):
        return None
    if separator in whole:
        head, *rest = whole.split(separator)
        if not head or len(head) > 3 or any(len(part) != 3 for part in rest):
            return None  # 1,23,456 is not grouped under either convention

    try:
        return sign * Decimal(f"{digits}.{fraction}" if fraction else digits)
    except InvalidOperation:
        return None


def read_figure(literal: str) -> Figure:
    readings = []
    for separator, decimal_point in ((",", "."), (".", ",")):
        value = _read(literal, separator, decimal_point)
        if value is not None and value not in readings:
            readings.append(value)
    return Figure(literal=literal, readings=tuple(readings))


def read_figures(text: str) -> list[Figure]:
    """Every numeric literal in a quote, in the order it is written."""
    return [read_figure(match.group()) for match in _LITERAL.finditer(text)]


def _significant_digits(value: Decimal) -> int:
    return len(value.normalize().as_tuple().digits)


def _round_to(value: Decimal, digits: int) -> Decimal:
    """``value`` rounded to ``digits`` significant digits."""
    if value == 0:
        return Decimal(0)
    exponent = value.adjusted() - digits + 1
    quantum = Decimal(1).scaleb(exponent)
    return (value / quantum).quantize(Decimal(1)) * quantum


def compare(figure: Figure, target: Decimal) -> str:
    """How a written figure relates to the value it is offered for.

    ``rounded`` is agreement at the precision the document itself chose:
    a report saying 2,850,000 for an underlying 2,847,000 has rounded, not
    contradicted. A reading that only matches because we guessed a
    grouping convention is a coincidence candidate, never agreement.
    """
    for reading in figure.readings:
        if reading == target:
            return (AnchorMatch.EXACT.value if not figure.ambiguous
                    else AnchorMatch.COINCIDENTAL_CANDIDATE.value)
    for reading in figure.readings:
        digits = _significant_digits(reading)
        if digits and _round_to(target, digits) == reading:
            return (AnchorMatch.ROUNDED.value if not figure.ambiguous
                    else AnchorMatch.COINCIDENTAL_CANDIDATE.value)
    return AnchorMatch.COINCIDENTAL_CANDIDATE.value


def match_quote(quote: str, target: Decimal) -> tuple[str, Figure | None]:
    """The best match any figure in the quote achieves against ``target``."""
    ranking = {
        AnchorMatch.EXACT.value: 0,
        AnchorMatch.ROUNDED.value: 1,
        AnchorMatch.COINCIDENTAL_CANDIDATE.value: 2,
    }
    best = (AnchorMatch.COINCIDENTAL_CANDIDATE.value, None)
    for figure in read_figures(quote):
        match = compare(figure, target)
        if ranking[match] < ranking[best[0]]:
            best = (match, figure)
    return best


def distinct_values(quote: str) -> list[Decimal]:
    """Unambiguous values a quote states, in order, deduplicated."""
    values: list[Decimal] = []
    for figure in read_figures(quote):
        value = figure.value
        if value is not None and value not in values:
            values.append(value)
    return values


def _magnitude(value: Decimal) -> int:
    return value.adjusted()


def restated_values(quote: str) -> list[Decimal]:
    """Values a quote offers for *the same* figure, when it offers several.

    This is how a restatement announces itself in prose: "EUR 3,200,000
    (restated from EUR 3,050,000)". Two numbers in one sentence prove
    nothing on their own — a sentence about Q1 2023 has a quarter and a
    year in it too — so the test is same *magnitude*: figures of the same
    size, competing for one slot. Empty when the quote states one value,
    or several that are plainly about different things.
    """
    by_magnitude: dict[int, list[Decimal]] = {}
    for value in distinct_values(quote):
        by_magnitude.setdefault(_magnitude(value), []).append(value)
    competing = [group for group in by_magnitude.values() if len(group) > 1]
    if not competing:
        return []
    return max(competing, key=len)
