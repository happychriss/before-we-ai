"""The ``llm:`` block of before-ai.yaml — provider, tiers, offline switch.

Model tiers follow the architecture: hypothesis generation (V1) and role
binding are frontier-class work, plain probe binding (V2) runs mid-tier.
All overridable per project. The API key is read from an environment
variable only — never from any file, never logged, never committed.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from before_we_ai.store.layout import CONFIG_FILE

# Owner decision 2026-07-12: Anthropic API; Opus 4.8 frontier, Sonnet 5 mid-tier.
DEFAULT_MODELS = {
    "v1_hypotheses": "claude-opus-4-8",
    "role_binding": "claude-opus-4-8",
    "v2_bind": "claude-sonnet-5",
}


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = "anthropic"
    offline: bool = False
    api_key_env: str = "ANTHROPIC_API_KEY"
    models: dict[str, str] = DEFAULT_MODELS
    roles_file: str | None = None
    fixtures_dir: str | None = None  # required when offline

    @classmethod
    def from_project(cls, root: str | Path) -> "LLMConfig":
        config = yaml.safe_load(
            (Path(root) / CONFIG_FILE).read_text(encoding="utf-8")
        ) or {}
        block = config.get("llm") or {}
        merged_models = {**DEFAULT_MODELS, **(block.get("models") or {})}
        return cls.model_validate({**block, "models": merged_models})


def build_client(config: LLMConfig):
    """The client the config asks for; offline strictly requires fixtures."""
    if config.offline:
        from before_we_ai.llm.stub import FixtureMissing, StubClient

        if not config.fixtures_dir:
            raise FixtureMissing(
                "offline mode has no fixture source: set llm.fixtures_dir "
                "in before-ai.yaml (stub answers must come from somewhere)"
            )
        return StubClient(config.fixtures_dir)
    if config.provider != "anthropic":
        raise ValueError(f"unknown LLM provider {config.provider!r}")
    from before_we_ai.llm.client import AnthropicClient

    return AnthropicClient(api_key_env=config.api_key_env)
