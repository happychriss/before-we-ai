"""Seeded-Recall — the online eval, never a CI gate.

Runs the full M4 pipeline (scan -> V1 -> role proposals -> V2 -> engine ->
role resolution) against the frozen corpus and scores which seeded traps
surfaced as claims, per the recall_set in expected_verdicts.yaml. Reports;
does not gate: the bar is an owner decision taken from real runs
(owner-aligned 2026-07-12: measure first).

Scoring is matcher-based and trap-class-generic in spirit: a trap counts
as recalled when *some* claim grounds the seeded relationship (right
predicate family, right columns) — never by matching an exact expected
wording. The semantic-only class (candidate matrix is blind; only V1
semantics can find it) is counted separately, and a hit there triggers
the leakage protocol, not a celebration: the report points at the logged
request so the prompt bytes can be audited first.

Usage (from src/, venv active; ANTHROPIC_API_KEY for online):

    python tests/eval/seeded_recall.py [--offline] [--keep DIR]
"""

import argparse
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

from _corpus import EXPECTED_VERDICTS, ROLES_FILE, build_corpus_project

from before_we_ai.engine import run_ready
from before_we_ai.llm import (
    bind_probes,
    hypothesize,
    load_roles,
    propose_role_bindings,
    resolve_roles,
)
from before_we_ai.model import Actor, ClaimStatus
from before_we_ai.model.objects import Claim, ConceptClaim, RoleBindingClaim
from before_we_ai.sources import open_catalog
from before_we_ai.store import ProjectStore

# Tokens that must never appear in what the model saw (see the tripwire
# tests); echoed in the report as the first-line leakage check.
LEAK_TOKENS = ("trap", "decoy", "BLIND_", "expected_verdicts", "F27", "Seeded")


@dataclass(frozen=True)
class Matcher:
    """A trap is recalled when some claim matches: predicate in
    ``predicates`` (None = any) and, for every token group, at least one
    token appears in the claim's haystack."""

    groups: tuple[tuple[str, ...], ...]
    predicates: tuple[str, ...] | None = None
    scope: str = "v1"  # v1 | m5_docs | m6_tell | blind


def _m(*groups, predicates=None, scope="v1"):
    return Matcher(tuple(tuple(g) if isinstance(g, (tuple, list)) else (g,)
                         for g in groups),
                   tuple(predicates) if predicates else None, scope)


# One matcher per recall_set trap. Test-side corpus knowledge by design.
# Out-of-scope traps (documents M5, tell statements M6, blind) are listed
# so the report is complete and honest about what V1 could never see.
MATCHERS: dict[str, Matcher] = {
    "F1": _m("de_erp__orders", "de_erp__invoices"),
    "F2": _m("order_reference", ("de_erp__orders", "de_erp__invoices")),
    "F3": _m("invoice_type", ("storno", "reversal", "de_erp__invoices")),
    "F4": _m("credit_notes_legacy"),
    "F5": _m(("kundenmigration", "legacy_id")),
    "F6": _m("customer_hierarchy", predicates=("temporal_validity",)),
    "F7": _m("product_hierarchy_string", predicates=("decodes",)),
    "F8": _m("produktgruppen_marketing",
             ("materials", "material_hierarchy"),
             predicates=("semantic_equivalent",)),
    "F9": _m("territory_plz", predicates=("range_mapping",)),
    "F10": _m("crm_activities", ("sales_reps", "rep_id")),
    "F11": _m("customer_reference", "legacy"),
    "F12": _m("customer_reference", "customers"),
    "F13": _m("crm_activities", ("customer", "prospect")),
    "F14": _m("gl_postings", ("sign", "negative", "haben", "credit convention")),
    "F15": _m(("revenue", "umsatz", "4000")),
    "F16": _m(("cost_center", "project_id")),
    "F17": _m("fx_rates", ("rate_type", "monthly", "spot")),
    "F18": _m("fx_rates", predicates=("covers",)),
    "F19": _m("fx_rates", ("rate_type", "policy", "average")),
    "F20": _m("ar_open_items", ("gl_postings", "invoices")),
    "F21": _m(("revenue", "umsatz"), ("intercompany", "4300", "90001")),
    "F22": _m("intercompany", predicates=("ic_symmetric",)),
    "F23": _m((), scope="m5_docs"),
    "F24": _m((), scope="m5_docs"),
    "F25": _m(("rebate", "bonus", "accrual", "4800")),
    "F26": _m((), scope="m5_docs"),
    "F27": _m("buchungen_report", "gl_postings"),
    "F28": _m(("document_exchange_rate", "amount_doc_currency")),
    "F29": _m((), scope="m6_tell"),
    "BLIND_1": _m((), scope="blind"),
    "BLIND_2": _m((), scope="blind"),
    "BLIND_3": _m((), scope="blind"),
}

SEMANTIC_ONLY = {"F8"}  # T7 class: candidate matrix is blind, only semantics


def _haystack(claim: Claim) -> str:
    parts = [claim.statement,
             json.dumps(claim.predicate.params if claim.predicate else {},
                        sort_keys=True, ensure_ascii=False, default=str)]
    if isinstance(claim, ConceptClaim):
        parts += [claim.term, claim.definition]
    if isinstance(claim, RoleBindingClaim):
        parts.append(json.dumps(claim.binding, sort_keys=True, ensure_ascii=False))
    return " ".join(p for p in parts if p).lower()


def matches(matcher: Matcher, claims: list[Claim]) -> Claim | None:
    for claim in claims:
        if matcher.predicates is not None:
            if claim.predicate is None or claim.predicate.name not in matcher.predicates:
                continue
        haystack = _haystack(claim)
        if all(any(token.lower() in haystack for token in group)
               for group in matcher.groups):
            return claim
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true",
                        help="run from stub fixtures (smoke test of the harness)")
    parser.add_argument("--keep", metavar="DIR",
                        help="build the project here and keep it (default: temp)")
    args = parser.parse_args()

    workdir = Path(args.keep) if args.keep else Path(tempfile.mkdtemp(prefix="recall-"))
    root = build_corpus_project(workdir / "project", offline=args.offline)
    store = ProjectStore(root)
    roles = load_roles(ROLES_FILE)
    scenario = "corpus"  # fixtures and logs share the scenario name

    v1 = hypothesize(root, store=store, scenario=scenario)
    proposals = propose_role_bindings(root, roles=roles, store=store,
                                      scenario=scenario)
    v2 = bind_probes(root, store=store, scenario=scenario)
    con = open_catalog(root)
    try:
        engine = run_ready(store, con)
    finally:
        con.close()
    store = ProjectStore(root)
    role_cards = resolve_roles(store, roles)

    ai_claims = [c for c in store.claims.values() if c.created_by is Actor.AI]

    # -- false promotion (hard invariant, reported not gated) -------------
    false_promotions = [
        c for c in ai_claims
        if c.status is not ClaimStatus.INFERRED
        and not any(store.evidence[eid].actor is Actor.PROBE
                    for eid in c.evidence_ids if eid in store.evidence)
    ]

    # -- leakage first line ------------------------------------------------
    logged_requests = sorted((root / "cache" / "llm_log").glob("*.json"))
    leaks = []
    for path in logged_requests:
        request = json.loads(path.read_text(encoding="utf-8"))["request"]
        blob = (request["system"] + request["user"]).lower()
        leaks += [f"{path.name}: {token}"
                  for token in LEAK_TOKENS if token.lower() in blob]

    # -- recall scoring ----------------------------------------------------
    recall_set = yaml.safe_load(EXPECTED_VERDICTS.read_text(encoding="utf-8"))["recall_set"]
    rows, hits, semantic_hits, in_scope = [], 0, 0, 0
    for trap in recall_set:
        matcher = MATCHERS[trap]
        if matcher.scope != "v1":
            rows.append((trap, f"out of scope ({matcher.scope})", ""))
            continue
        in_scope += 1
        hit = matches(matcher, ai_claims)
        if hit:
            hits += 1
            if trap in SEMANTIC_ONLY:
                semantic_hits += 1
            rows.append((trap, "HIT", hit.statement[:70]))
        else:
            rows.append((trap, "miss", ""))

    usage: dict[str, int] = {}
    for source in (v1.usage, proposals.usage, v2.usage):
        for key, value in source.items():
            usage[key] = usage.get(key, 0) + value

    lines = ["# Seeded-Recall report", ""]
    lines.append(f"mode: {'OFFLINE (stub fixtures — harness smoke, not an eval)' if args.offline else 'online'}")
    lines.append(f"leakage scan of every logged request: "
                 f"{'CLEAN' if not leaks else 'LEAKED: ' + '; '.join(leaks)}")
    lines.append(f"false promotions (must be 0): {len(false_promotions)}")
    for claim in false_promotions:
        lines.append(f"  !! {claim.id} [{claim.status.value}] {claim.statement}")
    lines += [
        "",
        f"claims: {len(v1.claims_created)} hypotheses "
        f"(+{v1.claims_deduped} deduped, {len(v1.skipped)} skipped), "
        f"{len(proposals.claims_created)} role candidates",
        f"probes: {len(v2.probes_created)} bound, {len(v2.unbindable)} unbindable, "
        f"{len(v2.semantic_only)} semantic-only, {len(v2.unanswered)} unanswered",
        f"engine: {len(engine.executed)} probes executed, {len(engine.skipped)} skipped",
        f"role questions: {len(role_cards)}",
        f"token usage: {usage or 'n/a (stub)'}",
        "",
        f"## Recall: {hits}/{in_scope} in-scope traps "
        f"(semantic-only: {semantic_hits}/{len(SEMANTIC_ONLY)})",
        "",
        "| trap | result | matched claim |",
        "|---|---|---|",
    ]
    lines += [f"| {trap} | {result} | {statement} |" for trap, result, statement in rows]
    if semantic_hits:
        lines += [
            "",
            "**Semantic-only trap recalled — run the leakage protocol before "
            "celebrating:** the scan above covers the denylist only; open the "
            "logged requests in cache/llm_log/ and audit what the model saw.",
        ]

    report = "\n".join(lines) + "\n"
    out = root / "cache" / "eval"
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "seeded_recall.md"
    report_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"(report: {report_path})")
    if not args.keep:
        shutil.rmtree(workdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
