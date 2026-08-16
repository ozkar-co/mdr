"""Aplicación TUI con curses."""

from __future__ import annotations

import curses
import re
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path

from mdr.help_text import HELP_LINES
from mdr.links import Link, extract_links, resolve_href
from mdr.render import RenderResult, render_markdown
from mdr.search import find_matches

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
ANSI_SGR = re.compile(r"\x1b\[([0-9;]*)m")

PAIR_LINK = 1
PAIR_STATUS = 3
PAIR_SEARCH = 5
PAIR_SEARCH_CURRENT = 6


@dataclass
class PageState:
    path: Path
    content: str
    scroll: int = 0
    link_index: int = 0
    anchor: str | None = None
    render: RenderResult | None = None
    source_links: list[Link] = field(default_factory=list)


@dataclass(frozen=True)
class Highlight:
    start: int
    end: int
    pair: int
    bold: bool = False


class MdrApp:
    def __init__(self, stdscr, initial_path: Path, allow_browser_return: bool = False):
        self.stdscr = stdscr
        self.allow_browser_return = allow_browser_return
        self.exit_action = "quit"
        self.history: list[PageState] = []
        self.current = self._load_page(initial_path)
        self.message = ""
        self.show_help = False
        self.search_input = ""
        self.search_query = ""
        self.search_hits: list[tuple[int, int, int]] = []
        self.search_index = 0
        self.mode = "normal"  # normal | search_input | search
        self._init_colors()

    def _init_colors(self) -> None:
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(PAIR_LINK, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(PAIR_STATUS, curses.COLOR_YELLOW, -1)
        curses.init_pair(PAIR_SEARCH, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        curses.init_pair(PAIR_SEARCH_CURRENT, curses.COLOR_WHITE, curses.COLOR_RED)

    def _load_page(self, path: Path, anchor: str | None = None) -> PageState:
        content = path.read_text(encoding="utf-8", errors="replace")
        state = PageState(path=path, content=content, anchor=anchor)
        state.source_links = extract_links(content)
        return state

    def _ensure_render(self, width: int) -> None:
        if self.current.render is None or self.current.render.width != width:
            self.current.render = render_markdown(
                self.current.content,
                self.current.source_links,
                width,
            )
            if self.current.anchor:
                self._scroll_to_anchor(self.current.anchor)
                self.current.anchor = None
            self._clamp_link_index()
            self._ensure_link_visible()
            if self.search_query:
                self._refresh_search_hits()

    def _refresh_search_hits(self) -> None:
        if not self.current.render or not self.search_query:
            self.search_hits = []
            return
        self.search_hits = find_matches(self.current.render.plain_lines, self.search_query)
        if self.search_hits:
            self.search_index = min(self.search_index, len(self.search_hits) - 1)
        else:
            self.search_index = 0

    def _scroll_to_anchor(self, anchor: str) -> None:
        if not self.current.render:
            return
        anchor = anchor.lstrip("#").lower()
        for idx, line in enumerate(self.current.render.plain_lines):
            if _normalize_heading(line) == anchor:
                self.current.scroll = idx
                return

    def run(self) -> str:
        curses.curs_set(1 if self.mode == "search_input" else 0)
        self.stdscr.keypad(True)
        self.stdscr.timeout(-1)
        self.exit_action = "quit"

        while True:
            height, width = self.stdscr.getmaxyx()
            content_width = max(width - 1, 40)
            self._ensure_render(content_width)
            self._draw(height, width)
            key = self.stdscr.getch()
            if not self._handle_key(key, height):
                break

        return self.exit_action

    def _draw(self, height: int, width: int) -> None:
        self.stdscr.erase()
        render = self.current.render
        assert render is not None

        if self.show_help:
            self._draw_help(height, width)
        else:
            view_height = height - 2
            visible_start = self.current.scroll
            visible_end = min(visible_start + view_height, len(render.lines))

            for row, line_idx in enumerate(range(visible_start, visible_end)):
                highlights = self._highlights_for_line(line_idx)
                self._draw_line(row, 0, render.lines[line_idx], width - 1, highlights)

            if self.mode == "search_input":
                self._draw_search_prompt(height, width)
            else:
                self._draw_status(height, width)

        self.stdscr.refresh()

    def _highlights_for_line(self, line_idx: int) -> list[Highlight]:
        highlights: list[Highlight] = []

        for idx, (hit_line, col, end_col) in enumerate(self.search_hits):
            if hit_line != line_idx:
                continue
            current = self.mode == "search" and idx == self.search_index
            highlights.append(
                Highlight(
                    start=col,
                    end=end_col,
                    pair=PAIR_SEARCH_CURRENT if current else PAIR_SEARCH,
                    bold=current,
                )
            )

        if (
            self.mode != "search_input"
            and self.current.render
            and self.current.render.links
            and 0 <= self.current.link_index < len(self.current.render.links)
        ):
            link = self.current.render.links[self.current.link_index]
            if link.line == line_idx:
                highlights.append(
                    Highlight(start=link.col, end=link.end_col, pair=PAIR_LINK, bold=True)
                )

        highlights.sort(key=lambda h: h.start)
        return _merge_highlights(highlights)

    def _draw_line(
        self,
        y: int,
        x: int,
        text: str,
        max_width: int,
        highlights: list[Highlight],
    ) -> None:
        if not highlights:
            try:
                _addstr_ansi(self.stdscr, y, x, text, max_width)
            except curses.error:
                pass
            return

        plain_len = len(ANSI_ESCAPE.sub("", text))
        cursor = 0
        cx = x

        for hl in highlights:
            if cursor < hl.start:
                segment = text[_ansi_slice(text, cursor) : _ansi_slice(text, hl.start)]
                cx = _addstr_ansi(self.stdscr, y, cx, segment, max_width - (cx - x)) or cx
            segment = text[_ansi_slice(text, hl.start) : _ansi_slice(text, hl.end)]
            plain_seg = ANSI_ESCAPE.sub("", segment)
            remaining = max_width - (cx - x)
            if remaining <= 0:
                return
            try:
                attr = curses.color_pair(hl.pair)
                if hl.bold:
                    attr |= curses.A_BOLD
                self.stdscr.attron(attr)
                self.stdscr.addstr(y, cx, plain_seg[:remaining])
                self.stdscr.attroff(attr)
            except curses.error:
                pass
            cx += min(len(plain_seg), remaining)
            cursor = hl.end

        if cursor < plain_len:
            segment = text[_ansi_slice(text, cursor) :]
            _addstr_ansi(self.stdscr, y, cx, segment, max_width - (cx - x))

    def _draw_status(self, height: int, width: int) -> None:
        render = self.current.render
        assert render is not None
        name = self.current.path.name
        status = f" {name}  Línea {self.current.scroll + 1}/{max(len(render.lines), 1)}"

        if self.mode == "search" and self.search_query:
            total = len(self.search_hits)
            if total:
                status += f"  /{self.search_query}: {self.search_index + 1}/{total}"
            else:
                status += f"  /{self.search_query}: sin coincidencias"

        if render.links:
            link = render.links[self.current.link_index]
            status += f"  Enlace {self.current.link_index + 1}/{len(render.links)}: {link.href}"

        if self.message:
            status = f" {self.message} "

        try:
            self.stdscr.attron(curses.color_pair(PAIR_STATUS))
            self.stdscr.addstr(height - 1, 0, status.ljust(width - 1)[: width - 1])
            self.stdscr.attroff(curses.color_pair(PAIR_STATUS))
        except curses.error:
            pass

    def _draw_search_prompt(self, height: int, width: int) -> None:
        prompt = f" /{self.search_input}_"
        try:
            self.stdscr.attron(curses.color_pair(PAIR_STATUS))
            self.stdscr.addstr(height - 1, 0, prompt.ljust(width - 1)[: width - 1])
            self.stdscr.attroff(curses.color_pair(PAIR_STATUS))
            self.stdscr.move(height - 1, min(len(prompt) - 1, width - 2))
        except curses.error:
            pass

    def _draw_help(self, height: int, width: int) -> None:
        for row in range(height - 1):
            try:
                self.stdscr.attron(curses.A_REVERSE)
                self.stdscr.addstr(row, 0, " " * max(width - 1, 0))
                self.stdscr.attroff(curses.A_REVERSE)
            except curses.error:
                pass

        y = max(0, (height - len(HELP_LINES)) // 2 - 1)
        for line in HELP_LINES:
            if y >= height - 1:
                break
            x = max(0, (width - len(line)) // 2)
            try:
                self.stdscr.addstr(y, x, line[: max(width - x - 1, 0)])
            except curses.error:
                pass
            y += 1

    def _handle_key(self, key: int, height: int) -> bool:
        if self.show_help:
            self.show_help = False
            return True

        if self.mode == "search_input":
            return self._handle_search_input(key)

        self.message = ""

        if key == ord("/"):
            self.mode = "search_input"
            self.search_input = ""
            curses.curs_set(1)
            return True

        if key in (ord("h"), ord("H")):
            self.show_help = True
            return True

        if self.mode == "search":
            if key == ord("n"):
                self._next_search_hit(1)
                return True
            if key == ord("N"):
                self._next_search_hit(-1)
                return True
            if key == 27:
                self._clear_search()
                return True

        view_height = max(height - 2, 1)
        render = self.current.render
        assert render is not None
        max_scroll = max(0, len(render.lines) - view_height)

        if key in (ord("q"), 27):
            return False
        if key == curses.KEY_UP:
            self.current.scroll = max(0, self.current.scroll - 1)
        elif key == curses.KEY_DOWN:
            self.current.scroll = min(max_scroll, self.current.scroll + 1)
        elif key == curses.KEY_PPAGE:
            self.current.scroll = max(0, self.current.scroll - view_height)
        elif key == curses.KEY_NPAGE:
            self.current.scroll = min(max_scroll, self.current.scroll + view_height)
        elif key == curses.KEY_LEFT:
            self._prev_link()
        elif key == curses.KEY_RIGHT:
            self._next_link()
        elif key in (curses.KEY_ENTER, 10, 13):
            self._follow_link()
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            self._go_back()
            if self.exit_action == "browser":
                return False
        elif key == curses.KEY_HOME:
            self.current.scroll = 0
        elif key == curses.KEY_END:
            self.current.scroll = max_scroll

        return True

    def _handle_search_input(self, key: int) -> bool:
        if key == 27:
            self.mode = "normal"
            self.search_input = ""
            curses.curs_set(0)
            return True

        if key in (curses.KEY_BACKSPACE, 127, 8):
            self.search_input = self.search_input[:-1]
            return True

        if key in (curses.KEY_ENTER, 10, 13):
            self.search_query = self.search_input.strip()
            self._refresh_search_hits()
            self.mode = "search" if self.search_query else "normal"
            self.search_input = ""
            curses.curs_set(0)
            if self.search_hits:
                self.search_index = 0
                self._scroll_to_search_hit()
                self.message = f"{len(self.search_hits)} coincidencia(s)"
            elif self.search_query:
                self.message = "Sin coincidencias"
            return True

        if key == curses.KEY_DC:
            self.search_input = ""
            return True

        if 32 <= key <= 126:
            self.search_input += chr(key)

        return True

    def _next_search_hit(self, delta: int) -> None:
        if not self.search_hits:
            self.message = "Sin coincidencias"
            return
        self.search_index = (self.search_index + delta) % len(self.search_hits)
        self._scroll_to_search_hit()

    def _scroll_to_search_hit(self) -> None:
        if not self.search_hits:
            return
        line, _, _ = self.search_hits[self.search_index]
        height, _ = self.stdscr.getmaxyx()
        view_height = max(height - 2, 1)
        if line < self.current.scroll:
            self.current.scroll = line
        elif line >= self.current.scroll + view_height:
            self.current.scroll = line - view_height + 1

    def _clear_search(self) -> None:
        self.mode = "normal"
        self.search_query = ""
        self.search_hits = []
        self.search_index = 0

    def _prev_link(self) -> None:
        if not self.current.render or not self.current.render.links:
            return
        n = len(self.current.render.links)
        self.current.link_index = (self.current.link_index - 1) % n
        self._ensure_link_visible()

    def _next_link(self) -> None:
        if not self.current.render or not self.current.render.links:
            return
        n = len(self.current.render.links)
        self.current.link_index = (self.current.link_index + 1) % n
        self._ensure_link_visible()

    def _clamp_link_index(self) -> None:
        if not self.current.render or not self.current.render.links:
            self.current.link_index = 0
            return
        n = len(self.current.render.links)
        self.current.link_index = max(0, min(self.current.link_index, n - 1))

    def _ensure_link_visible(self) -> None:
        if not self.current.render or not self.current.render.links:
            return
        link = self.current.render.links[self.current.link_index]
        height, _ = self.stdscr.getmaxyx()
        view_height = max(height - 2, 1)
        if link.line < self.current.scroll:
            self.current.scroll = link.line
        elif link.line >= self.current.scroll + view_height:
            self.current.scroll = link.line - view_height + 1

    def _follow_link(self) -> None:
        if not self.current.render or not self.current.render.links:
            return
        link = self.current.render.links[self.current.link_index]
        resolved = resolve_href(link.href, self.current.path)

        if resolved is None:
            self.message = "Enlace inválido"
            return

        if isinstance(resolved, str) and resolved.startswith("#"):
            self._scroll_to_anchor(resolved)
            self.message = f"Ancla {resolved}"
            return

        if isinstance(resolved, str):
            try:
                webbrowser.open(resolved)
                self.message = f"Abierto: {resolved}"
            except OSError:
                self.message = "No se pudo abrir el enlace"
            return

        if not resolved.exists():
            self.message = f"No encontrado: {resolved.name}"
            return

        if resolved.suffix.lower() in {".md", ".markdown", ".mdown", ".mkd", ""}:
            self.history.append(self.current)
            self.current = self._load_page(resolved)
            self.current.render = None
            self._clear_search()
            return

        try:
            import subprocess

            subprocess.run(["xdg-open", str(resolved)], check=False)
            self.message = f"Abierto: {resolved.name}"
        except OSError:
            self.message = "No se pudo abrir el archivo"

    def _go_back(self) -> None:
        if not self.history:
            if self.allow_browser_return:
                self.exit_action = "browser"
            else:
                self.message = "Sin historial"
            return
        self.current = self.history.pop()
        self.current.render = None
        self._clear_search()


def run_app(path: Path, allow_browser_return: bool = False) -> None:
    curses.wrapper(
        lambda stdscr: MdrApp(stdscr, path, allow_browser_return=allow_browser_return).run()
    )


def _merge_highlights(highlights: list[Highlight]) -> list[Highlight]:
    if not highlights:
        return highlights
    merged = [highlights[0]]
    for hl in highlights[1:]:
        prev = merged[-1]
        if hl.start <= prev.end and hl.pair == prev.pair:
            merged[-1] = Highlight(prev.start, max(prev.end, hl.end), prev.pair, prev.bold or hl.bold)
        else:
            merged.append(hl)
    return merged


def _normalize_heading(line: str) -> str:
    text = line.strip().lower()
    if text.startswith("#"):
        text = text.lstrip("#").strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text.strip())
    return text


def _ansi_slice(text: str, plain_index: int) -> int:
    plain_count = 0
    i = 0
    while i < len(text) and plain_count < plain_index:
        match = ANSI_ESCAPE.match(text, i)
        if match:
            i = match.end()
            continue
        i += 1
        plain_count += 1
    return i


def _addstr_ansi(win, y: int, x: int, text: str, max_width: int) -> int:
    if max_width <= 0:
        return x

    attrs = curses.A_NORMAL
    col = x
    i = 0
    plain_len = 0

    while i < len(text) and plain_len < max_width:
        esc = ANSI_ESCAPE.match(text, i)
        if esc:
            attrs = _sgr_to_attr(esc.group(0), attrs)
            i = esc.end()
            continue

        ch = text[i]
        i += 1
        try:
            win.attron(attrs)
            win.addstr(y, col, ch)
            win.attroff(attrs)
        except curses.error:
            return col + 1
        col += 1
        plain_len += 1

    return col


def _sgr_to_attr(code: str, current: int) -> int:
    match = ANSI_SGR.match(code)
    if not match:
        return current

    parts = match.group(1).split(";") if match.group(1) else ["0"]
    attr = current

    for part in parts:
        if part in ("0", ""):
            attr = curses.A_NORMAL
        elif part == "1":
            attr |= curses.A_BOLD
        elif part == "4":
            attr |= curses.A_UNDERLINE
        elif part == "22":
            attr &= ~curses.A_BOLD
        elif part == "24":
            attr &= ~curses.A_UNDERLINE
        elif part.startswith("3") or part.startswith("9"):
            attr = _apply_fg(part, attr)

    return attr


def _apply_fg(code: str, attr: int) -> int:
    mapping = {
        "30": curses.COLOR_BLACK,
        "31": curses.COLOR_RED,
        "32": curses.COLOR_GREEN,
        "33": curses.COLOR_YELLOW,
        "34": curses.COLOR_BLUE,
        "35": curses.COLOR_MAGENTA,
        "36": curses.COLOR_CYAN,
        "37": curses.COLOR_WHITE,
    }
    color = mapping.get(code)
    if color is None:
        return attr
    pair = 10 + color
    try:
        curses.init_pair(pair, color, -1)
        return curses.color_pair(pair) | (attr & (curses.A_BOLD | curses.A_UNDERLINE))
    except curses.error:
        return attr
