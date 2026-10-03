"""Check an answer somebody else computed — claim by claim.

The rest of this package gates a model: settle what the answer depends on,
then allow it. The control run of 2026-10-03 showed a plain model does not
need the gate to get the vessel figures right — and that nobody without the
answer key could tell it had. This module is the other way round: let the
model answer, have it say what its figures rest on, and check *that*.

An answer is a set of **figures**, each a ledger total plus **corrections**
("this row is a duplicate of that one", "this row belongs to another
project", "this amount was converted the wrong way"). Every correction is a
claim, and each kind of claim has a part that data can show and a part that
it cannot:

    duplicate   two rows agree on the columns named          — data shows it
    recompute   the row's value follows from a formula, and
                the same formula fits the other rows         — data shows it
    assign      the row has no group; where it belongs is
                somebody's word                              — a quote
    reassign    the row sits in one group; that it belongs
                in another is somebody's word                — a quote
    add         a cost that is not in the ledger at all      — a quote
    remove      a row that should not count                  — a quote

For the second kind the check is the one documents already get here: the
quote has to be in the named document, word for word. That does not make
the quoted sentence true. It makes it *somebody's*, and findable.

Then each figure is recomputed from the ledger and its corrections. A
figure that does not come out is not reproduced, whatever the prose says.

Nothing here calls a model, and nothing here decides whether the answer is
right. It says how much of it can be checked, and what the rest rests on.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

VERIFIED = "verified"  # the data alone shows it
DOCUMENT = "document"  # the row facts hold; the reason is a quote that exists
UNSUPPORTED = "unsupported"  # the reason cannot be found
REFUTED = "refuted"  # the data says otherwise

KINDS = ("duplicate", "recompute", "assign", "reassign", "add", "remove")
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_VIEW = re.compile(r"[A-Za-z0-9_]+")
MONEY_TOLERANCE = 1.0  # one currency unit: figures are stated in whole units
FORMULA_FIT = 0.95  # share of other rows a recompute formula must fit


@dataclass
class ClaimCheck:
    id: str
    kind: str
    status: str
    says: str  # the claim, in a sentence
    found: str  # what the check found
    effect: dict[str, float] = field(default_factory=dict)  # group -> change


@dataclass
class FigureCheck:
    label: str
    group: str
    stated: float
    base: float  # the ledger total before any correction
    computed: float
    reproduced: bool
    rests_on: dict[str, int] = field(default_factory=dict)  # status -> count
    claims: list[str] = field(default_factory=list)


@dataclass
class AnswerCheck:
    claims: list[ClaimCheck]
    figures: list[FigureCheck]
    problems: list[str] = field(default_factory=list)  # malformed input


def _q(name: str) -> str:
    if not _VIEW.fullmatch(str(name)):
        raise ValueError(f"not a plain view or column name: {name!r}")
    return f'"{name}"'


def _num(column: str) -> str:
    return f"TRY_CAST({_q(column)} AS DOUBLE)"


def _squash(text: str) -> str:
    """Whitespace, typographic quotes and dashes carry no meaning in a quote."""
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(str.maketrans({
        "‘": "'", "’": "'", "“": '"', "”": '"',
        "–": "-", "—": "-", "­": ""}))
    return " ".join(text.split()).lower()


class Documents:
    """The text of the declared documents, read once."""

    def __init__(self, paths: dict[str, Path]):
        self._paths = paths
        self._text: dict[str, str] = {}

    def text(self, name: str) -> str | None:
        if name not in self._paths:
            return None
        if name not in self._text:
            import pymupdf

            with pymupdf.open(self._paths[name]) as pdf:
                self._text[name] = _squash(
                    " ".join(page.get_text() for page in pdf))
        return self._text[name]

    def has(self, name: str, quote: str) -> tuple[bool, str]:
        text = self.text(name)
        if text is None:
            return False, f"no document named '{name}' is declared"
        if len(_squash(quote)) < 12:
            return False, "the quote is too short to identify a passage"
        if _squash(quote) in text:
            return True, f"the quote is in {name}, word for word"
        return False, f"the quote is not in {name}"


class _Ledger:
    def __init__(self, con, spec: dict):
        self.con = con
        self.view = _q(spec["view"])
        self.key = spec["key"]
        self.measure = spec["measure"]
        self.group = spec["group"]
        self.columns = [r[0] for r in con.execute(
            f"DESCRIBE {self.view}").fetchall()]

    def row(self, key: str) -> dict | None:
        cursor = self.con.execute(
            f"SELECT * FROM {self.view} WHERE CAST({_q(self.key)} AS VARCHAR) = ?",
            [str(key)])
        names = [d[0] for d in cursor.description]
        found = cursor.fetchall()
        return dict(zip(names, found[0])) if len(found) == 1 else None

    def amount(self, row: dict) -> float:
        try:
            return float(row[self.measure])
        except (TypeError, ValueError):
            return 0.0

    def totals(self) -> dict[str, float]:
        rows = self.con.execute(
            f"SELECT coalesce(CAST({_q(self.group)} AS VARCHAR), ''), "
            f"coalesce(sum({_num(self.measure)}), 0) FROM {self.view} GROUP BY 1"
        ).fetchall()
        return {group.strip(): float(total) for group, total in rows}

    def group_of(self, row: dict) -> str:
        value = row.get(self.group)
        return "" if value is None else str(value).strip()

    def formula(self, expression: str) -> str:
        if re.search(r"[^A-Za-z0-9_+\-*/(). ]", expression):
            raise ValueError("a formula uses column names, numbers, + - * / "
                             "and parentheses, nothing else")
        for name in _NAME.findall(expression):
            if name not in self.columns:
                raise ValueError(f"`{name}` is not a column of the ledger")
        return _NAME.sub(lambda m: _num(m.group()), expression)


def _check_claim(claim: dict, ledger: _Ledger, documents: Documents) -> ClaimCheck:
    kind, cid = claim.get("kind", ""), str(claim.get("id", "?"))

    def out(status, says, found, effect=None):
        return ClaimCheck(cid, kind, status, says, found, effect or {})

    def quoted() -> tuple[bool, str]:
        if not claim.get("document") or not claim.get("quote"):
            return False, "no document and quote were given for the reason"
        return documents.has(claim["document"], claim["quote"])

    if kind not in KINDS:
        return out(UNSUPPORTED, f"a claim of kind '{kind}'",
                   f"unknown kind — one of {', '.join(KINDS)}")

    if kind == "add":
        amount, group = float(claim["amount"]), str(claim["group"])
        says = f"{amount:,.0f} is missing from the ledger and belongs to {group}"
        ok, where = quoted()
        return out(DOCUMENT if ok else UNSUPPORTED, says,
                   where + ("; the ledger cannot show a cost it does not hold"
                            if ok else ""),
                   {group: amount})

    row = ledger.row(claim["row"])
    if row is None:
        return out(REFUTED, f"about ledger row {claim['row']}",
                   f"there is no single row {claim['row']} in the ledger")
    amount, group = ledger.amount(row), ledger.group_of(row)

    if kind == "duplicate":
        other = ledger.row(claim["of"])
        says = f"row {claim['row']} repeats row {claim['of']}"
        if other is None:
            return out(REFUTED, says, f"there is no row {claim['of']}")
        same = [c for c in claim.get("same", []) if c in ledger.columns]
        if len(same) < 2:
            return out(UNSUPPORTED, says,
                       "fewer than two columns were named as identical")
        differ = [c for c in same if str(row[c]) != str(other[c])]
        if differ:
            return out(REFUTED, says,
                       "the rows differ on " + ", ".join(differ))
        return out(VERIFIED, says,
                   "the two rows agree on " + ", ".join(same), {group: -amount})

    if kind == "recompute":
        says = (f"row {claim['row']} should be {claim['expression']}, "
                f"not the {amount:,.0f} it shows")
        sql = ledger.formula(claim["expression"])
        value = ledger.con.execute(
            f"SELECT {sql} FROM {ledger.view} "
            f"WHERE CAST({_q(ledger.key)} AS VARCHAR) = ?",
            [str(claim["row"])]).fetchone()[0]
        if value is None:
            return out(REFUTED, says, "the formula gives no value for this row")
        fits, others = ledger.con.execute(
            f"SELECT count(*) FILTER (WHERE abs(({sql}) - {_num(ledger.measure)}) "
            f"<= greatest({MONEY_TOLERANCE}, 0.01 * abs({_num(ledger.measure)}))), "
            f"count(*) FROM {ledger.view} "
            f"WHERE CAST({_q(ledger.key)} AS VARCHAR) <> ?",
            [str(claim["row"])]).fetchone()
        share = fits / others if others else 0.0
        if abs(value - amount) <= MONEY_TOLERANCE:
            return out(REFUTED, says,
                       "the formula gives the value the row already shows")
        found = (f"the formula gives {value:,.0f}; it fits {fits} of the "
                 f"{others} other rows")
        if share < FORMULA_FIT:
            return out(UNSUPPORTED, says, found + " — too few to call this "
                       "row the exception rather than the formula")
        return out(VERIFIED, says, found, {group: value - amount})

    ok, where = quoted()
    if kind == "assign":
        to = str(claim["to"])
        says = f"row {claim['row']} has no group and belongs to {to}"
        if group:
            return out(REFUTED, says, f"the row is already in '{group}'")
        return out(DOCUMENT if ok else UNSUPPORTED, says,
                   f"the row has no group; {where}", {"": -amount, to: amount})
    if kind == "reassign":
        to = str(claim["to"])
        says = f"row {claim['row']} is booked to {group} and belongs to {to}"
        if claim.get("from") and str(claim["from"]) != group:
            return out(REFUTED, says,
                       f"the row is in '{group}', not '{claim['from']}'")
        return out(DOCUMENT if ok else UNSUPPORTED, says,
                   f"the row is in {group}; {where}",
                   {group: -amount, to: amount})
    says = f"row {claim['row']} should not count"  # remove
    return out(DOCUMENT if ok else UNSUPPORTED, says, where, {group: -amount})


def check_answer(con, answer: dict, document_paths: dict[str, Path]) -> AnswerCheck:
    """Check every claim, then recompute every figure from the ledger."""
    ledger = _Ledger(con, answer["ledger"])
    documents = Documents(document_paths)
    result = AnswerCheck(claims=[], figures=[])
    by_id: dict[str, ClaimCheck] = {}
    for claim in answer.get("claims", []):
        try:
            checked = _check_claim(claim, ledger, documents)
        except (KeyError, ValueError) as exc:
            checked = ClaimCheck(str(claim.get("id", "?")), claim.get("kind", ""),
                                 UNSUPPORTED, "a claim that could not be read",
                                 f"{type(exc).__name__}: {exc}")
        result.claims.append(checked)
        by_id[checked.id] = checked

    totals = ledger.totals()
    for figure in answer.get("figures", []):
        group = str(figure["group"])
        base = totals.get(group, 0.0)
        computed, rests = base, {}
        for cid in figure.get("claims", []):
            claim = by_id.get(str(cid))
            if claim is None:
                result.problems.append(
                    f"figure '{figure['label']}' cites claim {cid}, which "
                    "was not given")
                continue
            rests[claim.status] = rests.get(claim.status, 0) + 1
            computed += claim.effect.get(group, 0.0)
        stated = float(figure["stated"])
        result.figures.append(FigureCheck(
            label=figure["label"], group=group, stated=stated, base=base,
            computed=computed,
            reproduced=abs(computed - stated) <= MONEY_TOLERANCE,
            rests_on=rests, claims=[str(c) for c in figure.get("claims", [])]))
    return result
