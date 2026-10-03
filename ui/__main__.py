"""Start the demo web app: ``python -m ui`` from the repository root."""

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    uvicorn.run("ui.app:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
