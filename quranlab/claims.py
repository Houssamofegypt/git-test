"""The claim ledger.

A research claim is not a sentence in a draft; it is a sentence plus the query
that produces its number. Claims live in claims/*.toml and are re-run by
`quranlab claims`. A claim whose query no longer returns its recorded value
fails — because the sources moved, the normalization changed, or the claim was
wrong. Any of those you want to find out about from CI, not from a reviewer.

This is the piece that makes the rest of the repository *research* infrastructure
rather than a nicely-shaped copy of the text.

    [claim]
    id        = "0001-root-rhm-frequency"
    statement = "The root ر-ح-م occurs 339 times as a word in the corpus spine."
    level     = "n/a"            # which rung of the ladder the claim depends on
    author    = "..."
    date      = "2026-09-20"
    query     = "SELECT word_count FROM root WHERE text = 'رحم'"
    expect    = 339
    note      = "..."            # optional: caveats, scope, what would falsify it
"""

from __future__ import annotations

import json
import sqlite3
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .build import DB_PATH
from .fetch import ROOT

CLAIMS_DIR = ROOT / "claims"


@dataclass
class Claim:
    id: str
    statement: str
    query: str
    expect: object
    path: Path
    level: str = "n/a"
    author: str = "unattributed"
    date: str = ""
    note: str = ""


@dataclass
class Result:
    claim: Claim
    ok: bool
    actual: object
    error: str = ""


def load(directory: Path = CLAIMS_DIR) -> list[Claim]:
    claims = []
    for path in sorted(directory.glob("*.toml")):
        with path.open("rb") as fh:
            data = tomllib.load(fh)["claim"]
        missing = {"id", "statement", "query", "expect"} - data.keys()
        if missing:
            raise SystemExit(f"{path}: claim is missing {', '.join(sorted(missing))}")
        claims.append(Claim(
            id=data["id"], statement=data["statement"], query=data["query"],
            expect=data["expect"], path=path, level=data.get("level", "n/a"),
            author=data.get("author", "unattributed"), date=data.get("date", ""),
            note=data.get("note", ""),
        ))
    ids = [c.id for c in claims]
    if len(set(ids)) != len(ids):
        raise SystemExit("duplicate claim ids: " + ", ".join(sorted(
            {i for i in ids if ids.count(i) > 1})))
    return claims


def _normalize_result(rows: list[tuple]) -> object:
    """Shape a result set so `expect` can be written the obvious way.

        one row, one column     -> scalar        expect = 339
        one row, many columns   -> flat list     expect = [339, 62, 9]
        many rows, one column   -> flat list     expect = ["warsh", "qalun"]
        otherwise               -> list of lists
    """
    if not rows:
        return []
    if len(rows) == 1:
        return rows[0][0] if len(rows[0]) == 1 else list(rows[0])
    if len(rows[0]) == 1:
        return [r[0] for r in rows]
    return [list(r) for r in rows]


def check(conn: sqlite3.Connection, claim: Claim) -> Result:
    try:
        rows = conn.execute(claim.query).fetchall()
    except sqlite3.Error as exc:
        return Result(claim, False, None, f"query failed: {exc}")
    actual = _normalize_result(rows)
    expect = claim.expect
    # TOML has no tuples; compare structurally via JSON so [1,2] == (1,2).
    ok = json.loads(json.dumps(actual, default=str)) == json.loads(
        json.dumps(expect, default=str))
    return Result(claim, ok, actual)


def run(db_path: Path = DB_PATH, verbose: bool = True) -> bool:
    claims = load()
    if not claims:
        if verbose:
            print("  no claims recorded")
        return True
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        results = [check(conn, c) for c in claims]
    finally:
        conn.close()
    if verbose:
        for r in results:
            mark = "ok  " if r.ok else "FAIL"
            print(f"  [{mark}] {r.claim.id}")
            print(f"         {r.claim.statement}")
            if not r.ok:
                print(f"         expected: {r.claim.expect!r}")
                print(f"         actual:   {r.actual!r}")
                if r.error:
                    print(f"         {r.error}")
                print(f"         {r.claim.path}")
        passed = sum(1 for r in results if r.ok)
        print(f"\n  {passed}/{len(results)} claims reproduce")
    return all(r.ok for r in results)


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
