"""Data-level tests. Skipped when the database has not been built yet."""

import sqlite3

import pytest

from quranlab.build import DB_PATH
from quranlab.claims import run as run_claims
from quranlab.verify import checks

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(), reason="run `make build` first")


@pytest.fixture(scope="module")
def conn():
    c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    c.execute("PRAGMA foreign_keys = ON")
    yield c
    c.close()


def test_all_invariants_hold(conn):
    failures = [(name, detail) for name, ok, detail in checks(conn) if not ok]
    assert not failures, "\n".join(f"{n}: {d}" for n, d in failures)


def test_claims_reproduce():
    assert run_claims(verbose=False)


def test_reference_lookup(conn):
    row = conn.execute(
        "SELECT ref FROM v_ayah WHERE surah = 2 AND number = 255").fetchone()
    assert row[0] == "Q2:255"


def test_word_spans_are_well_formed(conn):
    bad = conn.execute("""
        SELECT COUNT(*) FROM ayah
        WHERE word_start IS NULL OR word_end IS NULL OR word_end < word_start
    """).fetchone()[0]
    assert bad == 0


def test_annotation_span_constraint_is_enforced(tmp_path):
    """A stand-off annotation cannot name a backwards span."""
    import shutil
    from pathlib import Path
    scratch = tmp_path / "copy.db"
    shutil.copy(DB_PATH, scratch)
    c = sqlite3.connect(scratch)
    c.execute("PRAGMA foreign_keys = ON")
    layer = c.execute(
        "SELECT COALESCE(MAX(id), 0) + 1 FROM annotation_layer").fetchone()[0]
    c.execute("INSERT INTO annotation_layer (id, slug, title, description, author,"
              " method, created_at) VALUES (?,'t','T','test','t','manual','now')",
              (layer,))
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO annotation (layer_id, word_start, word_end, key,"
                  " created_at) VALUES (?, 100, 50, 'k', 'now')", (layer,))
    c.close()


def test_every_edition_covers_every_ayah(conn):
    gaps = conn.execute("""
        SELECT COUNT(*) FROM edition e CROSS JOIN ayah a
        WHERE NOT EXISTS (
            SELECT 1 FROM ayah_text t
            WHERE t.edition_id = e.id AND t.ayah_id = a.id)
    """).fetchone()[0]
    assert gaps == 0


def test_interrupted_build_leaves_no_usable_database(tmp_path, monkeypatch):
    """A half-written database opens fine and answers every query with zero rows.

    Anything downstream then reports an empty corpus as a fact, so the build
    writes to a temporary file and moves it into place only on success.
    """
    from quranlab import build as build_mod

    target = tmp_path / "quran.db"
    boom = RuntimeError("interrupted")

    def explode(*_a, **_k):
        raise boom

    monkeypatch.setattr(build_mod, "load_spine", explode)
    with pytest.raises(RuntimeError):
        build_mod.build(target)

    assert not target.exists(), "a partial build must not be left in place"
