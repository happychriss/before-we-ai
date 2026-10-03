"""Drop files in, press scan.

The layout has reserved `sources/` as a drop directory since M2 and
nothing ever read it: `init_project()` wrote `sources: []` and a human
hand-authored every entry. These tests are almost entirely about the one
word that makes discovery safe — **merge**. Discovery proposes; it never
edits, reorders or removes what a person wrote, and re-running it is a
no-op. Everything below is a way of asking that same question.
"""

import pytest
import yaml

from before_we_ai.sources.discover import discover, source_name
from before_we_ai.store import init_project
from before_we_ai.store.layout import CONFIG_FILE

pytestmark = pytest.mark.unit


def _config(root) -> dict:
    return yaml.safe_load((root / CONFIG_FILE).read_text(encoding="utf-8"))


def _sources(root) -> list[dict]:
    return _config(root).get("sources") or []


@pytest.fixture
def project(tmp_path):
    root = init_project(tmp_path / "p")
    return root


def _drop(root, relative: str, content: str = "a,b\n1,2\n"):
    path = root / "sources" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


class TestWhatItFinds:
    def test_it_reads_the_directory_nothing_ever_read(self, project):
        _drop(project, "ledger.csv")
        result = discover(project)
        assert [e["name"] for e in result.added] == ["ledger"]
        assert _sources(project)[0] == {
            "name": "ledger", "kind": "csv", "location": "sources/ledger.csv",
        }

    @pytest.mark.parametrize("filename,kind", [
        ("a.csv", "csv"), ("b.xlsx", "xlsx"),
        ("c.pdf", "pdf"), ("d.duckdb", "duckdb"),
    ])
    def test_kind_comes_from_the_suffix(self, project, filename, kind):
        _drop(project, filename)
        assert discover(project).added[0]["kind"] == kind

    def test_a_subdirectory_becomes_part_of_the_name(self, project):
        """Two files with the same stem in different folders are two
        sources, and the name says where each one actually is."""
        _drop(project, "noise/report.pdf")
        _drop(project, "report.pdf")
        names = sorted(e["name"] for e in discover(project).added)
        assert names == ["noise__report", "report"]

    def test_the_location_is_relative_to_the_project(self, project):
        _drop(project, "noise/report.pdf")
        assert discover(project).added[0]["location"] == "sources/noise/report.pdf"


class TestItProposesAndNeverOverwrites:
    def test_a_hand_authored_entry_survives_untouched(self, project):
        """Somebody who set a scope did so deliberately."""
        path = _drop(project, "ledger.csv")
        config = _config(project)
        config["sources"] = [{"name": "the_ledger", "kind": "csv",
                              "location": "sources/ledger.csv",
                              "scope": {"entity": "DE"}}]
        (project / CONFIG_FILE).write_text(yaml.safe_dump(config))

        result = discover(project)
        assert result.added == []
        assert _sources(project)[0]["scope"] == {"entity": "DE"}
        assert _sources(project)[0]["name"] == "the_ledger"
        assert path.exists()

    def test_the_same_file_is_not_declared_twice_under_two_names(self, project):
        """Matched on the resolved path, not the string it was written as —
        otherwise one file gets profiled twice under two names."""
        _drop(project, "ledger.csv")
        config = _config(project)
        config["sources"] = [{"name": "hand_named", "kind": "csv",
                              "location": str(project / "sources" / "ledger.csv")}]
        (project / CONFIG_FILE).write_text(yaml.safe_dump(config))
        assert discover(project).added == []

    def test_running_it_twice_adds_nothing(self, project):
        """The same idempotence contract scan already keeps."""
        _drop(project, "ledger.csv")
        discover(project)
        before = _sources(project)
        assert discover(project).added == []
        assert _sources(project) == before

    def test_an_entry_outside_the_drop_directory_is_left_alone(self, project,
                                                               tmp_path):
        """A connected database. Its location is the thing a person got
        right, and discovery has nothing to say about it."""
        external = tmp_path / "warehouse.duckdb"
        external.write_bytes(b"")
        config = _config(project)
        config["sources"] = [{"name": "warehouse", "kind": "duckdb",
                              "location": str(external)}]
        (project / CONFIG_FILE).write_text(yaml.safe_dump(config))

        discover(project)
        assert _sources(project)[0]["location"] == str(external)

    def test_new_entries_are_appended_after_the_declared_ones(self, project):
        _drop(project, "new.csv")
        config = _config(project)
        config["sources"] = [{"name": "declared", "kind": "csv",
                              "location": "elsewhere/old.csv"}]
        (project / CONFIG_FILE).write_text(yaml.safe_dump(config))
        discover(project)
        assert [e["name"] for e in _sources(project)] == ["declared", "new"]

    def test_nothing_else_in_the_config_is_disturbed(self, project):
        config = _config(project)
        config["llm"] = {"offline": True}
        config["tolerances"] = {"balance": 0.01}
        (project / CONFIG_FILE).write_text(yaml.safe_dump(config))
        _drop(project, "ledger.csv")
        discover(project)
        assert _config(project)["llm"] == {"offline": True}
        assert _config(project)["tolerances"] == {"balance": 0.01}


class TestNothingIsSkippedSilently:
    def test_an_unreadable_suffix_is_reported(self, project):
        _drop(project, "notes.txt")
        result = discover(project)
        assert result.added == []
        assert result.skipped == [("sources/notes.txt", "no reader for .txt")]

    def test_a_suffix_nothing_implements_is_not_guessed_at(self, project):
        """`.xls` is the tempting one — openpyxl does not read it, so
        inferring `xlsx` turns a clear message here into a parse failure
        three stages later."""
        _drop(project, "legacy.xls")
        assert discover(project).skipped[0][1] == "no reader for .xls"

    def test_a_name_collision_is_reported_rather_than_resolved(self, project):
        _drop(project, "ledger.csv")
        config = _config(project)
        config["sources"] = [{"name": "ledger", "kind": "csv",
                              "location": "elsewhere/other.csv"}]
        (project / CONFIG_FILE).write_text(yaml.safe_dump(config))

        result = discover(project)
        assert result.added == []
        assert "already declared" in result.skipped[0][1]

    def test_editor_litter_is_neither_added_nor_reported(self, project):
        """Reporting noise a person did not put there would train the
        reader to ignore the skipped list, which is the one part of this
        that has to stay worth reading."""
        _drop(project, ".DS_Store", "")
        _drop(project, "~$open.xlsx", "")
        _drop(project, "half.csv.part", "")
        result = discover(project)
        assert result.added == [] and result.skipped == []


class TestTheCautiousPath:
    def test_write_false_changes_nothing_on_disk(self, project):
        _drop(project, "ledger.csv")
        result = discover(project, write=False)
        assert result.added
        assert _sources(project) == []

    def test_an_empty_drop_directory_is_not_an_error(self, project):
        result = discover(project)
        assert result.added == [] and result.skipped == []

    def test_a_missing_drop_directory_is_not_an_error(self, project):
        (project / "sources").rmdir()
        assert discover(project).added == []


def test_the_name_is_a_pure_function_of_the_path(tmp_path):
    root = tmp_path / "p"
    (root / "sources" / "Sub Dir").mkdir(parents=True)
    path = root / "sources" / "Sub Dir" / "My File.csv"
    assert source_name(path, root) == "sub_dir__my_file"


class TestNamingAShippedPack:
    """`domain_guide_file: finance` should mean the pack we ship.

    Until now it was always read as a path relative to the project, so
    the bundled packs could only be reached by spelling out where pip put
    them — which a first-run project has no way to know.
    """

    def test_a_bare_name_resolves_to_the_shipped_pack(self, project):
        from before_we_ai.domains import packaged, resolve_guide

        assert resolve_guide("finance", project) == packaged("finance")
        assert resolve_guide("finance", project).is_file()

    def test_a_real_file_always_wins_over_a_pack_of_the_same_name(self,
                                                                  project):
        """Theirs, not ours. We never shadow a file that exists."""
        from before_we_ai.domains import resolve_guide

        mine = project / "finance"
        mine.write_text("domain: finance\nobjects: {}\n", encoding="utf-8")
        assert resolve_guide("finance", project) == mine

    def test_a_path_stays_a_path_even_when_it_is_missing(self, project):
        """So the caller reports "no such file" about the place the person
        actually named, rather than about a pack they never mentioned."""
        from before_we_ai.domains import resolve_guide

        assert resolve_guide("guides/mine.yaml", project) == \
            project / "guides" / "mine.yaml"

    def test_an_unknown_bare_name_is_left_as_written(self, project):
        from before_we_ai.domains import resolve_guide

        assert resolve_guide("nosuchdomain", project) == project / "nosuchdomain"

    def test_the_shipped_packs_can_be_listed(self):
        from before_we_ai.domains import available

        assert "finance" in available()
