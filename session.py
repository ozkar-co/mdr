"""Sesión principal: navegador + lector."""

from __future__ import annotations

import curses
from pathlib import Path

from mdr.app import MdrApp
from mdr.browser import FileBrowser


def run_session(start: Path | None = None, root: Path | None = None) -> None:
    root = (root or Path.cwd()).resolve()
    from_browser = start is None

    while True:
        if start is not None:
            path = start.resolve()
            start = None
        else:
            path = curses.wrapper(lambda stdscr: FileBrowser(stdscr, root).run())
            if path is None:
                return

        action = curses.wrapper(
            lambda stdscr, p=path: MdrApp(
                stdscr,
                p,
                allow_browser_return=from_browser,
            ).run()
        )
        if action != "browser":
            return
