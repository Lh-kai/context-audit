# context-audit

[简体中文](README.zh-CN.md) | English

**Measure how much of an LLM's context window a finished conversation actually consumes.**

`context-audit` takes a completed chat log, counts its tokens with the best tokenizer
available for the target model, and reports usage, remaining headroom, a per-role
breakdown, and a risk level. The same core function powers the Python SDK, the CLI,
and an MCP tool, so all three interfaces always agree.

- **Three interfaces, one implementation** — SDK, CLI, and MCP share `core.audit()`.
- **Zero runtime dependencies** — `pip install context-audit-tool` works offline with a
  CJK-aware estimator; install extras for exact token counts.
- **Real tokenizers when available** — `tiktoken` for OpenAI, Hugging Face
  `transformers` for Qwen / DeepSeek, with automatic fallback.
- **Log friendly** — read inline messages, `.json`, `.jsonl`, a whole directory, or stdin.
- **Actionable risk levels** — `low` / `medium` / `high` / `critical` plus a warning flag.
- **Read-only and local** — no API keys, no network calls, no data leaves your machine.

> Status: alpha. The report schema is stable; the model registry will keep growing.

## Installation

From PyPI (after release):

```bash
pip install context-audit-tool
```

> The PyPI distribution is named `context-audit-tool` because `context-audit` is
> already registered by another project. The import package remains
> `context_audit` and the CLI command remains `context-audit`.

From a source checkout:

```bash
git clone <repository-url>
cd context-audit
pip install -e .
```

Optional extras:

```bash
pip install "context-audit-tool[openai]"   # exact OpenAI counts via tiktoken
pip install "context-audit-tool[hf]"       # Qwen / DeepSeek tokenizers via transformers
pip install "context-audit-tool[mcp]"      # MCP server entry point
pip install "context-audit-tool[all]"      # everything above
pip install "context-audit-tool[dev]"      # pytest + ruff
pip install "context-audit-tool[release]"  # build + twine
```

Requires Python 3.10+.

## SDK

```python
from context_audit import audit

messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好，有什么可以帮你？"},
]

result = audit(messages=messages, model="qwen-max")
print(result["usage_percent"])  # e.g. "0.1%"
```

Analyze files and directories:

```python
from context_audit import audit_file, audit_dir

result = audit_file("chat.jsonl", model="qwen-max")
results = audit_dir("logs/", model="gpt-4o")

for report in results:
    print(report["file"], report["usage_percent"], report["level"])
```

Override the window for a supported model:

```python
audit(messages, model="gpt-4o", context_window=64_000)
```

Messages use the common OpenAI-style chat shape. `content` may be a string or a
structured list; `name` and `tool_calls` are counted when present. Supported roles
are `system`, `user`, `assistant`, and `tool` (`developer` is treated as `system`,
`function` as `tool`).

## CLI

```bash
context-audit analyze --file chat.jsonl --model qwen-max
context-audit analyze --dir logs/ --model gpt-4o
context-audit analyze --model gpt-4o < chat.json
context-audit analyze --file chat.jsonl --model gpt-4o --output json
context-audit analyze --file chat.jsonl --model gpt-4o --output table
```

The default output is a table:

```text
Context Audit Report
==============================================
Model           qwen-max
Context window  32,768 tokens
Used            12,456 tokens (38.0%)
Remaining       20,312 tokens
Messages        18
Risk level      LOW (warning: no)

Tokens by role
----------------------------------------------
  system           1,024
  user             5,200
  assistant        6,232
  tool                 0
  total           12,456
```

Directory mode prints one row per log file. `--output json` prints the report
(one object for a file/stdin, a list for a directory) with a `file` key added for
each directory entry.

Exit codes: `0` success, `1` runtime error (missing file, invalid JSON, unknown
model), `2` CLI usage error.

Try the bundled example:

```bash
context-audit analyze --file examples/sample_chat.jsonl --model qwen-max
```

## MCP server

The MCP entry point exposes a single tool, `measure_context_usage`.

```bash
pip install "context-audit-tool[mcp]"
context-audit-mcp
```

Example client configuration:

```json
{
  "mcpServers": {
    "context-audit": {
      "command": "context-audit-mcp"
    }
  }
}
```

Tool inputs:

| Parameter        | Type              | Required | Description                              |
| ---------------- | ----------------- | -------- | ---------------------------------------- |
| `messages`       | array of objects  | yes      | Conversation messages (`role`, `content`) |
| `model`          | string            | yes      | Model name from the registry             |
| `context_window` | integer           | no       | Override the model's context window      |

The tool returns exactly the same report dictionary as the SDK and CLI.

## Supported models

| Model               | Provider  | Context window | Token counting              |
| ------------------- | --------- | -------------: | --------------------------- |
| `gpt-4o`            | OpenAI    |        128,000 | `tiktoken` (`o200k_base`)   |
| `gpt-4o-mini`       | OpenAI    |        128,000 | `tiktoken` (`o200k_base`)   |
| `gpt-4-turbo`       | OpenAI    |        128,000 | `tiktoken` (`cl100k_base`)  |
| `gpt-4`             | OpenAI    |          8,192 | `tiktoken` (`cl100k_base`)  |
| `gpt-3.5-turbo`     | OpenAI    |         16,385 | `tiktoken` (`cl100k_base`)  |
| `claude-3-5-sonnet` | Anthropic |        200,000 | estimator                   |
| `claude-3-7-sonnet` | Anthropic |        200,000 | estimator                   |
| `claude-3-haiku`    | Anthropic |        200,000 | estimator                   |
| `claude-3-opus`     | Anthropic |        200,000 | estimator                   |
| `qwen-max`          | Qwen      |         32,768 | Hugging Face tokenizer      |
| `qwen-plus`         | Qwen      |        131,072 | Hugging Face tokenizer      |
| `qwen-turbo`        | Qwen      |          8,192 | Hugging Face tokenizer      |
| `qwen-long`         | Qwen      |     10,000,000 | Hugging Face tokenizer      |
| `deepseek-chat`     | DeepSeek  |        128,000 | Hugging Face tokenizer      |
| `deepseek-reasoner` | DeepSeek  |        128,000 | Hugging Face tokenizer      |

Versioned names such as `gpt-4o-2024-08-06` resolve to their base model and keep
the original name in the report. Window sizes are registry defaults; use
`context_window` to override. Add new models in
[`src/context_audit/models.py`](src/context_audit/models.py).

## How tokens are counted

1. **OpenAI** — `tiktoken` with the encoding configured per model.
2. **Qwen / DeepSeek** — the matching Hugging Face tokenizer via `transformers`
   (remote code execution is not enabled).
3. **Fallback** — a CJK-aware estimator: one token per CJK character plus roughly
   four characters per token for other text.

The fallback activates when an optional dependency is missing, the tokenizer
cannot be loaded (for example offline without a cache), or estimation is forced:

```bash
export CONTEXT_AUDIT_TOKENIZER=estimate
```

Counts cover message content, `name`, and serialized `tool_calls`. Chat-template
framing overhead is not included, so exact billed tokens can be slightly higher.
Use the optional tokenizer extras when precision matters.

## Report schema

```json
{
  "model": "qwen-max",
  "context_window": 32768,
  "total_tokens": 12456,
  "usage_ratio": 0.38,
  "usage_percent": "38.0%",
  "remaining_tokens": 20312,
  "breakdown": {
    "system_tokens": 1024,
    "user_tokens": 5200,
    "assistant_tokens": 6232,
    "tool_tokens": 0
  },
  "message_count": 18,
  "level": "low",
  "warning": false
}
```

Risk levels:

| Level      | Usage ratio        | `warning` |
| ---------- | ------------------ | --------- |
| `low`      | `< 60%`            | `false`   |
| `medium`   | `60%` – `< 80%`    | `false`   |
| `high`     | `80%` – `< 95%`    | `true`    |
| `critical` | `>= 95%`           | `true`    |

`remaining_tokens` never goes below zero, and reports may exceed 100% when the
conversation is already over the window.

## Development

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
ruff check .
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Release to PyPI

```bash
pip install ".[release]"
python -m build
python -m twine check dist/*
python -m twine upload dist/*
```

Bump the version in `pyproject.toml` and `src/context_audit/__init__.py` before
building.

## Security

The tool is read-only and local; see [SECURITY.md](SECURITY.md) for the security
policy and data-handling notes.

## License

[MIT](LICENSE) © context-audit contributors
