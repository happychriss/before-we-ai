import argparse
from pathlib import Path

from readiness_report.render import default_output_path, write_project_view


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render the readiness report of a before-we-ai project as one HTML page."
    )
    parser.add_argument("root", help="Path to the before-we-ai project directory")
    parser.add_argument(
        "-o",
        "--output",
        help="Output HTML path (defaults to a sibling file outside the project)",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    output = Path(args.output).resolve() if args.output else default_output_path(root)
    path = write_project_view(root, output)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
