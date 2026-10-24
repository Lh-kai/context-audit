"""Token counting with graceful, offline-friendly fallbacks.

Backend selection per model:

* ``tiktoken`` -- OpenAI models when the ``openai`` extra is installed.
* ``hf``       -- Qwen / DeepSeek models when the ``hf`` extra is installed.
* ``estimate`` -- CJK-aware character heuristic, always available.

Set ``CONTEXT_AUDIT_TOKENIZER=estimate`` to force the heuristic, for example in
offline CI or when tokenizer downloads are undesirable.
"""

from __future__ import annotations

import logging
import math
import os
import re
from functools import cache
from typing import Any

from .models import ModelConfig

logger = logging.getLogger(__name__)

_CJK_RE = re.compile(
    r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af]"
)
_FORCE_ESTIMATE_ENV = "CONTEXT_AUDIT_TOKENIZER"


def estimate_tokens(text: str) -> int:
    """Estimate tokens without a tokenizer.

    CJK characters count as one token each; other text counts roughly four
    characters per token. This is deliberately conservative for mixed-language
    chat logs.
    """

    if not text:
        return 0
    cjk_count = len(_CJK_RE.findall(text))
    other = _CJK_RE.sub("", text)
    return cjk_count + math.ceil(len(other) / 4)


def count_tokens(text: str, model: ModelConfig) -> int:
    """Count tokens in *text* using the best backend available for *model*."""

    if not text:
        return 0

    backend = _selected_backend(model)
    if backend == "tiktoken":
        count = _count_with_tiktoken(text, model)
        if count is not None:
            return count
    elif backend == "hf":
        count = _count_with_hf(text, model)
        if count is not None:
            return count

    return estimate_tokens(text)


def _selected_backend(model: ModelConfig) -> str:
    forced = os.environ.get(_FORCE_ESTIMATE_ENV, "").strip().lower()
    if forced in {"estimate", "char", "fallback"}:
        return "estimate"
    return model.tokenizer


def _count_with_tiktoken(text: str, model: ModelConfig) -> int | None:
    if not model.tiktoken_encoding:
        return None
    encoding = _get_tiktoken_encoding(model.tiktoken_encoding)
    if encoding is None:
        return None
    try:
        return len(encoding.encode(text, disallowed_special=()))
    except Exception as exc:  # third-party boundary
        logger.debug("tiktoken failed for %s: %s", model.name, exc)
        return None


def _count_with_hf(text: str, model: ModelConfig) -> int | None:
    if not model.hf_repo:
        return None
    tokenizer = _get_hf_tokenizer(model.hf_repo)
    if tokenizer is None:
        return None
    try:
        return len(tokenizer.encode(text, add_special_tokens=False))
    except Exception as exc:  # third-party boundary
        logger.debug("Hugging Face tokenizer failed for %s: %s", model.name, exc)
        return None


@cache
def _get_tiktoken_encoding(encoding_name: str) -> Any | None:
    try:
        import tiktoken
    except ImportError:
        logger.debug("tiktoken is not installed; using the estimator")
        return None
    try:
        return tiktoken.get_encoding(encoding_name)
    except Exception as exc:  # network or cache failure
        logger.debug("could not load tiktoken encoding %s: %s", encoding_name, exc)
        return None


@cache
def _get_hf_tokenizer(repo: str) -> Any | None:
    try:
        from transformers import AutoTokenizer
    except ImportError:
        logger.debug("transformers is not installed; using the estimator")
        return None
    try:
        # trust_remote_code stays disabled: conversation logs are local, but
        # tokenizer repositories should never execute code on the user's machine.
        return AutoTokenizer.from_pretrained(repo)
    except Exception as exc:  # missing cache, offline mode, unsupported repo
        logger.debug("could not load tokenizer %s: %s", repo, exc)
        return None
