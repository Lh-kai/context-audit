"""Command-line interface for context-audit."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import __version__
from .core import DEFAULT_MODEL, audit, audit_dir, audit_file
from .file_io import parse_messages_text

_ROLE_LABELS = (
    ("system", "system_tokens"),
    ("user", "user_tokens"),
    ("assistant", "assistant_tokens"),
    ("tool", "tool_tokens"),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="context-audit",
        description="Measure how much of a model's context window a conversation uses.",
        epilog=(
            "examples:\n"
            "  context-audit analyze --file chat.jsonl --model qwen-max\n"
            "  context-audit analyze --dir logs/ --model gpt-4o\n"
            "  context-audit analyze --model gpt-4o < chat.json\n"
            "  context-audit analyze --file chat.jsonl --model gpt-4o --output json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser(
        "analyze",
        help="analyze a conversation log or standard input",
        description="Analyze one log file, a directory of logs, or JSON/JSONL from stdin.",
    )

    source = analyze.add_mutually_exclusive_group()
    source.add_argument(
        "--file",
        type=Path,
        metavar="PATH",
        help="path to a .json or .jsonl conversation log",
    )
    source.add_argument(
        "--dir",
        dest="directory",
        type=Path,
        metavar="DIR",
        help="analyze every .json / .jsonl log in DIR",
    )

    analyze.add_argument(
        "-m",
        "--model",
        default=DEFAULT_MODEL,
        help=f"model name (default: {DEFAULT_MODEL})",
    )
    analyze.add_argument(
        "--context-window",
        type=int,
        metavar="TOKENS",
        help="override the model's context window",
    )
    analyze.add_argument(
        "-o",
        "--output",
        choices=("table", "json"),
        default="table",
        help="output format (default: table)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return _run_analyze(args)
    except (OSError, ValueError, TypeError) as exc:
        print(f"context-audit: error: {exc}", file=sys.stderr)
        return 1


def _run_analyze(args: argparse.Namespace) -> int:
    if args.directory is not None:
        reports = audit_dir(
            args.directory,
            model=args.model,
            context_window=args.context_window,
        )
        if not reports:
            print(
                f"context-audit: no .json or .jsonl log files found in {args.directory}",
                file=sys.stderr,
            )
            return 1
        _emit(reports, args.output, is_directory=True)
        return 0

    if args.file is not None:
        report = audit_file(
            args.file,
            model=args.model,
            context_window=args.context_window,
        )
    else:
        messages = parse_messages_text(sys.stdin.read(), source="<stdin>")
        report = audit(
            messages,
            model=args.model,
            context_window=args.context_window,
        )

    _emit(report, args.output, is_directory=False)
    return 0


def _emit(payload: Any, output_format: str, *, is_directory: bool) -> None:
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif is_directory:
        _print_directory_table(payload)
    else:
        _print_report(payload)


def _print_report(report: dict[str, Any]) -> None:
    print("Context Audit Report")
    print("=" * 46)
    fields = (
        ("Model", report["model"]),
        ("Context window", f"{report['context_window']:,} tokens"),
        ("Used", f"{report['total_tokens']:,} tokens ({report['usage_percent']})"),
        ("Remaining", f"{report['remaining_tokens']:,} tokens"),
        ("Messages", f"{report['message_count']:,}"),
        (
            "Risk level",
            f"{report['level'].upper()} (warning: {'yes' if report['warning'] else 'no'})",
        ),
    )
    for label, value in fields:
        print(f"{label:<16}{value}")

    print()
    print("Tokens by role")
    print("-" * 46)
    for label, key in _ROLE_LABELS:
        print(f"  {label:<12}{report['breakdown'][key]:>10,}")
    print(f"  {'total':<12}{report['total_tokens']:>10,}")


def _print_directory_table(reports: list[dict[str, Any]]) -> None:
    headers = ("File", "Tokens", "Window", "Usage", "Remaining", "Level")
    rows = [
        (
            str(report["file"]),
            f"{report['total_tokens']:,}",
            f"{report['context_window']:,}",
            report["usage_percent"],
            f"{report['remaining_tokens']:,}",
            report["level"],
        )
        for report in reports
    ]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]

    print(_format_row(headers, widths))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print(_format_row(row, widths))


def _format_row(values: Sequence[str], widths: Sequence[int]) -> str:
    cells = [
        value.ljust(width) if index == 0 else value.rjust(width)
        for index, (value, width) in enumerate(zip(values, widths, strict=True))
    ]
    return "  ".join(cells)
