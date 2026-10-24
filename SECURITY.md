# Security Policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | Yes       |

## Reporting a vulnerability

Please do not open a public issue for security problems. Use GitHub's private
vulnerability reporting (repository **Security** tab → **Report a vulnerability**)
and include:

- affected version,
- a minimal reproduction,
- the impact you observed,
- any suggested fix.

We aim to acknowledge reports within 7 days. Please allow time for a fix and a
release before disclosing details publicly.

## Data handling

- `context-audit` runs locally and is read-only. It does not call any model API
  and does not upload conversation logs.
- Optional tokenizer backends may access the network on first use:
  `tiktoken` may download encoding files, and `transformers` may download
  tokenizer files from Hugging Face. Conversation content is not sent to those
  services by this tool.
- Hugging Face `trust_remote_code` is intentionally disabled. Only standard
  tokenizer loading is used.
- Treat chat logs as sensitive data. Token counts and reports may still reveal
  message volume and role distribution; redact logs before sharing reports.
- Token counts are measurements or estimates, not a security control. Do not use
  them as the only defense against context-window exhaustion or prompt injection.

## Scope

In scope: vulnerabilities in the package code, CLI, MCP server, and packaging.

Out of scope: issues in third-party tokenizers or MCP clients, model behavior,
and inaccurate token estimates when the fallback estimator is active.
