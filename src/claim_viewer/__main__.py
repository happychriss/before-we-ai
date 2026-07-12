import argparse
from pathlib import Path

from claim_viewer.viewer import default_output_path, write_project_view


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a read-only HTML viewer for a before-we-ai project."
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
