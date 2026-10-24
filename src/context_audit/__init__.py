"""Audit how much of a model's context window a finished conversation uses.

The public API mirrors the three supported interfaces:

    from context_audit import audit, audit_file, audit_dir

All three call the same core implementation, so the SDK, the CLI, and the MCP
tool always report identical numbers.
"""

from __future__ import annotations

from .core import audit, audit_dir, audit_file
from .models import MODEL_REGISTRY, ModelConfig, UnknownModelError

__version__ = "0.1.0"

__all__ = [
    "MODEL_REGISTRY",
    "ModelConfig",
    "UnknownModelError",
    "__version__",
    "audit",
    "audit_dir",
    "audit_file",
]
