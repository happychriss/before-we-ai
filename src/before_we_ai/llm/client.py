"""The client seam and the one-retry loop shared by all contracts.

``LLMClient`` is a two-method surface (a name and ``complete``); the real
Anthropic client and the fixture stub implement it identically, so every
line of validation, retry, and logging is exercised offline.

Retry semantics (fixed by the spec): parse + validate + semantic-check
the answer; on any error, exactly one retry with the errors fed back
verbatim; a second failure is logged and reported — the caller skips and
continues, a failed call never crashes a sweep.
"""

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Protocol

from pydantic import BaseModel, ValidationError

from before_we_ai.llm.call_log import CallLogger
from before_we_ai.llm.inputs import BuiltInput

MAX_OUTPUT_TOKENS = 16_000

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$")


@dataclass
class Completion:
    text: str
    usage: dict[str, int] = field(default_factory=dict)
    ms: int = 0


class LLMClient(Protocol):
    name: str

    def complete(self, *, contract: str, scenario: str, model: str,
                 system: str, messages: list[dict[str, str]]) -> Completion: ...


class AnthropicClient:
    """Direct Anthropic SDK, imported lazily — the package must work
    (and CI must pass) without the ``llm`` extra installed."""

    name = "anthropic"

    def __init__(self, api_key_env: str = "ANTHROPIC_API_KEY"):
        key = os.environ.get(api_key_env)
        if not key:
            raise RuntimeError(
                f"no API key: set the {api_key_env} environment variable "
                "(the key is never read from any file)"
            )
        import anthropic

        self._client = anthropic.Anthropic(api_key=key)

    def complete(self, *, contract: str, scenario: str, model: str,
                 system: str, messages: list[dict[str, str]]) -> Completion:
        start = time.monotonic()
        response = self._client.messages.create(
            model=model,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=system,
            messages=messages,
        )
        text = "".join(
            block.text for block in response.content
            if getattr(block, "type", None) == "text"
        )
        return Completion(
            text=text,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            ms=int((time.monotonic() - start) * 1000),
        )


@dataclass
class LLMResult:
    parsed: BaseModel | None  # None only when the schema never validated
    raw_text: str
    retries: int
    failure: str | None  # set only when parsed is None
    semantic_errors: list[str]  # errors surviving the retry — caller skips those items
    usage: dict[str, int]
    log_ref: str


def _validate(schema: type[BaseModel], text: str) -> tuple[BaseModel | None, list[str]]:
    stripped = _FENCE.sub("", text.strip())
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        return None, [f"response is not valid JSON: {exc}"]
    try:
        return schema.model_validate(data), []
    except ValidationError as exc:
        return None, [
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
            for e in exc.errors()
        ]


_RETRY_TEMPLATE = (
    "Your previous response failed validation:\n{errors}\n\n"
    "Return a corrected response that conforms to the schema and fixes "
    "every listed error. Respond with the JSON object only."
)


def call_with_retry(
    client: LLMClient,
    *,
    contract: str,
    scenario: str,
    model: str,
    system: str,
    built: BuiltInput,
    schema: type[BaseModel],
    semantic_check: Callable[[BaseModel], list[str]] | None = None,
    logger: CallLogger,
) -> LLMResult:
    messages = [{"role": "user", "content": built.text}]
    attempts: list[dict] = []
    parsed: BaseModel | None = None
    raw_text = ""
    usage_total: dict[str, int] = {}
    schema_errors: list[str] = []
    semantic_errors: list[str] = []

    for attempt in range(2):
        completion = client.complete(
            contract=contract, scenario=scenario, model=model,
            system=system, messages=messages,
        )
        raw_text = completion.text
        for key, value in completion.usage.items():
            usage_total[key] = usage_total.get(key, 0) + value
        parsed, schema_errors = _validate(schema, completion.text)
        semantic_errors = (
            semantic_check(parsed)
            if parsed is not None and semantic_check is not None else []
        )
        errors = schema_errors + semantic_errors
        attempts.append({
            "raw_text": completion.text,
            "validation_errors": errors,
            "usage": completion.usage,
            "ms": completion.ms,
        })
        if not errors:
            break
        if attempt == 0:
            messages = messages + [
                {"role": "assistant", "content": completion.text},
                {"role": "user",
                 "content": _RETRY_TEMPLATE.format(errors="\n".join(f"- {e}" for e in errors))},
            ]

    # A schema-valid parse with residual semantic errors is returned as
    # "partial": the caller skips the offending items, never the batch.
    outcome = ("failed" if parsed is None
               else "partial" if semantic_errors
               else "ok" if len(attempts) == 1
               else "retried_ok")
    failure = "; ".join(schema_errors) if parsed is None else None
    log_path = logger.write({
        "contract": contract,
        "scenario": scenario,
        "model": model,
        "provider": client.name,
        "schema": schema.__name__,
        "input_sha256": built.sha256,
        "trim_notices": built.trim_notices,
        "request": {"system": system, "user": built.text},
        "attempts": attempts,
        "outcome": outcome,
        "failure": failure,
    })
    return LLMResult(
        parsed=parsed,
        raw_text=raw_text,
        retries=len(attempts) - 1,
        failure=failure,
        semantic_errors=semantic_errors,
        usage=usage_total,
        log_ref=str(log_path),
    )
