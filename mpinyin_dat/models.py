from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Entry:
    word: str
    codes: tuple[str, ...] = ()
    rank: int = 0


class FormatError(ValueError):
    """Raised when a DAT file is structurally invalid or unsupported."""
