"""The shared retry loop: one retry with errors fed back, honest outcomes
(ok / retried_ok / partial / failed), and a complete call log."""

import json

import pytest
from pydantic import BaseModel, ConfigDict

from before_we_ai.llm.call_log import CallLogger
from before_we_ai.llm.client import AnthropicClient, Completion, call_with_retry
from before_we_ai.llm.config import LLMConfig, build_client
from before_we_ai.llm.inputs import BuiltInput
from before_we_ai.llm.stub import FixtureMissing, StubClient


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int


class FakeClient:
    name = "fake"

    def __init__(self, texts: list[str]):
        self.texts = list(texts)
        self.calls: list[list[dict[str, str]]] = []

    def complete(self, *, contract, scenario, model, system, messages):
        self.calls.append(messages)
        return Completion(text=self.texts[len(self.calls) - 1],
                          usage={"input_tokens": 10, "output_tokens": 5})


def _built(text="the input") -> BuiltInput:
    import hashlib

    return BuiltInput(text=text,
                      sha256=hashlib.sha256(text.encode()).hexdigest(),
                      trim_notices=["trimmed: example notice"])


def _call(tmp_path, client, semantic_check=None):
    return call_with_retry(
        client, contract="v1_hypotheses", scenario="test", model="test-model",
        system="answer with json", built=_built(), schema=Answer,
        semantic_check=semantic_check, logger=CallLogger(tmp_path),
    )


def _log(result) -> dict:
    return json.loads(open(result.log_ref, encoding="utf-8").read())


def test_invalid_then_valid_answer_retries_once(tmp_path):
    client = FakeClient(["not json at all", '{"value": 7}'])
    result = _call(tmp_path, client)
    assert result.parsed == Answer(value=7)
    assert result.retries == 1 and result.failure is None
    # the retry message feeds the errors back
    retry_messages = client.calls[1]
    assert len(retry_messages) == 3
    assert retry_messages[1] == {"role": "assistant", "content": "not json at all"}
    assert "failed validation" in retry_messages[2]["content"]
    assert "not valid JSON" in retry_messages[2]["content"]
    assert _log(result)["outcome"] == "retried_ok"


def test_second_failure_reports_and_never_raises(tmp_path):
    client = FakeClient(['{"value": "x"}', '{"wrong_field": 1}'])
    result = _call(tmp_path, client)
    assert result.parsed is None
    assert result.failure
    entry = _log(result)
    assert entry["outcome"] == "failed"
    assert len(entry["attempts"]) == 2
    assert entry["attempts"][0]["validation_errors"]


def test_markdown_fences_are_tolerated(tmp_path):
    client = FakeClient(['```json\n{"value": 3}\n```'])
    result = _call(tmp_path, client)
    assert result.parsed == Answer(value=3)
    assert result.retries == 0
    assert _log(result)["outcome"] == "ok"


def test_residual_semantic_errors_yield_partial_not_failed(tmp_path):
    client = FakeClient(['{"value": -1}', '{"value": -1}'])
    result = _call(tmp_path, client,
                   semantic_check=lambda a: ["value must be positive"] if a.value < 0 else [])
    assert result.parsed == Answer(value=-1)  # caller decides what to skip
    assert result.failure is None
    assert result.semantic_errors == ["value must be positive"]
    assert result.retries == 1
    assert "value must be positive" in client.calls[1][2]["content"]
    assert _log(result)["outcome"] == "partial"


def test_log_carries_the_verbatim_request_and_input_hash(tmp_path):
    result = _call(tmp_path, FakeClient(['{"value": 1}']))
    entry = _log(result)
    assert entry["contract"] == "v1_hypotheses"
    assert entry["model"] == "test-model"
    assert entry["provider"] == "fake"
    assert entry["schema"] == "Answer"
    assert entry["input_sha256"] == _built().sha256
    assert entry["request"] == {"system": "answer with json", "user": "the input"}
    assert entry["trim_notices"] == ["trimmed: example notice"]
    assert entry["attempts"][0]["usage"] == {"input_tokens": 10, "output_tokens": 5}
    assert result.usage == {"input_tokens": 10, "output_tokens": 5}


def test_anthropic_client_requires_the_env_var(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        AnthropicClient()


def test_config_defaults_and_offline_requires_fixtures(tmp_path):
    from before_we_ai.store import init_project

    root = init_project(tmp_path / "p")
    config = LLMConfig.from_project(root)
    assert config.provider == "anthropic"
    assert config.models["v1_hypotheses"] == "claude-opus-4-8"
    assert config.models["v2_bind"] == "claude-sonnet-5"
    assert config.offline is False

    with pytest.raises(FixtureMissing, match="no fixture source"):
        build_client(LLMConfig(offline=True))

    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    client = build_client(LLMConfig(offline=True, fixtures_dir=str(fixtures)))
    assert isinstance(client, StubClient)


def test_stub_client_replays_fixtures_and_fails_loudly(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "v1_hypotheses__test.json").write_text(json.dumps({
        "contract": "v1_hypotheses", "scenario": "test",
        "input_sha256": "abc", "recorded_at": "hand-authored",
        "response_text": '{"value": 42}',
    }), encoding="utf-8")
    stub = StubClient(fixtures)
    result = _call(tmp_path, stub)
    assert result.parsed == Answer(value=42)
    with pytest.raises(FixtureMissing, match="scenario 'missing'"):
        stub.complete(contract="v1_hypotheses", scenario="missing",
                      model="m", system="s", messages=[])
    with pytest.raises(FixtureMissing, match="not a directory"):
        StubClient(tmp_path / "nowhere")
