"""Descubrimiento de archivos Markdown."""

from __future__ import annotations

from pathlib import Path

MD_EXTENSIONS = {".md", ".markdown", ".mdown", ".mkd"}
SKIP_DIRS = {".venv", ".git", "__pycache__", "node_modules", "dist", "build"}


def find_markdown_files(root: Path) -> list[Path]:
    root = root.resolve()
    if not root.is_dir():
        return []

    found: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in MD_EXTENSIONS:
            continue
        rel = path.relative_to(root)
        if rel.name.startswith("."):
            continue
        if any(part in SKIP_DIRS or part.startswith(".") for part in rel.parts[:-1]):
            continue
        found.append(path)

    return sorted(found, key=lambda p: str(p.relative_to(root)).lower())
