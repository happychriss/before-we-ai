"""Two entities, one role: what scoped elections change.

The frozen corpus declares no source scopes, so the walkthrough cannot show
this. Here DE and US each own a ledger and a period column, both ledgers pass
the balance law, and the question is asked *for Germany*. Expect: two
journal elections (not one contest with a loser), two period questions that
would have deduplicated into one before M6, and a readiness map that reads
only DE's evidence.

    ./scripts/two-entities.sh [outdir]        # default: validation/data/two-entities
"""
import shutil, subprocess, sys, yaml
from pathlib import Path

from before_we_ai.core import (Actor, AnswerRequest, CheckPlan, CheckVerdict,
                                EvidenceRecord, EvidenceType, MappingClaim,
                                Scope, Source)
from before_we_ai.core.transitions import attach_evidence
from before_we_ai.store import ProjectStore, init_project

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/two-entities")
shutil.rmtree(OUT, ignore_errors=True)
root = init_project(OUT / "project", name="two-entities")
store = ProjectStore(root)

guide = OUT / "guide.yaml"
guide.write_text("""domain: finance
objects:
  journal:
    decided_by: balance
    definition: >-
      The transactional ledger of record: one row per posting line, carrying a
      signed amount; debit and credit lines balance per document.
    fields:
      amount_local:
        decided_by: slot
        fills: amount
        definition: The signed posting amount in local currency.
      period:
        decided_by: clarification
        definition: The posting period, at fiscal-period granularity.
answer_types:
  profit_and_loss_by_dimension:
    definition: >-
      The result of a period, broken out by a dimension the postings carry.
    requires:
      - object: journal
        why: the figures are summed from the ledger of record
      - field: journal.amount_local
        why: it is the number that gets summed
      - field: journal.period
        why: the answer is broken out by month
""", encoding="utf-8")
config = yaml.safe_load((root / "before-ai.yaml").read_text())
config["llm"] = {"domain_guide_file": str(guide)}
(root / "before-ai.yaml").write_text(yaml.safe_dump(config))

def candidate(role, table, scope, source_id):
    c = MappingClaim(statement=f"role '{role}' is played by {table}",
                     created_by=Actor.AI, role=role, scope=scope,
                     binding={"table": table}, source_ids=[source_id])
    store.save_claim(c)
    return c

def passing_balance(claim, column):
    plan = CheckPlan(template="balance", roles=["journal"],
                     params={"journal": claim.binding["table"],
                             "amount": column, "group_column": "period"})
    store.save_check_plan(plan)
    rec = EvidenceRecord(type=EvidenceType.CHECK_RESULT, actor=Actor.CHECK,
                         claim_id=claim.id, check_plan_id=plan.id,
                         verdict=CheckVerdict.PASS, population=4000,
                         exception_count=0)
    store.add_evidence(rec)
    store.save_claim(attach_evidence(claim, rec, []))

for entity, table, amount in (("DE", "de_erp__gl_postings", "betrag"),
                              ("US", "us_erp__gl_postings", "amount_usd")):
    scope = Scope(entity=entity)
    src = Source(name=f"{entity.lower()}_erp", kind="duckdb",
                 location=f"sources/{entity}.duckdb", scope=scope)
    store.save_source(src)
    passing_balance(candidate("journal", table, scope, src.id), amount)
    candidate("period", f"{table}", scope, src.id)

# Classified, not listed: the three dependencies below are expanded from the
# answer type, each wearing the request's scope — which is the point here.
# A scoped question elects per scope, so the same three items read DE's
# evidence and only DE's.
request = AnswerRequest(
    question="Can these files reliably produce actual P&L for Germany by month?",
    requested_output="P&L for the German entity, per month",
    answer_type="profit_and_loss_by_dimension",
    scope=Scope(entity="DE"))
store.save_request(request)

from before_we_ai.llm import load_domain_guide, resolve_mappings
cards = resolve_mappings(ProjectStore(root), load_domain_guide(guide))
print(f"clarification questions drafted: {len(cards)}")
for c in cards:
    print(f"  [{c.scope.label() if c.scope else 'landscape-wide'}] {c.question[:80]}…")

out = OUT / "report.html"
subprocess.run([sys.executable, "-m", "readiness_report", str(root), "-o", str(out)],
               check=True, stdout=subprocess.DEVNULL)
print(f"\nreport: {out}")
