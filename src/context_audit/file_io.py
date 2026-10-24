"""Read conversation logs from JSON files, JSONL files, or directories."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LOG_SUFFIXES = frozenset({".json", ".jsonl"})


def load_messages(path: str | Path) -> list[dict[str, Any]]:
    """Load a message list from a ``.json`` or ``.jsonl`` file."""

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"log file not found: {file_path}")
    if not file_path.is_file():
        raise IsADirectoryError(f"expected a file, got a directory: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix not in LOG_SUFFIXES:
        raise ValueError(
            f"unsupported log file {file_path}; expected a .json or .jsonl file"
        )

    text = file_path.read_text(encoding="utf-8-sig")
    if suffix == ".jsonl":
        return _parse_jsonl(text, source=str(file_path))
    return _parse_json_document(text, source=str(file_path))


def parse_messages_text(text: str, *, source: str = "<input>") -> list[dict[str, Any]]:
    """Parse a JSON document or JSONL stream, e.g. content read from stdin."""

    stripped = text.strip()
    if not stripped:
        raise ValueError(f"{source}: no messages found")

    if stripped[0] in "[{":
        try:
            return _parse_json_document(stripped, source=source)
        except ValueError as document_error:
            # A JSONL stream is not a single document; retry line by line and
            # keep the document error if the input is not JSONL either.
            try:
                return _parse_jsonl(stripped, source=source)
            except ValueError:
                raise document_error from None
    return _parse_jsonl(stripped, source=source)


def iter_log_files(directory: str | Path) -> list[Path]:
    """Return supported log files in *directory*, sorted by file name."""

    dir_path = Path(directory)
    if not dir_path.exists():
        raise FileNotFoundError(f"directory not found: {dir_path}")
    if not dir_path.is_dir():
        raise NotADirectoryError(f"expected a directory, got a file: {dir_path}")

    return sorted(
        (
            path
            for path in dir_path.iterdir()
            if path.is_file() and path.suffix.lower() in LOG_SUFFIXES
        ),
        key=lambda path: path.name.lower(),
    )


def _parse_json_document(text: str, *, source: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{source}: invalid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})"
        ) from exc

    if isinstance(data, dict):
        nested = data.get("messages")
        if isinstance(nested, list):
            return _ensure_message_list(nested, source)
        if "role" in data:
            return [data]
        raise ValueError(
            f'{source}: JSON object must be a message or contain a "messages" list'
        )
    if isinstance(data, list):
        return _ensure_message_list(data, source)
    raise ValueError(f"{source}: JSON log must be a message list or object")


def _parse_jsonl(text: str, *, source: str) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue

        line_source = f"{source}:{line_number}"
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{line_source}: invalid JSON: {exc.msg}") from exc

        if isinstance(item, dict):
            nested = item.get("messages")
            if isinstance(nested, list):
                messages.extend(_ensure_message_list(nested, line_source))
            elif "role" in item:
                messages.append(item)
            else:
                raise ValueError(
                    f'{line_source}: JSON object must be a message or contain a "messages" list'
                )
        elif isinstance(item, list):
            messages.extend(_ensure_message_list(item, line_source))
        else:
            raise ValueError(
                f"{line_source}: expected a JSON object or array, got {type(item).__name__}"
            )

    return messages


def _ensure_message_list(items: list[Any], source: str) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(
                f"{source}: message at index {index} must be a JSON object, "
                f"got {type(item).__name__}"
            )
        messages.append(item)
    return messages
