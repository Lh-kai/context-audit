# Contributing

Thanks for helping improve `context-audit`.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
ruff check .
```

Optional dependencies are not required for the test suite: tests force the
estimator via `CONTEXT_AUDIT_TOKENIZER=estimate`, so they run offline and produce
deterministic counts.

## Guidelines

- Keep the SDK, CLI, and MCP layers thin. Calculation logic belongs in
  `core.py`; tokenizer selection belongs in `tokenizers.py`.
- Add models to `models.py` with provider, context window, tokenizer backend, and
  tool support. Include the model in both README tables.
- Preserve the public report schema. Additive fields need a clear use case and
  tests.
- Add a test for every behavior change, including edge cases such as risk-level
  boundaries, malformed logs, and window overrides.
- Prefer graceful fallback over hard failures when an optional tokenizer is
  unavailable. Errors in user input should stay clear and actionable.
- Keep output stable for scripts: JSON keys, exit codes, and level names are part
  of the interface.

## Pull requests

1. Fork the repository and create a branch.
2. Make the change with tests and documentation.
3. Run `pytest` and `ruff check .`.
4. Describe the motivation and any behavior changes in the pull request.

By contributing, you agree that your contributions are licensed under the MIT
License.
