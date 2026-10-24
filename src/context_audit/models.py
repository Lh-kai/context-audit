"""Central model registry: context windows and default tokenizer backends."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """Static configuration for one supported model."""

    name: str
    provider: str
    context_window: int
    tokenizer: str
    supports_tools: bool = True
    tiktoken_encoding: str | None = None
    hf_repo: str | None = None


class UnknownModelError(ValueError):
    """Raised when a model is missing from the registry."""


_MODELS: tuple[ModelConfig, ...] = (
    # OpenAI: exact counts through tiktoken when the optional extra is installed.
    ModelConfig(
        "gpt-4o", "openai", 128_000, "tiktoken", True, tiktoken_encoding="o200k_base"
    ),
    ModelConfig(
        "gpt-4o-mini", "openai", 128_000, "tiktoken", True, tiktoken_encoding="o200k_base"
    ),
    ModelConfig(
        "gpt-4-turbo", "openai", 128_000, "tiktoken", True, tiktoken_encoding="cl100k_base"
    ),
    ModelConfig("gpt-4", "openai", 8_192, "tiktoken", True, tiktoken_encoding="cl100k_base"),
    ModelConfig(
        "gpt-3.5-turbo", "openai", 16_385, "tiktoken", True, tiktoken_encoding="cl100k_base"
    ),
    # Anthropic does not publish an offline tokenizer, so counts use the estimator.
    ModelConfig("claude-3-5-sonnet", "anthropic", 200_000, "estimate"),
    ModelConfig("claude-3-7-sonnet", "anthropic", 200_000, "estimate"),
    ModelConfig("claude-3-haiku", "anthropic", 200_000, "estimate"),
    ModelConfig("claude-3-opus", "anthropic", 200_000, "estimate"),
    # Qwen: counts through the matching Hugging Face tokenizer.
    ModelConfig(
        "qwen-max", "qwen", 32_768, "hf", hf_repo="Qwen/Qwen2.5-7B-Instruct"
    ),
    ModelConfig(
        "qwen-plus", "qwen", 131_072, "hf", hf_repo="Qwen/Qwen2.5-7B-Instruct"
    ),
    ModelConfig(
        "qwen-turbo", "qwen", 8_192, "hf", hf_repo="Qwen/Qwen2.5-7B-Instruct"
    ),
    ModelConfig(
        "qwen-long", "qwen", 10_000_000, "hf", hf_repo="Qwen/Qwen2.5-7B-Instruct"
    ),
    # DeepSeek: counts through the matching Hugging Face tokenizer.
    ModelConfig(
        "deepseek-chat", "deepseek", 128_000, "hf", hf_repo="deepseek-ai/DeepSeek-V3"
    ),
    ModelConfig(
        "deepseek-reasoner", "deepseek", 128_000, "hf", hf_repo="deepseek-ai/DeepSeek-V3"
    ),
)

MODEL_REGISTRY: dict[str, ModelConfig] = {model.name: model for model in _MODELS}


def get_model_config(name: str) -> ModelConfig:
    """Resolve *name* to a registry entry.

    Versioned names such as ``gpt-4o-2024-08-06`` or
    ``claude-3-5-sonnet-20241022`` resolve to their base model while keeping the
    original name in the report.
    """

    if not isinstance(name, str) or not name.strip():
        raise UnknownModelError("model name must be a non-empty string")

    key = name.strip().lower()
    config = MODEL_REGISTRY.get(key)
    if config is not None:
        return config

    for registered in sorted(MODEL_REGISTRY, key=len, reverse=True):
        if key.startswith(f"{registered}-"):
            return replace(MODEL_REGISTRY[registered], name=name.strip())

    supported = ", ".join(sorted(MODEL_REGISTRY))
    raise UnknownModelError(
        f"unsupported model {name!r}. Supported models: {supported}. "
        "Use --context-window only to override the window of a supported model."
    )
