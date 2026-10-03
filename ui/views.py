"""What the pages show — read from the store on every request, never cached.

Everything here is a plain reading of claims, evidence, questions and the
derived ReadinessMap. No status is decided in this module: a view that
re-derived a verdict would be a second place where truth could live.
"""

from collections import Counter

from before_we_ai.core import Actor, ClaimStatus, EvidenceType
from before_we_ai.core.objects import ConceptClaim, MappingClaim
from before_we_ai.readiness import evaluate_request
from before_we_ai.stages import STAGES
from before_we_ai.statements import rival_claims
from before_we_ai.store import ProjectStore

from ui import pipeline

STATUS_ORDER = ("business-confirmed", "test-supported", "proposed",
                "unresolved", "contradicted")
STATUS_LABEL = {
    "proposed": "Proposed",
    "test-supported": "Test-supported",
    "contradicted": "Contradicted",
    "unresolved": "Unresolved",
    "business-confirmed": "Confirmed by a person",
}
VERDICT_LABEL = {
    "ready": "Ready",
    "ready_with_limitations": "Ready with limitations",
    "blocked": "Blocked",
}
GROUND_LABEL = {
    "elected": "settled",
    "slot_derivation": "settled by a law",
    "stated_rule": "settled",
    "waived": "waived",
    "undecided": "needs a decision",
    "nothing_proposed": "nothing found",
    "all_contradicted": "contradicted by the data",
}
ACTOR_LABEL = {"ai": "AI", "check": "Check", "human": "Person",
               "system": "System"}


def _when(value) -> str:
    return value.strftime("%H:%M:%S") if value else ""


def _binding(claim) -> str:
    if not isinstance(claim, MappingClaim):
        return ""
    binding = dict(claim.binding)
    if "column" in binding:
        return binding["column"]
    if "table" in binding:
        return binding["table"]
    return ", ".join(f"{k}={v}" for k, v in sorted(binding.items()))


def evidence_view(s: ProjectStore, record) -> dict:
    payload = record.payload or {}
    view = {
        "type": record.type.value,
        "actor": ACTOR_LABEL.get(record.actor.value, record.actor.value),
        "stale": record.stale,
        "when": _when(record.created_at),
        "verdict": record.verdict.value if record.verdict else "",
        "title": "",
        "detail": "",
        "sql": "",
        "samples": [],
    }
    if record.type is EvidenceType.CHECK_RESULT:
        template = payload.get("template", "check")
        spec = pipeline.REGISTRY.get(template)
        view["title"] = f"Check: {template}"
        view["detail"] = (
            f"{record.exception_count or 0:,} exceptions in "
            f"{record.population or 0:,} rows — {payload.get('summary', '')}"
        )
        view["tests"] = spec.tests if spec else ""
        view["sql"] = payload.get("sql", "")
        view["samples"] = record.exception_samples[:3]
    elif record.type is EvidenceType.DOCUMENT_ANCHOR:
        view["title"] = (f"Quote from {payload.get('source')}, "
                         f"page {payload.get('page')}")
        view["detail"] = str(payload.get("quote", ""))
        view["quote"] = True
    elif record.type is EvidenceType.CONFIRMATION:
        scope = record.scope.label() if record.scope else ""
        view["title"] = "Confirmed by a person"
        view["detail"] = " · ".join(
            part for part in (f"scope: {scope}" if scope else "",
                              str(payload.get("note", ""))) if part)
    elif record.type is EvidenceType.TESTIMONIAL:
        view["title"] = "A person said"
        view["detail"] = record.statement or ""
        view["quote"] = True
    else:
        view["title"] = f"Declaration: {payload.get('rule', '')}"
        view["detail"] = f"{payload.get('table', '')}.{payload.get('column', '')}"
    return view


def claim_view(s: ProjectStore, claim) -> dict:
    if isinstance(claim, MappingClaim):
        kind = "Role candidate"
    elif isinstance(claim, ConceptClaim):
        kind = "Definition"
    else:
        kind = "Relationship"
    evidence = sorted(s.evidence_for(claim), key=lambda e: e.created_at)
    return {
        "id": claim.id,
        "statement": claim.statement,
        "status": claim.status.value,
        "status_label": STATUS_LABEL[claim.status.value],
        "kind": kind,
        "role": getattr(claim, "role", ""),
        "binding": _binding(claim),
        "author": ACTOR_LABEL.get(claim.created_by.value, claim.created_by.value),
        "predicate": claim.predicate.name if claim.predicate else "",
        "evidence": [evidence_view(s, e) for e in evidence],
        "checks_pass": sum(1 for e in evidence
                           if e.verdict and e.verdict.value == "pass"),
        "checks_fail": sum(1 for e in evidence
                           if e.verdict and e.verdict.value == "fail"),
    }


def _request(s: ProjectStore):
    return next(iter(sorted(s.requests.values(), key=lambda r: r.created_at)),
                None)


def readiness(s: ProjectStore) -> dict | None:
    """The ReadinessMap as the engine derives it, plus what a person can do
    about each open item."""
    request = _request(s)
    if request is None:
        return None
    result = evaluate_request(s, pipeline.guide(), request.id)
    cards = list(s.questions.values())
    items = []
    for judged in result.items:
        candidates = []
        card_id = ""
        for claim_id in judged.claim_ids:
            claim = s.claims.get(claim_id)
            if claim is None:
                continue
            view = claim_view(s, claim)
            view["can_confirm"] = (
                not judged.satisfied
                and claim.status is not ClaimStatus.CONTRADICTED
            )
            candidates.append(view)
        for card in cards:
            if set(card.claim_ids) & set(judged.claim_ids) and rival_claims(
                    s, card.claim_ids):
                card_id = card.id
                break
        knowledge = judged.item
        items.append({
            "ref": judged.ref,
            "kind": knowledge.kind.value,
            "why": knowledge.why,
            "satisfied": judged.satisfied,
            "structural": judged.structural,
            "ground": judged.ground.value,
            "ground_label": GROUND_LABEL.get(judged.ground.value,
                                             judged.ground.value),
            "because": judged.because,
            "waived": judged.ground.value == "waived",
            "candidates": candidates,
            "card_id": card_id,
        })
    return {
        "request_id": request.id,
        "question": request.question,
        "requested_output": request.requested_output,
        "answer_type": request.answer_type,
        "verdict": result.verdict.value,
        "verdict_label": VERDICT_LABEL[result.verdict.value],
        "reason": result.reason(),
        "confirmed": result.confirmed,
        "items": items,
        "open": [i for i in items if not i["satisfied"]],
        "settled": [i for i in items if i["satisfied"]],
        # satisfied only because a person set it aside — the verdict counts
        # these as supported, so the page says so next to it
        "waived": [i for i in items if i["waived"]],
    }


def findings(s: ProjectStore, ready: dict | None) -> list[dict]:
    """Question cards that are not a choice on this answer's path."""
    on_path = {i["card_id"] for i in (ready["items"] if ready else [])}
    out = []
    for card in sorted(s.questions.values(), key=lambda c: c.created_at):
        if card.id in on_path:
            continue
        claims = [claim_view(s, s.claims[cid]) for cid in card.claim_ids
                  if cid in s.claims]
        out.append({
            "id": card.id,
            "question": card.question,
            "finding": card.finding,
            "deferred": card.deferred is not None,
            "stale": card.stale,
            "claims": claims,
        })
    return out


def decision_log(s: ProjectStore) -> list[dict]:
    """Everything a person did, oldest first."""
    entries = []
    for record in s.evidence.values():
        if record.actor is not Actor.HUMAN:
            continue
        claim = s.claims.get(record.claim_id or "")
        if record.type is EvidenceType.CONFIRMATION:
            entries.append((record.created_at, "Confirmed",
                            claim.statement if claim else ""))
        elif record.type is EvidenceType.TESTIMONIAL:
            entries.append((record.created_at, "Stated",
                            record.statement or ""))
    for act in s.acts.values():
        if act.actor is not Actor.HUMAN:
            continue
        what = {
            "waive": ("Waived", f"{act.ref} — {act.reason}"),
            "require_again": ("Required again", act.ref or ""),
            "confirm": ("Confirmed the dependency list",
                        f"answer type {act.answer_type}"),
            "link": ("Linked", act.ref or ""),
            "add": ("Added a dependency", act.item.name if act.item else ""),
        }[act.kind.value]
        entries.append((act.created_at, *what))
    for card in s.questions.values():
        if card.deferred:
            entries.append((card.deferred.at, "Deferred", card.question))
    entries.sort(key=lambda e: e[0])
    return [{"when": _when(at), "what": what, "detail": detail}
            for at, what, detail in entries]


def sources(s: ProjectStore) -> list[dict]:
    tables: dict[str, dict[str, int]] = {}
    for profile in s.profiles.values():
        per = tables.setdefault(profile.source_id, {})
        per[profile.table] = max(per.get(profile.table, 0),
                                 int(profile.stats.get("row_count") or 0))
    columns = Counter(p.source_id for p in s.profiles.values())
    documents = {d.source_id: d for d in s.documents.values()}
    declared = {entry["name"]: entry for entry in pipeline.SOURCES}
    out = []
    names = [src.name for src in s.sources.values()]
    for src in sorted(s.sources.values(), key=lambda x: x.name):
        doc = documents.get(src.id)
        out.append({
            "name": src.name,
            "kind": src.kind,
            "description": src.description,
            "file": src.location.rsplit("/", 1)[-1],
            "tables": sorted(tables.get(src.id, {}).items()),
            "columns": columns.get(src.id, 0),
            "pages": doc.pages if doc else 0,
            "passages": doc.chunk_count if doc else 0,
            "is_document": src.kind in ("pdf", "text"),
            "read": bool(doc) or src.id in tables,
        })
    # declared but not read yet: the run has not reached the scan
    for name, entry in sorted(declared.items()):
        if name not in names:
            out.append({
                "name": name, "kind": entry["kind"],
                "description": entry.get("description", ""),
                "file": str(entry["location"]).rsplit("/", 1)[-1],
                "tables": [], "columns": 0, "pages": 0, "passages": 0,
                "is_document": entry["kind"] in ("pdf", "text"),
                "read": False,
            })
    return out


def claims(s: ProjectStore) -> list[dict]:
    rank = {status: i for i, status in enumerate(STATUS_ORDER)}
    views = [claim_view(s, claim) for claim in s.claims.values()]
    views.sort(key=lambda v: (rank.get(v["status"], 9), v["kind"],
                              v["statement"]))
    return views


def overview(s: ProjectStore | None) -> dict:
    finished = pipeline.done()
    steps = [{
        "key": step.key, "stage": step.stage, "title": step.title,
        "actor": step.actor, "detail": step.detail,
        "done": step.key in finished, "summary": finished.get(step.key, ""),
    } for step in pipeline.STEPS]
    upcoming = pipeline.next_step()
    view = {
        "steps": steps,
        "next": upcoming.key if upcoming else "",
        "complete": upcoming is None,
        "started": bool(finished),
        "progress": len(finished),
        "total": len(pipeline.STEPS),
        "question": pipeline.DEMO_QUESTION,
        "stages": [],
        "ready": None,
    }
    if s is None:
        view["stages"] = [{"number": st.number, "name": st.name,
                           "title": st.title, "actor": st.actor,
                           "count": "", "done": False} for st in STAGES]
        return view

    ready = readiness(s) if "request" in finished else None
    status = Counter(c.status.value for c in s.claims.values())
    ai = pipeline.ai_claims(s)
    checks = [e for e in s.evidence.values()
              if e.type is EvidenceType.CHECK_RESULT]
    verdicts = Counter(e.verdict.value for e in checks if e.verdict)
    human_confirmed = {
        e.claim_id for e in s.evidence.values()
        if e.type is EvidenceType.CONFIRMATION and e.actor is Actor.HUMAN}
    promoted = [c for c in ai if c.status is not ClaimStatus.PROPOSED]
    by_check = [c for c in promoted if c.id not in human_confirmed and any(
        e.actor is Actor.CHECK for e in s.evidence_for(c))]
    by_human = [c for c in promoted if c.id in human_confirmed]
    by_nobody = [c for c in promoted
                 if c not in by_check and c not in by_human]
    open_cards = [c for c in s.questions.values() if not c.deferred]
    tables = {p.table for p in s.profiles.values()}
    passages = sum(d.chunk_count for d in s.documents.values())
    total = sum(status.values())

    stage_done = {
        "0": "inputs" in finished, "1": "request" in finished,
        "2": "documents" in finished, "3": "read_documents" in finished,
        "4": "test" in finished, "5": "tell" in finished,
        "6": upcoming is None,
    }
    stage_count = {
        "0": f"{len(pipeline.SOURCES)} sources",
        "1": (ready["answer_type"].replace("_", " ") if ready else ""),
        "2": f"{len(s.profiles)} columns · {passages} passages",
        "3": f"{len(ai)} claims · {len(s.checks)} checks",
        "4": f"{verdicts.get('pass', 0)} pass · {verdicts.get('fail', 0)} fail",
        "5": f"{len(open_cards)} questions",
        "6": ready["verdict_label"] if ready and upcoming is None else "",
    }
    view["stages"] = [{
        "number": st.number, "name": st.name, "title": st.title,
        "actor": st.actor, "done": stage_done[st.number],
        "count": stage_count[st.number] if stage_done[st.number] else "",
    } for st in STAGES]
    view.update({
        "ready": ready,
        "counts": {
            "sources": len(s.sources) or len(pipeline.SOURCES),
            "tables": len(tables),
            "columns": len(s.profiles),
            "documents": len(s.documents),
            "passages": passages,
            "claims": total,
            "checks": len(checks),
            "pass": verdicts.get("pass", 0),
            "fail": verdicts.get("fail", 0),
            "inconclusive": verdicts.get("inconclusive", 0),
            "questions": len(open_cards),
            "deferred": len(s.questions) - len(open_cards),
        },
        "status": [{
            "key": key, "label": STATUS_LABEL[key], "n": status.get(key, 0),
            "pct": (100 * status.get(key, 0) / total) if total else 0,
        } for key in STATUS_ORDER],
        "authority": {
            "proposed_by_ai": len(ai),
            "by_check": len(by_check),
            "by_human": len(by_human),
            "by_ai": len(by_nobody),
            "still_proposed": len(ai) - len(promoted),
        },
        "log": decision_log(s),
    })
    return view
