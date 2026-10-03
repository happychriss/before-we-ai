"""Referential integrity over the YAML files.

No database enforces references here, so this check is mandatory, not
optional — every ID a file mentions must resolve to an existing object.
Returns findings instead of raising so a report can list them all.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from before_we_ai.store.repository import ProjectStore


def check_integrity(store: "ProjectStore") -> list[str]:
    findings: list[str] = []

    for claim in store.claims.values():
        for eid in claim.evidence_ids:
            if eid not in store.evidence:
                findings.append(f"claim {claim.id}: dangling evidence reference {eid}")
        for dep in claim.depends_on:
            if dep not in store.claims:
                findings.append(f"claim {claim.id}: dangling dependency {dep}")
        if claim.derived_from and claim.derived_from not in store.claims:
            findings.append(
                f"claim {claim.id}: dangling parent reference {claim.derived_from}"
            )
        if claim.derived_from_evidence and claim.derived_from_evidence not in store.evidence:
            findings.append(
                f"claim {claim.id}: dangling origin-evidence reference "
                f"{claim.derived_from_evidence}"
            )
        for sid in claim.source_ids:
            if sid not in store.sources:
                findings.append(f"claim {claim.id}: dangling source reference {sid}")

    for record in store.evidence.values():
        if record.claim_id and record.claim_id not in store.claims:
            findings.append(
                f"evidence {record.id}: dangling claim reference {record.claim_id}"
            )
        if record.check_plan_id and record.check_plan_id not in store.checks:
            findings.append(
                f"evidence {record.id}: dangling check reference {record.check_plan_id}"
            )

    for check in store.checks.values():
        if check.claim_id and check.claim_id not in store.claims:
            findings.append(
                f"check {check.id}: dangling claim reference {check.claim_id}"
            )

    for card in store.questions.values():
        for cid in card.claim_ids:
            if cid not in store.claims:
                findings.append(f"question {card.id}: dangling claim reference {cid}")

    for required in store.required.values():
        if required.request_id not in store.requests:
            findings.append(
                f"required knowledge {required.id}: dangling request reference "
                f"{required.request_id}"
            )
        for item in required.items:
            for link in item.satisfied_by:
                if link.claim_id not in store.claims:
                    findings.append(
                        f"required knowledge {required.id}: {item.ref()} is "
                        f"linked to missing claim {link.claim_id}"
                    )

    for act in store.acts.values():
        if act.request_id not in store.requests:
            findings.append(
                f"knowledge act {act.id}: dangling request reference "
                f"{act.request_id}"
            )
        if act.claim_id and act.claim_id not in store.claims:
            findings.append(
                f"knowledge act {act.id}: {act.ref} is linked to missing "
                f"claim {act.claim_id}"
            )

    for profile in store.profiles.values():
        if profile.source_id not in store.sources:
            findings.append(
                f"profile {profile.id}: dangling source reference {profile.source_id}"
            )

    return findings
