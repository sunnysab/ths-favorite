from __future__ import annotations

from typing import Dict


def parse_cookie_string(raw: str) -> Dict[str, str]:
    """Parse a ``Cookie`` header string into a dictionary."""

    cookies: Dict[str, str] = {}
    if not raw:
        return cookies
    for pair_str in raw.split(";"):
        pair_str = pair_str.strip()
        if not pair_str or "=" not in pair_str:
            continue
        name, value = pair_str.split("=", 1)
        cookies[name.strip()] = value.strip()
    return cookies


def parse_cookie_header(header: str) -> Dict[str, str]:
    """Parse a ``Set-Cookie`` style header containing comma-separated cookies."""

    cookies: Dict[str, str] = {}
    if not header:
        return cookies
    for part in header.split(","):
        segment = part.strip()
        if not segment:
            continue
        pair = segment.split(";", 1)[0]
        if "=" not in pair:
            continue
        name, value = pair.split("=", 1)
        cookies[name.strip()] = value.strip()
    return cookies
