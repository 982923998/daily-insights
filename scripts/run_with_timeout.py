#!/usr/bin/env python3
"""Run a command with timeout and stream output."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Run command with timeout")
    parser.add_argument("--timeout", type=int, required=True, help="Timeout seconds (>0)")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command after --")
    args = parser.parse_args()

    timeout = args.timeout
    command = args.command
    if command and command[0] == "--":
        command = command[1:]

    if timeout <= 0:
        print("[run_with_timeout] timeout must be > 0", file=sys.stderr)
        return 2
    if not command:
        print("[run_with_timeout] command is required", file=sys.stderr)
        return 2

    proc = subprocess.Popen(command, start_new_session=True)
    try:
        return proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        print(
            f"[run_with_timeout] timed out after {timeout}s, terminating process group",
            file=sys.stderr,
        )
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
        return 124
    except KeyboardInterrupt:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
