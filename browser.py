"""Selector de archivos Markdown."""

from __future__ import annotations

import curses
from pathlib import Path

from mdr.files import find_markdown_files

PAIR_SELECTED = 1
PAIR_STATUS = 3


class FileBrowser:
    def __init__(self, stdscr: curses.window, root: Path):
        self.stdscr = stdscr
        self.root = root.resolve()
        self.files = find_markdown_files(self.root)
        self.labels = [str(p.relative_to(self.root)) for p in self.files]
        self.index = 0
        self.scroll = 0
        self.message = ""
        self._init_colors()

    def _init_colors(self) -> None:
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(PAIR_SELECTED, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(PAIR_STATUS, curses.COLOR_YELLOW, -1)

    def run(self) -> Path | None:
        curses.curs_set(0)
        self.stdscr.keypad(True)
        self.stdscr.timeout(-1)

        while True:
            height, width = self.stdscr.getmaxyx()
            self._draw(height, width)
            key = self.stdscr.getch()
            if not self._handle_key(key, height):
                return None
            if self.message == "__open__":
                return self.files[self.index]

    def _draw(self, height: int, width: int) -> None:
        self.stdscr.erase()
        view_height = height - 2

        title = f" Archivos Markdown en {self.root.name}/ "
        try:
            self.stdscr.attron(curses.A_BOLD)
            self.stdscr.addstr(0, 0, title[: max(width - 1, 0)])
            self.stdscr.attroff(curses.A_BOLD)
        except curses.error:
            pass

        if not self.files:
            msg = " No hay archivos .md en este directorio "
            try:
                self.stdscr.addstr(max(view_height // 2, 1), 0, msg[: max(width - 1, 0)])
            except curses.error:
                pass
        else:
            visible_end = min(self.scroll + view_height, len(self.labels))
            for row, item_idx in enumerate(range(self.scroll, visible_end)):
                y = row + 1
                label = self.labels[item_idx]
                line = f" {label}"
                try:
                    if item_idx == self.index:
                        self.stdscr.attron(curses.color_pair(PAIR_SELECTED) | curses.A_BOLD)
                        self.stdscr.addstr(y, 0, line.ljust(width - 1)[: width - 1])
                        self.stdscr.attroff(curses.color_pair(PAIR_SELECTED) | curses.A_BOLD)
                    else:
                        self.stdscr.addstr(y, 0, line[: width - 1])
                except curses.error:
                    pass

        status = f" {len(self.files)} archivo(s)  ↑↓ navegar  Enter abrir  q salir"
        if self.message and self.message != "__open__":
            status = f" {self.message} "
        try:
            self.stdscr.attron(curses.color_pair(PAIR_STATUS))
            self.stdscr.addstr(height - 1, 0, status.ljust(width - 1)[: width - 1])
            self.stdscr.attroff(curses.color_pair(PAIR_STATUS))
        except curses.error:
            pass

        self.stdscr.refresh()

    def _handle_key(self, key: int, height: int) -> bool:
        self.message = ""
        view_height = max(height - 2, 1)

        if key in (ord("q"), 27):
            return False

        if not self.files:
            return True

        max_scroll = max(0, len(self.files) - view_height)

        if key == curses.KEY_UP:
            self.index = max(0, self.index - 1)
            self._ensure_visible(view_height)
        elif key == curses.KEY_DOWN:
            self.index = min(len(self.files) - 1, self.index + 1)
            self._ensure_visible(view_height)
        elif key == curses.KEY_PPAGE:
            self.scroll = max(0, self.scroll - view_height)
            self.index = max(self.scroll, self.index - view_height)
            self.index = max(0, self.index)
        elif key == curses.KEY_NPAGE:
            self.scroll = min(max_scroll, self.scroll + view_height)
            self.index = min(len(self.files) - 1, self.index + view_height)
        elif key == curses.KEY_HOME:
            self.index = 0
            self.scroll = 0
        elif key == curses.KEY_END:
            self.index = len(self.files) - 1
            self.scroll = max_scroll
        elif key in (curses.KEY_ENTER, 10, 13):
            self.message = "__open__"
            return True

        return True

    def _ensure_visible(self, view_height: int) -> None:
        if self.index < self.scroll:
            self.scroll = self.index
        elif self.index >= self.scroll + view_height:
            self.scroll = self.index - view_height + 1


def run_browser(root: Path) -> Path | None:
    return curses.wrapper(lambda stdscr: FileBrowser(stdscr, root).run())
