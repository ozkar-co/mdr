"""Búsqueda en texto renderizado."""

from __future__ import annotations


def find_matches(plain_lines: list[str], query: str) -> list[tuple[int, int, int]]:
    if not query:
        return []

    needle = query.casefold()
    hits: list[tuple[int, int, int]] = []

    for line_idx, line in enumerate(plain_lines):
        hay = line.casefold()
        start = 0
        while True:
            col = hay.find(needle, start)
            if col < 0:
                break
            hits.append((line_idx, col, col + len(query)))
            start = col + 1

    return hits
