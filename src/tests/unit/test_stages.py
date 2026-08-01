"""The stage spine has one home, and every surface renders it.

Three surfaces describe the same seven stages: the readiness report's
diagram and section anchors, the walkthrough's scripts, and
`docs/architecture.md`. They disagreed once — two scripts feeding one
section, a section with no script, one script feeding two sections. These
tests are what stops that returning.
"""

import re
from pathlib import Path

from before_we_ai.stages import BOUNDARY_BEFORE, BY_NAME, FRAME, STAGES

REPO = Path(__file__).resolve().parents[3]


def test_the_spine_is_numbered_0_to_6_without_gaps():
    assert [s.number for s in STAGES] == [str(i) for i in range(7)]
    assert len({s.name for s in STAGES}) == len(STAGES)


def test_every_stage_says_who_is_responsible_and_what_it_moves():
    """A stage without an actor is a step; a stage is a change in what is
    known, and someone is answerable for it."""
    for s in STAGES:
        assert s.actor and s.reads and s.produces and s.heading


def test_the_frame_opens_at_the_question_and_closes_at_the_verdict():
    """Stage 0 is outside it: declared inputs are the precondition every
    question shares, and the request contract reads the domain guide — so
    a question cannot come before the vocabulary it is decomposed against."""
    assert FRAME == (STAGES[1].name, STAGES[-1].name)
    assert STAGES[0].name == "inputs"


def test_the_boundary_falls_where_authorship_shifts():
    """Left of it everything is a proposal. The stage before must be the
    AI's and the stage at it must be the checks'."""
    names = [s.name for s in STAGES]
    at = names.index(BOUNDARY_BEFORE)
    assert "AI" in STAGES[at - 1].actor
    assert "check" in BY_NAME[BOUNDARY_BEFORE].actor


def test_the_walkthrough_has_a_script_for_every_stage():
    """And no numbered script for anything that is not a stage."""
    scripts = sorted(p.name for p in (REPO / "validation" / "scripts").glob("*.sh")
                     if p.name[0].isdigit())
    numbers = {re.match(r"(\d+)", name).group(1) for name in scripts}
    assert numbers == {s.number for s in STAGES}
    for name in scripts:
        stage = BY_NAME[[s.name for s in STAGES
                         if s.number == re.match(r"(\d+)", name).group(1)][0]]
        assert stage.name in name or stage.number == name[0], name


def test_the_architecture_table_matches_the_data():
    """The doc shows the spine for reading; the data is the home. A row that
    has drifted is a doc that will be believed over the code."""
    doc = (REPO / "docs" / "architecture.md").read_text(encoding="utf-8")
    spine = doc[doc.index("## The stage spine"):]
    for s in STAGES:
        row = f"| {s.number} | **{s.name.capitalize()}** — {s.heading} | {s.actor} |"
        assert row in spine, f"architecture.md has drifted for stage {s.number}"
