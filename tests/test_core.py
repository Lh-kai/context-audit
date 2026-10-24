from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from context_audit import audit, audit_dir, audit_file, tokenizers
from context_audit.cli import main as cli_main
from context_audit.mcp import measure_context_usage

MESSAGES = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好，有什么可以帮你？"},  # noqa: RUF001
]


@pytest.fixture(autouse=True)
def force_estimate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTEXT_AUDIT_TOKENIZER", "estimate")


def _write_jsonl(path: Path, messages: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(message, ensure_ascii=False) for message in messages) + "\n",
        encoding="utf-8",
    )


def test_report_shape_and_totals() -> None:
    report = audit(MESSAGES, model="qwen-max")

    assert report["model"] == "qwen-max"
    assert report["context_window"] == 32_768
    assert report["message_count"] == 3
    assert report["total_tokens"] == sum(report["breakdown"].values())
    assert report["total_tokens"] > 0
    assert report["remaining_tokens"] == 32_768 - report["total_tokens"]
    assert report["usage_percent"] == f"{report['usage_ratio'] * 100:.1f}%"
    assert report["level"] == "low"
    assert report["warning"] is False
    assert set(report["breakdown"]) == {
        "system_tokens",
        "user_tokens",
        "assistant_tokens",
        "tool_tokens",
    }


@pytest.mark.parametrize(
    ("used", "window", "level", "warning"),
    [
        (59, 100, "low", False),
        (60, 100, "medium", False),
        (79, 100, "medium", False),
        (80, 100, "high", True),
        (94, 100, "high", True),
        (95, 100, "critical", True),
        (130, 100, "critical", True),
    ],
)
def test_risk_level_boundaries(
    monkeypatch: pytest.MonkeyPatch,
    used: int,
    window: int,
    level: str,
    warning: bool,
) -> None:
    monkeypatch.setattr(tokenizers, "count_tokens", lambda text, model: 1)
    messages = [{"role": "user", "content": "x"} for _ in range(used)]

    report = audit(messages, model="gpt-4o", context_window=window)

    assert report["total_tokens"] == used
    assert report["usage_ratio"] == round(used / window, 4)
    assert report["remaining_tokens"] == max(window - used, 0)
    assert report["level"] == level
    assert report["warning"] is warning


def test_context_window_override_and_versioned_alias() -> None:
    override = audit(MESSAGES, model="qwen-max", context_window=1_000)
    assert override["context_window"] == 1_000

    versioned = audit(MESSAGES, model="gpt-4o-2024-08-06")
    assert versioned["model"] == "gpt-4o-2024-08-06"
    assert versioned["context_window"] == 128_000


def test_invalid_inputs_raise_clear_errors() -> None:
    with pytest.raises(ValueError, match="unsupported model"):
        audit(MESSAGES, model="not-a-real-model")

    with pytest.raises(ValueError, match="greater than 0"):
        audit(MESSAGES, model="gpt-4o", context_window=0)

    with pytest.raises(ValueError, match="unsupported role"):
        audit([{"role": "wizard", "content": "hello"}])

    with pytest.raises(TypeError, match="mapping"):
        audit([{"role": "user", "content": "hi"}, "not-a-message"])


def test_tool_calls_and_tool_messages_are_counted() -> None:
    messages = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "search", "arguments": '{"q":"x"}'},
                }
            ],
        },
        {"role": "tool", "name": "search", "content": "result"},
    ]

    report = audit(messages, model="gpt-4o")

    assert report["breakdown"]["assistant_tokens"] > 0
    assert report["breakdown"]["tool_tokens"] > 0
    assert report["total_tokens"] == (
        report["breakdown"]["assistant_tokens"] + report["breakdown"]["tool_tokens"]
    )


def test_estimator_handles_mixed_language() -> None:
    assert tokenizers.estimate_tokens("") == 0
    assert tokenizers.estimate_tokens("你好") == 2
    assert tokenizers.estimate_tokens("abcd") == 1
    assert tokenizers.estimate_tokens("你好abcd") == 3


def test_audit_file_and_directory(tmp_path: Path) -> None:
    jsonl_path = tmp_path / "chat.jsonl"
    _write_jsonl(jsonl_path, MESSAGES)

    json_path = tmp_path / "chat.json"
    json_path.write_text(
        json.dumps({"messages": MESSAGES}, ensure_ascii=False),
        encoding="utf-8",
    )

    assert audit_file(jsonl_path, model="qwen-max")["message_count"] == 3
    assert audit_file(json_path, model="qwen-max")["message_count"] == 3

    reports = audit_dir(tmp_path, model="qwen-max")
    assert {Path(report["file"]).name for report in reports} == {
        "chat.json",
        "chat.jsonl",
    }
    assert all(report["model"] == "qwen-max" for report in reports)


def test_invalid_jsonl_reports_line_number(tmp_path: Path) -> None:
    bad_path = tmp_path / "bad.jsonl"
    bad_path.write_text('{"role": "user", "content": "ok"}\nnot json\n', encoding="utf-8")

    with pytest.raises(ValueError, match=r"bad\.jsonl:2: invalid JSON"):
        audit_file(bad_path)


def test_cli_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "chat.jsonl"
    _write_jsonl(path, MESSAGES)

    exit_code = cli_main(
        ["analyze", "--file", str(path), "--model", "gpt-4o", "--output", "json"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["model"] == "gpt-4o"
    assert payload["message_count"] == 3


def test_cli_table_and_directory_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_jsonl(tmp_path / "chat.jsonl", MESSAGES)
    (tmp_path / "chat.json").write_text(json.dumps(MESSAGES), encoding="utf-8")

    assert cli_main(["analyze", "--file", str(tmp_path / "chat.jsonl")]) == 0
    table = capsys.readouterr().out
    assert "Context Audit Report" in table
    assert "Tokens by role" in table

    assert cli_main(["analyze", "--dir", str(tmp_path), "--model", "gpt-4o"]) == 0
    directory_table = capsys.readouterr().out
    assert "chat.json" in directory_table
    assert "chat.jsonl" in directory_table
    assert "Level" in directory_table


def test_cli_reads_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(MESSAGES)))

    exit_code = cli_main(["analyze", "--model", "qwen-max", "--output", "json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["message_count"] == 3


def test_cli_reads_jsonl_from_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    jsonl = "\n".join(json.dumps(message, ensure_ascii=False) for message in MESSAGES)
    monkeypatch.setattr(sys, "stdin", io.StringIO(jsonl))

    exit_code = cli_main(["analyze", "--model", "gpt-4o", "--output", "json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["message_count"] == 3


def test_cli_missing_file_returns_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = cli_main(["analyze", "--file", str(tmp_path / "missing.jsonl")])

    assert exit_code == 1
    assert "error" in capsys.readouterr().err


def test_mcp_tool_delegates_to_core() -> None:
    report = measure_context_usage(messages=MESSAGES, model="qwen-max")

    assert report["model"] == "qwen-max"
    assert report["context_window"] == 32_768
    assert report["message_count"] == 3


def test_mcp_server_constructs_when_dependency_available() -> None:
    pytest.importorskip("mcp")

    from context_audit import mcp as mcp_module

    server = mcp_module._create_server()

    assert server is not None
