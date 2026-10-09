"""Renderizado de Markdown con Rich."""

from __future__ import annotations

import re
from dataclasses import dataclass
from io import StringIO

from rich.console import Console
from rich.markdown import Markdown

from links import Link, _normalize_markdown_links

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
TERMINAL_CONTROL = re.compile(
    r"\x1b\[[0-9;]*m"      # colores/estilos SGR
    r"|\x1b\]8;[^\\]*\\"   # hipervínculos OSC 8 (Rich)
)


def strip_terminal_controls(text: str) -> str:
    return TERMINAL_CONTROL.sub("", text)


@dataclass
class RenderedLink:
    href: str
    text: str
    line: int  # 0-based index in rendered lines
    col: int
    end_col: int


@dataclass
class RenderResult:
    lines: list[str]
    plain_lines: list[str]
    links: list[RenderedLink]
    width: int


def render_markdown(content: str, source_links: list[Link], width: int) -> RenderResult:
    """Render markdown to ANSI-colored lines and locate links."""
    content = _normalize_markdown_links(content)
    console = Console(
        file=StringIO(),
        force_terminal=True,
        width=max(width, 40),
        color_system="truecolor",
        record=False,
    )
    console.print(Markdown(content, code_theme="monokai"))
    raw = console.file.getvalue()
    lines = raw.splitlines()
    plain_lines = [strip_terminal_controls(line) for line in lines]
    rendered_links = _locate_links(plain_lines, source_links)
    return RenderResult(
        lines=lines,
        plain_lines=plain_lines,
        links=rendered_links,
        width=width,
    )


def _locate_links(plain_lines: list[str], source_links: list[Link]) -> list[RenderedLink]:
    """Find link text positions in rendered output."""
    rendered: list[RenderedLink] = []
    used: list[tuple[int, int]] = []

    for link in source_links:
        pos = _find_text(plain_lines, link.text, used)
        if pos is None:
            continue
        line, col, end_col = pos
        used.append((line, col))
        rendered.append(
            RenderedLink(
                href=link.href,
                text=link.text,
                line=line,
                col=col,
                end_col=end_col,
            )
        )

    return rendered


def _find_text(
    lines: list[str],
    text: str,
    used: list[tuple[int, int]],
) -> tuple[int, int, int] | None:
    if not text:
        return None

    candidates = [text]
    # Rich may strip outer whitespace from link labels
    stripped = text.strip()
    if stripped and stripped not in candidates:
        candidates.append(stripped)

    for candidate in candidates:
        for line_idx, line in enumerate(lines):
            start = 0
            while True:
                col = line.find(candidate, start)
                if col < 0:
                    break
                if (line_idx, col) in used:
                    start = col + 1
                    continue
                return line_idx, col, col + len(candidate)
                start = col + 1

    return None
