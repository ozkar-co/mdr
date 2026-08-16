"""Extracción de enlaces desde Markdown."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from markdown_it import MarkdownIt

LOCAL_LINK_SUFFIX = re.compile(
    r"\[([^\]]+)\]\(([^)]+)\)([a-záéíóúñü]{1,3})(?=[\s,.;:!?\)'\"]|$)"
)
LOCAL_LINK_SPACES = re.compile(
    r"\[([^\]]+)\]\(([^<>\)]+)\)"
)


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


def _normalize_markdown_links(content: str) -> str:
    """Fix common wiki link shapes that CommonMark would not parse."""
    content = LOCAL_LINK_SUFFIX.sub(r"[\1\3](\2)", content)
    content = LOCAL_LINK_SPACES.sub(
        lambda match: (
            f"[{match.group(1)}](<{match.group(2)}>)"
            if " " in match.group(2)
            and not match.group(2).startswith(("http://", "https://", "mailto:"))
            else match.group(0)
        ),
        content,
    )
    return content


def _normalize_href(href: str) -> str:
    href = unquote(href.strip())
    if href.startswith("<") and href.endswith(">"):
        href = href[1:-1]
    return href


def extract_links(content: str) -> list[Link]:
    """Return inline links in document order."""
    content = _normalize_markdown_links(content)
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


def _find_local_file(base_path: Path, href: str) -> Path | None:
    name = Path(href).name
    direct = (base_path.parent / href).resolve()
    if direct.exists():
        return direct

    if not name.lower().endswith(".md"):
        md_name = f"{name}.md"
        md_direct = (base_path.parent / md_name).resolve()
        if md_direct.exists():
            return md_direct
        name = md_name

    for candidate in base_path.parent.iterdir():
        if candidate.is_file() and candidate.name.lower() == name.lower():
            return candidate.resolve()
    return None


def resolve_href(href: str, base_path: Path) -> Path | str | None:
    """Resolve href to a local path, external URL, or in-document anchor."""
    href = _normalize_href(href)
    if not href:
        return None

    if href.startswith("#"):
        return href

    if href.startswith(("http://", "https://", "mailto:")):
        return href

    if href.startswith("file://"):
        return Path(href[7:])

    found = _find_local_file(base_path, href)
    if found is not None:
        return found

    return (base_path.parent / href).resolve()
