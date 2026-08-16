#!/usr/bin/env python3
"""Punto de entrada de mdr."""

from __future__ import annotations

import sys
from pathlib import Path

from help_text import help_for_terminal
from session import run_session


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

        path = Path(args[0])
        if not path.exists():
            print(f"Error: no existe {path}", file=sys.stderr)
            sys.exit(1)
        if not path.is_file():
            print(f"Error: {path} no es un archivo", file=sys.stderr)
            sys.exit(1)

        run_session(start=path.resolve())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
