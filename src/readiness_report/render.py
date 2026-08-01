import os
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, PackageLoader, StrictUndefined

from readiness_report import projection


STATUS_COLORS = {
    "proposed": "status-proposed",
    "test-supported": "status-test-supported",
    "contradicted": "status-contradicted",
    "unresolved": "status-unresolved",
    "business-confirmed": "status-business-confirmed",
}

VERDICT_COLORS = {
    "pass": "verdict-pass",
    "fail": "verdict-fail",
    "inconclusive": "verdict-inconclusive",
}

_ENVIRONMENT = Environment(
    loader=PackageLoader("readiness_report", "templates"),
    autoescape=True,
    undefined=StrictUndefined,
    keep_trailing_newline=True,
)
_TEMPLATE = _ENVIRONMENT.get_template("report.html.j2")


def _resource_text(directory: str, name: str) -> str:
    return (
        files("readiness_report")
        .joinpath(directory)
        .joinpath(name)
        .read_text(encoding="utf-8")
    )


_CSS = _resource_text("static", "report.css")
_JS = _resource_text("static", "report.js")


def default_output_path(root: Path) -> Path:
    return root.resolve().parent / f"{root.name}-readiness-report.html"


def write_project_view(
    root: str | Path, output: str | Path | None = None
) -> Path:
    root_path = Path(root).resolve()
    out = (
        Path(output).resolve()
        if output
        else default_output_path(root_path)
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        render_project(root_path, out.parent), encoding="utf-8"
    )
    return out


def render_project(
    root: str | Path, out_dir: str | Path | None = None
) -> str:
    root_path = Path(root).resolve()
    return _TEMPLATE.render(
        view=projection.load_view_model(root_path),
        store_rel=_relative_prefix(root_path, out_dir),
        css=_CSS,
        js=_JS,
        status_colors=STATUS_COLORS,
        verdict_colors=VERDICT_COLORS,
    )


def _relative_prefix(
    root: Path, out_dir: str | Path | None
) -> str:
    """How to reach the project store from where the page will be written.

        Falls back to the default output location, which is what the CLI uses
        when no `-o` is given. An unreachable relative path (different drive)
        degrades to an absolute one rather than to a broken link.
    """
    base = (
        Path(out_dir).resolve()
        if out_dir
        else default_output_path(root).parent
    )
    try:
        rel = os.path.relpath(root, base)
    except ValueError:
        rel = str(root)
    return rel.replace(os.sep, "/").rstrip("/") + "/"
