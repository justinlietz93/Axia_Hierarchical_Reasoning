from __future__ import annotations

import argparse
import json
from typing import Sequence

from axia import __version__
from axia.source import RequestRecord


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="axia")
    parser.add_argument("--version", action="store_true", help="Print Axia version and exit.")

    subcommands = parser.add_subparsers(dest="command")

    ask = subcommands.add_parser("ask", help="Start a reasoning run from a question.")
    ask.add_argument("request", nargs="+")

    run = subcommands.add_parser("run", help="Start a reasoning run from a task request.")
    run.add_argument("request", nargs="*")
    run.add_argument("--mode", choices=["quick", "standard", "deep"], default="standard")
    run.add_argument("--model", default="tiny-default")

    trace = subcommands.add_parser("trace", help="Show a run trace.")
    trace.add_argument("run_id")

    replay = subcommands.add_parser("replay", help="Replay a run from stored artifacts.")
    replay.add_argument("run_id")

    profiles = subcommands.add_parser("profiles", help="Inspect model profiles.")
    profile_commands = profiles.add_subparsers(dest="profile_command")
    profile_commands.add_parser("list", help="List configured profiles.")

    benchmark = subcommands.add_parser("benchmark", help="Run reasoning-improvement benchmarks.")
    benchmark_commands = benchmark.add_subparsers(dest="benchmark_command")
    benchmark_run = benchmark_commands.add_parser("run", help="Run a benchmark suite.")
    benchmark_run.add_argument("--suite", default="baseline")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    if args.command == "ask":
        return _print_request_stub("ask", " ".join(args.request))
    if args.command == "run":
        return _print_request_stub("run", " ".join(args.request), mode=args.mode, model=args.model)
    if args.command == "profiles" and args.profile_command == "list":
        print("[]")
        return 0
    if args.command == "benchmark" and args.benchmark_command == "run":
        print(json.dumps({"status": "not_implemented", "suite": args.suite}, sort_keys=True))
        return 0
    if args.command in {"trace", "replay"}:
        print(json.dumps({"status": "not_implemented", "run_id": args.run_id}, sort_keys=True))
        return 0

    parser.print_help()
    return 0


def _print_request_stub(kind: str, request_text: str, **extra: str) -> int:
    record = RequestRecord.from_text(request_text)
    payload = {
        "status": "not_implemented",
        "command": kind,
        "request_hash": record.content_hash,
        **extra,
    }
    print(json.dumps(payload, sort_keys=True))
    return 0

