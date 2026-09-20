"""Canonical reference parsing and formatting.

A reference names a location in the text without naming an edition, because the
verse spine (Kufan numbering) is shared by every edition we ingest. Four levels
of precision, plus ranges:

    Q2              surah
    Q2:255          ayah
    Q2:255:1        word
    Q2:255:1:2      segment
    Q2:255-2:257    range (inclusive, any level on either side)

This is deliberately close to the CTS/URN convention used in classics
(urn:cts:...:2.255) so that our references survive being pasted into a paper.
`str(Ref)` round-trips through `Ref.parse` for every reference we can produce.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PART = r"\d+"
_LOC = re.compile(rf"^(?:Q|q)?({_PART})(?::({_PART}))?(?::({_PART}))?(?::({_PART}))?$")


class RefError(ValueError):
    """Raised for a reference we cannot parse or that names an impossible location."""


@dataclass(frozen=True, order=True)
class Ref:
    """A point in the text. Unset components are None, coarsest-first."""

    surah: int
    ayah: int | None = None
    word: int | None = None
    segment: int | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.surah <= 114:
            raise RefError(f"surah out of range: {self.surah}")
        # Precision must be contiguous: a word reference needs an ayah.
        parts = [self.ayah, self.word, self.segment]
        seen_none = False
        for p in parts:
            if p is None:
                seen_none = True
            elif seen_none:
                raise RefError(f"non-contiguous reference: {self!r}")
            elif p < 1:
                raise RefError(f"component must be >= 1: {p}")

    @property
    def level(self) -> str:
        if self.segment is not None:
            return "segment"
        if self.word is not None:
            return "word"
        if self.ayah is not None:
            return "ayah"
        return "surah"

    @classmethod
    def parse(cls, text: str) -> "Ref":
        m = _LOC.match(text.strip())
        if not m:
            raise RefError(f"cannot parse reference: {text!r}")
        nums = [int(g) if g is not None else None for g in m.groups()]
        return cls(nums[0], nums[1], nums[2], nums[3])

    def __str__(self) -> str:
        parts = [self.surah, self.ayah, self.word, self.segment]
        return "Q" + ":".join(str(p) for p in parts if p is not None)


@dataclass(frozen=True)
class RefRange:
    """An inclusive span between two references."""

    start: Ref
    end: Ref

    def __post_init__(self) -> None:
        if (self.end.surah, self.end.ayah or 0) < (self.start.surah, self.start.ayah or 0):
            raise RefError(f"range runs backwards: {self.start}-{self.end}")

    @classmethod
    def parse(cls, text: str) -> "RefRange":
        text = text.strip()
        if "-" not in text:
            r = Ref.parse(text)
            return cls(r, r)
        left, right = text.split("-", 1)
        start = Ref.parse(left)
        # "Q2:255-257" means 2:255 to 2:257: inherit the surah when omitted.
        right = right.strip()
        if right.count(":") < left.strip().lstrip("Qq").count(":"):
            right = f"{start.surah}:{right}"
        return cls(start, Ref.parse(right))

    def __str__(self) -> str:
        if self.start == self.end:
            return str(self.start)
        return f"{self.start}-{str(self.end).lstrip('Qq')}"


def parse(text: str) -> RefRange:
    """Parse any reference or range. The one entry point callers should use."""
    return RefRange.parse(text)
