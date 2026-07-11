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

    for record in store.evidence.values():
        if record.claim_id and record.claim_id not in store.claims:
            findings.append(
                f"evidence {record.id}: dangling claim reference {record.claim_id}"
            )

    for card in store.questions.values():
        for cid in card.claim_ids:
            if cid not in store.claims:
                findings.append(f"question {card.id}: dangling claim reference {cid}")

    for profile in store.profiles.values():
        if profile.source_id not in store.sources:
            findings.append(
                f"profile {profile.id}: dangling source reference {profile.source_id}"
            )

    return findings
