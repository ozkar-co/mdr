#!/usr/bin/env python3
"""Punto de entrada de mdr."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from help_text import help_for_terminal
from session import run_session


def resolve_user_path(arg: str) -> Path:
    """Resolve a CLI path relative to where run.sh was invoked, not the project dir."""
    path = Path(arg)
    if not path.is_absolute():
        invocation_pwd = os.environ.get("MDR_INVOCATION_PWD")
        if invocation_pwd:
            path = Path(invocation_pwd) / path
    return path.resolve()


def main() -> None:
    args = sys.argv[1:]

    if args and args[0] in ("help", "-h", "--help"):
        print(help_for_terminal())
        sys.exit(0)

    if len(args) > 1:
        print("Error: argumentos de más", file=sys.stderr)
        sys.exit(1)

    try:
        if not args:
            run_session(root=Path.cwd())
            return

        path = resolve_user_path(args[0])
        if not path.exists():
            print(f"Error: no existe {path}", file=sys.stderr)
            sys.exit(1)
        if path.is_dir():
            run_session(root=path)
            return
        if not path.is_file():
            print(f"Error: {path} no es un archivo ni un directorio", file=sys.stderr)
            sys.exit(1)

        run_session(start=path)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
