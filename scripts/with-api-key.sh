#!/usr/bin/env sh
# Export the Anthropic API key for exactly one command, and no further.
#
# WHY THIS EXISTS. The key used to sit in ~/.zshenv, which every zsh loads
# — including the one Claude Code starts in. Claude Code takes
# ANTHROPIC_API_KEY from the environment and bills the assistant session
# to it, so the key the owner created for the product's recordings paid
# for the chat about the product as well, at many times the cost. A key
# exported globally is not "the key for our LLM calls"; it is the key for
# everything running in that shell.
#
# So: the key lives in a file, and only the command that needs it sees it.
#
#     scripts/with-api-key.sh pytest -m live
#     scripts/with-api-key.sh python -m before_we_ai.llm.record ...
#
# Never `export` it in a shell you then keep working in — that recreates
# the same hole for as long as the shell lives.
set -eu

KEY_FILE="${ANTHROPIC_API_KEY_FILE:-$HOME/.config/before-we-ai/api-key}"

if [ "$#" -eq 0 ]; then
    echo "usage: $0 <command> [args...]" >&2
    exit 2
fi

if [ ! -r "$KEY_FILE" ]; then
    echo "$0: no readable key file at $KEY_FILE" >&2
    echo "  put the key there (chmod 600), or set ANTHROPIC_API_KEY_FILE" >&2
    exit 1
fi

ANTHROPIC_API_KEY="$(cat "$KEY_FILE")"
export ANTHROPIC_API_KEY
exec "$@"
