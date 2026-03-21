from __future__ import annotations


def kebab_to_camel(s: str) -> str:
    """Convert kebab-case to camelCase."""
    parts = s.split("-")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])
