from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from axia import __version__
from axia.boundary.adapters.sqlite_run_store import SQLiteRunStore
from axia.boundary.presentation.local_web import serve_local_web
from axia.operation import project_run_trace, replay_run
from axia.source import RequestRecord
from axia.shared.ids import RunId


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
    trace.add_argument("--run-store", default=".axia/runs.sqlite3")
    trace.add_argument("--format", choices=["json", "text"], default="json")

    replay = subcommands.add_parser("replay", help="Replay a run from stored artifacts.")
    replay.add_argument("run_id")
    replay.add_argument("--run-store", default=".axia/runs.sqlite3")

    profiles = subcommands.add_parser("profiles", help="Inspect model profiles.")
    profile_commands = profiles.add_subparsers(dest="profile_command")
    profile_commands.add_parser("list", help="List configured profiles.")

    benchmark = subcommands.add_parser("benchmark", help="Run reasoning-improvement benchmarks.")
    benchmark_commands = benchmark.add_subparsers(dest="benchmark_command")
    benchmark_run = benchmark_commands.add_parser("run", help="Run a benchmark suite.")
    benchmark_run.add_argument("--suite", default="baseline")

    web = subcommands.add_parser("web", help="Serve the local read-only run browser.")
    web.add_argument("--run-store", default=".axia/runs.sqlite3")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)

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
    if args.command == "web":
        return _serve_web(args.run_store, args.host, args.port)
    if args.command == "replay":
        return _replay_run(args.run_id, args.run_store)
    if args.command == "trace":
        return _trace_run(args.run_id, args.run_store, args.format)

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


def _replay_run(run_id_value: str, run_store_path: str) -> int:
    store = SQLiteRunStore(Path(run_store_path))
    try:
        replay = replay_run(RunId.from_value(run_id_value), store)
    finally:
        store.close()
    print(json.dumps(replay.to_payload(), sort_keys=True))
    return 0


def _trace_run(run_id_value: str, run_store_path: str, output_format: str) -> int:
    store = SQLiteRunStore(Path(run_store_path))
    try:
        trace = project_run_trace(RunId.from_value(run_id_value), store)
    finally:
        store.close()
    if output_format == "text":
        print(trace.render_text())
    else:
        print(json.dumps(trace.to_payload(), sort_keys=True))
    return 0


def _serve_web(run_store_path: str, host: str, port: int) -> int:
    store = SQLiteRunStore(Path(run_store_path))
    try:
        serve_local_web(store, host, port)
    except KeyboardInterrupt:
        return 0
    finally:
        store.close()
    return 0
