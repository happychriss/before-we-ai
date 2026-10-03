"""Read a foundation document — a Word file a person can sign — into rules.

A foundation document says, in general and before any file is seen, what
must be true of a company's data if it is what it claims to be. It is
written and reviewed by people, so it is a Word document; it is applied by
a machine, so its tables follow a fixed shape and its rules a small formal
syntax. This module is the seam between the two, and it refuses rather than
guesses: a rule it cannot parse is reported with the reason, never skipped
quietly and never repaired.

Only the standard library is used. A .docx is a zip of XML, and the three
things needed from it — headings, paragraphs, tables — are a few tags.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

KINDS = ("IDENTITY", "UNIQUE", "REFERENCE", "CONDITION", "TOTAL", "DIFFERENCE")
_NAME = r"[a-z][a-z0-9_]*"
_PARAM = r"[A-Z][A-Z0-9_]*"


@dataclass(frozen=True)
class Tolerance:
    name: str
    absolute: float | None
    relative: float | None
    applies_to: str = ""
    reasoning: str = ""


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    statement: str
    kind: str
    formal: str
    tolerance: str
    why: str = ""
    exception_means: str = ""
    applies: str = ""  # what the reader ticked; empty = not yet reviewed
    # filled by the parser from `formal`
    objects: tuple[str, ...] = ()
    quantities: tuple[tuple[str, str], ...] = ()  # (object, quantity)
    parameters: tuple[str, ...] = ()
    parts: dict = field(default_factory=dict, hash=False, compare=False)


@dataclass
class Foundation:
    path: Path
    objects: dict[str, dict[str, str]] = field(default_factory=dict)
    quantities: dict[tuple[str, str], dict[str, str]] = field(default_factory=dict)
    tolerances: dict[str, Tolerance] = field(default_factory=dict)
    min_share: float = 1.0
    parameters: dict[str, dict[str, str]] = field(default_factory=dict)
    rules: list[Rule] = field(default_factory=list)
    refused: list[tuple[str, str]] = field(default_factory=list)  # (rule id, why)
    open_questions: list[str] = field(default_factory=list)


class NotAFoundationDocument(ValueError):
    """The file does not have the shape a foundation document must have."""


# ---------------------------------------------------------------- docx


def _text(node) -> str:
    return "".join(t.text or "" for t in node.iter(f"{_W}t")).strip()


def _blocks(path: Path):
    """Yield ("heading", text) / ("para", text) / ("table", rows) in order."""
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    body = root.find(f"{_W}body")
    for child in body:
        if child.tag == f"{_W}tbl":
            rows = [[_text(cell) for cell in row.findall(f"{_W}tc")]
                    for row in child.findall(f"{_W}tr")]
            yield "table", rows
        elif child.tag == f"{_W}p":
            text = _text(child)
            if not text:
                continue
            style = child.find(f"{_W}pPr/{_W}pStyle")
            name = style.get(f"{_W}val", "") if style is not None else ""
            is_heading = name.replace(" ", "").lower() in ("heading1", "title")
            yield ("heading" if is_heading else "para"), text


def _sections(path: Path) -> dict[str, dict]:
    sections: dict[str, dict] = {}
    current = None
    for kind, value in _blocks(path):
        if kind == "heading":
            key = re.sub(r"^\d+[.)]?\s*", "", value).strip().lower()
            current = sections.setdefault(key, {"paras": [], "tables": []})
        elif current is not None:
            current["paras" if kind == "para" else "tables"].append(value)
    return sections


def _table(sections: dict, heading: str, header: list[str]) -> list[dict[str, str]]:
    section = next((v for k, v in sections.items() if k.startswith(heading)), None)
    if section is None:
        raise NotAFoundationDocument(f"no section headed '{heading}'")
    wanted = [h.lower() for h in header]
    for rows in section["tables"]:
        if rows and [c.lower() for c in rows[0]] == wanted:
            return [dict(zip(header, row)) for row in rows[1:] if any(row)]
    raise NotAFoundationDocument(
        f"section '{heading}' has no table with the columns {header}")


def _number(text: str) -> float | None:
    text = text.strip().replace(",", ".")
    if text in ("", "-", "–", "—", "n/a"):
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


# ---------------------------------------------------------------- rules


_OP = r"(<=|>=|=)"
_SUM = (rf"sum\(({_NAME})\.({_NAME})"
        rf"(?:\s+where\s+({_NAME})\.({_NAME})\s*(!=|=)\s*({_PARAM}))?\)"
        rf"\s+by\s+({_NAME})\.({_NAME})")
_STORED = rf"({_NAME})\.({_NAME})\s+by\s+({_NAME})\.({_NAME})"


def _sum_term(groups) -> dict:
    """One `sum(object.quantity [where object.status = PARAM]) by object.key`."""
    obj, measure, f_obj, f_quantity, f_op, f_param, k_obj, key = groups
    if k_obj != obj or (f_obj and f_obj != obj):
        raise ValueError("a sum, its filter and its key must stay within "
                         "one object")
    term = {"object": obj, "measure": measure, "key": key, "stored": False,
            "filter": None}
    if f_quantity:
        term["filter"] = {"quantity": f_quantity, "op": f_op, "parameter": f_param}
    return term


def _term_names(term: dict) -> tuple[list, list]:
    quantities = [(term["object"], term["measure"]), (term["object"], term["key"])]
    parameters = []
    if term.get("filter"):
        quantities.append((term["object"], term["filter"]["quantity"]))
        parameters.append(term["filter"]["parameter"])
    return quantities, parameters


def _parse_formal(kind: str, formal: str) -> dict:
    """The formal line as its parts. Raises ValueError with the reason."""
    formal = " ".join(formal.split())
    if kind == "IDENTITY":
        match = re.fullmatch(rf"({_NAME}):\s*(.+?)\s*{_OP}\s*(.+)", formal)
        if not match:
            raise ValueError("expected `object: left = right` (or <=, >=)")
        obj, left, op, right = match.groups()
        for side in (left, right):
            if re.search(r"[^a-z0-9_+\-*/(). ]", side):
                raise ValueError(
                    f"`{side}` uses something other than quantity names, "
                    "numbers, + - * / and parentheses")
        names = sorted(set(re.findall(_NAME, left + " " + right)))
        return {"object": obj, "left": left, "right": right, "op": op,
                "quantities": [(obj, n) for n in names]}
    if kind == "UNIQUE":
        match = re.fullmatch(rf"({_NAME}):\s*({_NAME}(?:\s*,\s*{_NAME})*)", formal)
        if not match:
            raise ValueError("expected `object: quantity_a, quantity_b`")
        obj = match.group(1)
        keys = [k.strip() for k in match.group(2).split(",")]
        return {"object": obj, "keys": keys,
                "quantities": [(obj, k) for k in keys]}
    if kind == "REFERENCE":
        match = re.fullmatch(
            rf"({_NAME})\.({_NAME})\s*->\s*({_NAME})\.({_NAME})", formal)
        if not match:
            raise ValueError("expected `object.quantity -> other_object.quantity`")
        child, ckey, parent, pkey = match.groups()
        return {"child": child, "child_key": ckey, "parent": parent,
                "parent_key": pkey,
                "quantities": [(child, ckey), (parent, pkey)]}
    if kind == "CONDITION":
        match = re.fullmatch(
            rf"({_NAME}):\s*when\s+({_NAME})\s*=\s*({_PARAM})\s+then\s+"
            rf"({_NAME})\s+(present|absent)", formal)
        if not match:
            raise ValueError(
                "expected `object: when status = PARAMETER then quantity "
                "present|absent`")
        obj, status, param, quantity, expect = match.groups()
        return {"object": obj, "status": status, "parameter": param,
                "quantity": quantity, "expect": expect,
                "quantities": [(obj, status), (obj, quantity)],
                "parameters": [param]}
    if kind == "TOTAL":
        match = re.fullmatch(rf"{_SUM}\s*{_OP}\s*{_SUM}", formal)
        if match:
            g = match.groups()
            left, op, right = _sum_term(g[:8]), g[8], _sum_term(g[9:])
        else:
            match = re.fullmatch(rf"{_SUM}\s*{_OP}\s*{_STORED}", formal)
            if not match:
                raise ValueError(
                    "expected `sum(object.quantity) by object.key = "
                    "other.quantity by other.key`, or a sum on both sides")
            g = match.groups()
            left, op = _sum_term(g[:8]), g[8]
            t_obj, t_q, t_obj2, t_key = g[9:]
            if t_obj != t_obj2:
                raise ValueError("each side must stay within one object")
            right = {"object": t_obj, "measure": t_q, "key": t_key,
                     "stored": True, "filter": None}
        quantities, parameters = [], []
        for term in (left, right):
            q, p = _term_names(term)
            quantities += q
            parameters += p
        return {"terms": [left, right], "op": op, "detail": left["object"],
                "quantities": quantities, "parameters": parameters}
    if kind == "DIFFERENCE":
        match = re.fullmatch(rf"{_SUM}\s*-\s*{_SUM}\s*=\s*{_SUM}", formal)
        if not match:
            raise ValueError("expected `sum(..) by .. - sum(..) by .. = "
                             "sum(..) by ..`")
        g = match.groups()
        terms = [_sum_term(g[0:8]), _sum_term(g[8:16]), _sum_term(g[16:24])]
        quantities, parameters = [], []
        for term in terms:
            q, p = _term_names(term)
            quantities += q
            parameters += p
        return {"terms": terms, "op": "=", "detail": terms[0]["object"],
                "quantities": quantities, "parameters": parameters}
    raise ValueError(f"unknown kind {kind!r} — one of {', '.join(KINDS)}")


def read_foundation(path: str | Path) -> Foundation:
    path = Path(path)
    sections = _sections(path)
    out = Foundation(path=path)

    for row in _table(sections, "business objects",
                      ["Object", "Meaning", "One record is"]):
        out.objects[row["Object"].strip()] = {
            "meaning": row["Meaning"], "record": row["One record is"]}
    for row in _table(sections, "quantities",
                      ["Object", "Quantity", "Type", "Meaning"]):
        out.quantities[(row["Object"].strip(), row["Quantity"].strip())] = {
            "type": row["Type"].strip().lower(), "meaning": row["Meaning"]}
    for row in _table(sections, "tolerances",
                      ["Class", "Applies to", "Absolute", "Relative", "Reasoning"]):
        name = row["Class"].strip()
        out.tolerances[name] = Tolerance(
            name, _number(row["Absolute"]), _number(row["Relative"]),
            row["Applies to"], row["Reasoning"])
    tolerance_text = " ".join(
        next(v for k, v in sections.items() if k.startswith("tolerances"))["paras"])
    share = re.search(r"MIN_SHARE\s*=\s*([01](?:[.,]\d+)?)", tolerance_text)
    if not share:
        raise NotAFoundationDocument(
            "the Tolerances section states no `MIN_SHARE = 0.xx`")
    out.min_share = float(share.group(1).replace(",", "."))
    for row in _table(sections, "company parameters",
                      ["Parameter", "Meaning", "Example"]):
        out.parameters[row["Parameter"].strip()] = {
            "meaning": row["Meaning"], "example": row["Example"]}

    header = ["ID", "Name", "Statement", "Kind", "Formal", "Tolerance",
              "Why it must hold", "An exception usually means", "Applies to us"]
    for row in _table(sections, "rules", header):
        rule_id, kind = row["ID"].strip(), row["Kind"].strip().upper()
        try:
            parts = _parse_formal(kind, row["Formal"])
            for obj, quantity in parts["quantities"]:
                if obj not in out.objects:
                    raise ValueError(f"object `{obj}` is not defined")
                if (obj, quantity) not in out.quantities:
                    raise ValueError(
                        f"quantity `{obj}.{quantity}` is not defined")
            for param in parts.get("parameters", []):
                if param not in out.parameters:
                    raise ValueError(f"parameter `{param}` is not defined")
            tolerance = row["Tolerance"].strip()
            if tolerance not in out.tolerances:
                raise ValueError(f"tolerance class `{tolerance}` is not defined")
        except ValueError as exc:
            out.refused.append((rule_id, str(exc)))
            continue
        out.rules.append(Rule(
            id=rule_id, name=row["Name"], statement=row["Statement"],
            kind=kind, formal=" ".join(row["Formal"].split()),
            tolerance=tolerance, why=row["Why it must hold"],
            exception_means=row["An exception usually means"],
            applies=row["Applies to us"].strip(),
            objects=tuple(sorted({o for o, _ in parts["quantities"]})),
            quantities=tuple(parts["quantities"]),
            parameters=tuple(parts.get("parameters", [])),
            parts=parts,
        ))

    last = next((v for k, v in sections.items()
                 if k.startswith("what this document cannot decide")), None)
    if last:
        out.open_questions = list(last["paras"])
    return out
