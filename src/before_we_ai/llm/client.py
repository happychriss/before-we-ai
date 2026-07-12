"""The client seam and the one-retry loop shared by all contracts.

``LLMClient`` is a two-method surface (a name and ``complete``); the real
Anthropic client and the fixture stub implement it identically, so every
line of validation, retry, and logging is exercised offline.

Retry semantics (the spec fixes the count — *ein Retry* — not its payload),
two-tier by the kind of failure:

* the answer never parsed (bad JSON, wrong shape) → nothing is worth
  keeping, so the **whole call** is retried with the errors fed back;
* the answer is schema-valid but some *items* of a batch fail the semantic
  checks → only those items are sent back for **repair**. Rewriting a whole
  batch to fix two of sixty-five items is expensive, and the corrective
  signal drowns: measured against a real V1 answer, the whole-batch retry
  re-emitted all 65 items byte-identically and fixed neither. A repair call
  also structurally cannot perturb the items that already validated.

Either way it stays one extra call. Whatever is still broken afterwards is
reported as ``partial``: the caller skips those items and keeps the rest —
a failed call never crashes a sweep.
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
class BatchRepair:
    """How to take a batch answer apart for an item-scoped repair.

    ``field`` names the list on the schema (``hypotheses``, ``bindings``,
    …); ``check_item`` returns the semantic errors of one item.
    """

    field: str
    check_item: Callable[[BaseModel], list[str]]


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


_REPAIR_TEMPLATE = (
    "{count} item(s) of your previous response failed validation. Everything "
    "else was accepted and is already stored — do not resend it.\n\n"
    "The rejected items, each with its errors:\n\n{items}\n\n"
    "Return a JSON object of the same schema containing ONLY corrected "
    "versions of these {count} item(s), in the same order. Respond with the "
    "JSON object only."
)


def _render_rejects(items: list[BaseModel], errors: list[list[str]]) -> str:
    return "\n\n".join(
        f"[{i}] {item.model_dump_json()}\n"
        + "\n".join(f"    error: {e}" for e in item_errors)
        for i, (item, item_errors) in enumerate(zip(items, errors), 1)
    )


def _item_errors(batch: BaseModel, repair: BatchRepair) -> list[list[str]]:
    return [repair.check_item(item) for item in getattr(batch, repair.field)]


def _repair_batch(
    client: LLMClient, *, contract: str, scenario: str, model: str, system: str,
    built: BuiltInput, schema: type[BaseModel], repair: BatchRepair,
    parsed: BaseModel, raw_text: str,
) -> tuple[BaseModel, dict, Completion]:
    """Send only the failing items back and splice accepted repairs into
    their original slots. Returns (merged batch, attempt log, completion)."""
    errors = _item_errors(parsed, repair)
    items = list(getattr(parsed, repair.field))
    bad = [i for i, item_errors in enumerate(errors) if item_errors]

    completion = client.complete(
        contract=contract, scenario=scenario, model=model, system=system,
        messages=[
            {"role": "user", "content": built.text},
            {"role": "assistant", "content": raw_text},
            {"role": "user", "content": _REPAIR_TEMPLATE.format(
                count=len(bad),
                items=_render_rejects([items[i] for i in bad],
                                      [errors[i] for i in bad]),
            )},
        ],
    )
    attempt = {
        "kind": "repair",
        "items_sent": len(bad),
        "raw_text": completion.text,
        "usage": completion.usage,
        "ms": completion.ms,
    }
    repaired, schema_errors = _validate(schema, completion.text)
    if repaired is None:
        attempt["validation_errors"] = [f"repair answer invalid: {e}"
                                        for e in schema_errors]
        return parsed, attempt, completion

    # The splice is positional, so the repair must answer exactly what was
    # asked. Anything else (a re-emitted full batch, a short list) is
    # discarded rather than guessed at: a mis-spliced item would silently
    # replace one claim with a different one.
    candidates = list(getattr(repaired, repair.field))
    if len(candidates) != len(bad):
        attempt["validation_errors"] = [
            f"repair returned {len(candidates)} item(s), expected {len(bad)} "
            "— discarded, originals kept"
        ]
        return parsed, attempt, completion

    accepted = 0
    for slot, candidate in zip(bad, candidates):
        if not repair.check_item(candidate):  # never splice a still-broken item
            items[slot] = candidate
            accepted += 1
    merged = parsed.model_copy(update={repair.field: items})
    attempt["items_accepted"] = accepted
    attempt["validation_errors"] = [
        e for item_errors in _item_errors(merged, repair) for e in item_errors
    ]
    return merged, attempt, completion


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
    repair: BatchRepair | None = None,
    logger: CallLogger,
) -> LLMResult:
    def check(batch: BaseModel) -> list[str]:
        if repair is not None:
            return [e for item_errors in _item_errors(batch, repair)
                    for e in item_errors]
        return semantic_check(batch) if semantic_check is not None else []

    messages = [{"role": "user", "content": built.text}]
    attempts: list[dict] = []
    usage_total: dict[str, int] = {}

    def account(completion: Completion) -> Completion:
        for key, value in completion.usage.items():
            usage_total[key] = usage_total.get(key, 0) + value
        return completion

    completion = account(client.complete(
        contract=contract, scenario=scenario, model=model,
        system=system, messages=messages,
    ))
    raw_text = completion.text
    parsed, schema_errors = _validate(schema, raw_text)
    semantic_errors = check(parsed) if parsed is not None else []
    attempts.append({
        "kind": "answer",
        "raw_text": raw_text,
        "validation_errors": schema_errors + semantic_errors,
        "usage": completion.usage,
        "ms": completion.ms,
    })

    if parsed is not None and semantic_errors and repair is not None:
        # Schema-valid batch: keep what validated, ask only for the rest.
        parsed, attempt, completion = _repair_batch(
            client, contract=contract, scenario=scenario, model=model,
            system=system, built=built, schema=schema, repair=repair,
            parsed=parsed, raw_text=raw_text,
        )
        account(completion)
        attempts.append(attempt)
        semantic_errors = check(parsed)
    elif schema_errors or semantic_errors:
        # Nothing worth keeping (or no batch structure to exploit): retry
        # the whole call with the errors fed back.
        messages = messages + [
            {"role": "assistant", "content": raw_text},
            {"role": "user", "content": _RETRY_TEMPLATE.format(
                errors="\n".join(f"- {e}" for e in schema_errors + semantic_errors))},
        ]
        completion = account(client.complete(
            contract=contract, scenario=scenario, model=model,
            system=system, messages=messages,
        ))
        raw_text = completion.text
        retried, retry_schema_errors = _validate(schema, raw_text)
        if retried is not None or parsed is None:
            parsed, schema_errors = retried, retry_schema_errors
            semantic_errors = check(parsed) if parsed is not None else []
        attempts.append({
            "kind": "retry",
            "raw_text": raw_text,
            "validation_errors": retry_schema_errors + semantic_errors,
            "usage": completion.usage,
            "ms": completion.ms,
        })

    # A schema-valid parse with residual semantic errors is returned as
    # "partial": the caller skips the offending items, never the batch.
    outcome = ("failed" if parsed is None
               else "partial" if semantic_errors
               else "ok" if len(attempts) == 1
               else "repaired_ok" if attempts[-1]["kind"] == "repair"
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
