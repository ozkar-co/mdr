"""Extracción de enlaces desde Markdown."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from markdown_it import MarkdownIt


def _parser() -> MarkdownIt:
    return (
        MarkdownIt("commonmark", {"linkify": True})
        .enable("strikethrough")
        .enable("table")
    )


@dataclass(frozen=True)
class Link:
    href: str
    text: str
    source_line: int  # 1-based line in source file


def extract_links(content: str) -> list[Link]:
    """Return inline links in document order."""
    tokens = _parser().parse(content)
    lines = content.splitlines()
    links: list[Link] = []
    _collect_links(tokens, lines, links)
    return links


def _collect_links(tokens, lines: list[str], links: list[Link]) -> None:
    for i, token in enumerate(tokens):
        if token.children:
            _collect_links(token.children, lines, links)
        if token.type != "link_open":
            continue
        href = token.attrGet("href")
        if not href:
            continue
        text = _link_text(tokens, i)
        line = _token_line(lines, token.map)
        links.append(Link(href=str(href), text=text, source_line=line))


def _link_text(tokens, link_open_index: int) -> str:
    parts: list[str] = []
    for token in tokens[link_open_index + 1 :]:
        if token.type == "link_close":
            break
        if token.type == "text":
            parts.append(token.content)
        elif token.type == "code_inline":
            parts.append(token.content)
    return "".join(parts) or "(enlace)"


def _token_line(lines: list[str], token_map) -> int:
    if token_map:
        return token_map[0] + 1
    return 1


def resolve_href(href: str, base_path: Path) -> Path | str | None:
    """Resolve href to a local path, external URL, or in-document anchor."""
    href = href.strip()
    if not href:
        return None

    if href.startswith("#"):
        return href

    if href.startswith(("http://", "https://", "mailto:")):
        return href

    if href.startswith("file://"):
        return Path(href[7:])

    target = (base_path.parent / href).resolve()
    if target.exists():
        return target

    # Allow links without extension to .md files
    md_target = target.with_suffix(".md")
    if md_target.exists():
        return md_target

    return target
