"""Counting with the rule attached.

"How many times is night mentioned in the Quran?" has no answer. It has about
six, and they differ by a factor of five. The widely-repeated claim that *yawm*
occurs 365 times survives none of them: the root gives 475, singular-only 446,
definite-only 77.

So this module refuses to return a bare number. A count is a `CountSpec` — a
named, explicit rule — and a result that carries the spec that produced it. Two
counts are comparable only if their specs are, and `compare()` enforces that.

The point is not pedantry. Numerical claims about the Quran circulate widely and
are almost always artefacts of an unstated counting rule. Making the rule part of
the result is what turns "night appears 92 times" from a factoid into a finding
someone else can check.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

#: Grammatical number, as the morphology marks it.
NUMBERS = {"singular": "S", "dual": "D", "plural": "P"}

UNITS = ("root", "lemma", "form", "rasm")


@dataclass(frozen=True)
class CountSpec:
    """A counting rule. Every field changes the answer, so every field is stated."""

    unit: str                      # root | lemma | form | rasm
    value: str
    numbers: tuple[str, ...] = ()  # (), or any of singular/dual/plural
    definite: bool | None = None   # None = either; True = with al-; False = without
    pos: str | None = None         # N | V | P
    scope: str = "all"             # all | meccan | medinan
    label: str = ""

    def __post_init__(self) -> None:
        if self.unit not in UNITS:
            raise ValueError(f"unit must be one of {UNITS}, not {self.unit!r}")
        bad = set(self.numbers) - set(NUMBERS)
        if bad:
            raise ValueError(f"unknown grammatical number(s): {sorted(bad)}")
        if self.scope not in ("all", "meccan", "medinan"):
            raise ValueError(f"unknown scope {self.scope!r}")

    def describe(self) -> str:
        bits = [f"{self.unit} {self.value}"]
        if self.numbers:
            bits.append("+".join(sorted(self.numbers)))
        if self.definite is True:
            bits.append("definite only")
        elif self.definite is False:
            bits.append("indefinite only")
        if self.pos:
            bits.append(f"pos={self.pos}")
        if self.scope != "all":
            bits.append(self.scope)
        return ", ".join(bits)


@dataclass
class CountResult:
    spec: CountSpec
    words: int
    ayahs: int
    surahs: int
    per_10k: float
    examples: list = field(default_factory=list)

    def __str__(self) -> str:
        return (f"{self.words} words / {self.ayahs} ayahs / {self.surahs} surahs"
                f"  [{self.spec.describe()}]")


_COL = {"root": "w.root", "lemma": "w.lemma", "form": "w.form", "rasm": "w.rasm"}


#: The stem segment: the one carrying the word's lexical identity. Affixes are
#: marked PREF/SUFF by the corpus, and this matters more than it looks — a
#: pronoun suffix carries its own number, so `yawmihim` ("their day") is a
#: SINGULAR noun with a 3MP suffix. Reading number off any segment counts it as
#: plural, and 27 occurrences of this root alone are affected.
_STEM = """
    SELECT sg.features FROM segment sg WHERE sg.word_id = w.id
      AND ',' || REPLACE(sg.features, '|', ',') || ',' NOT LIKE '%,PREF,%'
      AND ',' || REPLACE(sg.features, '|', ',') || ',' NOT LIKE '%,SUFF,%'
"""

#: Number tags as the corpus writes them, with and without a gender prefix.
_NUMBER_TAGS = {"D": ("MD", "FD", "D"), "P": ("MP", "FP", "P")}


def _tagged(letter: str) -> tuple[str, list]:
    """SQL testing whether the STEM segment carries a given number tag."""
    tags = _NUMBER_TAGS[letter]
    ors = " OR ".join(
        "',' || REPLACE(f.features, '|', ',') || ',' LIKE ?" for _ in tags)
    return (f"EXISTS (SELECT 1 FROM ({_STEM}) f WHERE {ors})",
            [f"%,{t},%" for t in tags])


def _where(spec: CountSpec) -> tuple[str, list]:
    clauses = [f"{_COL[spec.unit]} = ?"]
    params: list = [spec.value]
    if spec.scope != "all":
        clauses.append("s.revelation_place = ?")
        params.append(spec.scope)
    if spec.pos:
        clauses.append("w.pos = ?")
        params.append(spec.pos)

    if spec.numbers:
        ors, oparams = [], []
        for name in sorted(spec.numbers):
            if name == "singular":
                # Singular is unmarked: no dual and no plural tag on the stem.
                dual, dp = _tagged("D")
                plural, pp = _tagged("P")
                ors.append(f"(NOT {dual} AND NOT {plural})")
                oparams.extend(dp + pp)
            else:
                sql, sp = _tagged(NUMBERS[name])
                ors.append(sql)
                oparams.extend(sp)
        clauses.append("(" + " OR ".join(ors) + ")")
        params.extend(oparams)

    if spec.definite is not None:
        # The definite article is a PREFIX segment, so this one correctly looks
        # across all segments rather than only the stem.
        op = "EXISTS" if spec.definite else "NOT EXISTS"
        clauses.append(
            f"{op} (SELECT 1 FROM segment sg WHERE sg.word_id = w.id"
            f" AND ',' || REPLACE(sg.features, '|', ',') || ',' LIKE '%,DET,%')")
    return " AND ".join(clauses), params


def count(conn: sqlite3.Connection, spec: CountSpec, examples: int = 0) -> CountResult:
    where, params = _where(spec)
    sql = f"""
        SELECT COUNT(*) AS words, COUNT(DISTINCT w.ayah_id) AS ayahs,
               COUNT(DISTINCT a.surah) AS surahs
        FROM word w JOIN ayah a ON a.id = w.ayah_id
        JOIN surah s ON s.number = a.surah WHERE {where}"""
    row = conn.execute(sql, params).fetchone()
    total = conn.execute(
        "SELECT COUNT(*) FROM word w JOIN ayah a ON a.id = w.ayah_id"
        " JOIN surah s ON s.number = a.surah"
        + (" WHERE s.revelation_place = ?" if spec.scope != "all" else ""),
        ([spec.scope] if spec.scope != "all" else [])).fetchone()[0]
    ex = []
    if examples:
        ex = [dict(r) for r in conn.execute(
            f"""SELECT 'Q' || a.surah || ':' || a.number || ':' || w.position AS ref,
                       w.form, w.lemma
                FROM word w JOIN ayah a ON a.id = w.ayah_id
                JOIN surah s ON s.number = a.surah
                WHERE {where} ORDER BY w.id LIMIT {int(examples)}""", params)]
    return CountResult(spec, row[0], row[1], row[2],
                       10000 * row[0] / total if total else 0.0, ex)


def compare(conn: sqlite3.Connection, a: CountSpec, b: CountSpec) -> dict:
    """Compare two counts, refusing to compare rules that are not alike.

    Comparing a root count to a lemma count, or a Meccan count to a whole-corpus
    count, is the mechanism behind most circulating numerical claims. It is a
    error here, not a footnote.
    """
    differing = [f for f in ("unit", "numbers", "definite", "pos", "scope")
                 if getattr(a, f) != getattr(b, f)]
    if differing:
        raise ValueError(
            "refusing to compare counts whose rules differ in: "
            + ", ".join(differing)
            + f"\n  A: {a.describe()}\n  B: {b.describe()}"
            + "\nMake the rules identical, or state the comparison as two separate counts.")
    ra, rb = count(conn, a), count(conn, b)
    return {
        "a": ra, "b": rb, "rule": a.describe().replace(f"{a.unit} {a.value}", a.unit),
        "ratio": (ra.words / rb.words) if rb.words else None,
        "equal": ra.words == rb.words,
    }
