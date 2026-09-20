"""Tests for counting and lexical fields.

The bug class these exist to prevent is a plausible wrong number. A count that
is off by 5% raises nothing, reads fine, and ends up in a footnote.
"""

import sqlite3

import pytest

from quranlab.build import DB_PATH
from quranlab.counting import CountSpec, compare, count
from quranlab.fields import load_definitions
from quranlab.search import Scope, cooccur

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="run `make build` first")


@pytest.fixture(scope="module")
def conn():
    c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    yield c
    c.close()


# --- the partition invariant -------------------------------------------------

@pytest.mark.parametrize("root", ["يوم", "ليل", "نهر", "صبر", "أمن", "كفر", "علم", "رحم"])
def test_grammatical_number_partitions_the_total(conn, root):
    """singular + dual + plural must equal the total, for every root.

    This is the check that caught the original bug: number was read off any
    segment, so `yawmihim` ("their day") scored as plural because its pronoun
    suffix is 3MP. The partition did not sum, and could not be made to.
    """
    total = count(conn, CountSpec("root", root)).words
    parts = sum(count(conn, CountSpec("root", root, numbers=(n,))).words
                for n in ("singular", "dual", "plural"))
    assert parts == total, f"{root}: partition {parts} != total {total}"


def test_definite_and_indefinite_also_partition(conn):
    total = count(conn, CountSpec("root", "يوم")).words
    d = count(conn, CountSpec("root", "يوم", definite=True)).words
    i = count(conn, CountSpec("root", "يوم", definite=False)).words
    assert d + i == total


def test_yawm_is_not_365_under_any_supported_rule(conn):
    """The claim that yawm occurs 365 times survives no counting rule here."""
    rules = [
        CountSpec("root", "يوم"),
        CountSpec("root", "يوم", numbers=("singular",)),
        CountSpec("root", "يوم", definite=True),
        CountSpec("root", "يوم", definite=False),
        CountSpec("root", "يوم", numbers=("singular",), definite=True),
        CountSpec("root", "يوم", numbers=("singular",), definite=False),
    ]
    assert 365 not in {count(conn, r).words for r in rules}


def test_scopes_partition_the_corpus(conn):
    total = count(conn, CountSpec("root", "صبر")).words
    m = count(conn, CountSpec("root", "صبر", scope="meccan")).words
    d = count(conn, CountSpec("root", "صبر", scope="medinan")).words
    assert m + d == total


# --- the comparison guard ----------------------------------------------------

def test_compare_refuses_mismatched_rules(conn):
    with pytest.raises(ValueError, match="unit"):
        compare(conn, CountSpec("root", "ليل"), CountSpec("lemma", "يَوْم"))
    with pytest.raises(ValueError, match="scope"):
        compare(conn, CountSpec("root", "ليل"),
                CountSpec("root", "نهر", scope="meccan"))


def test_compare_allows_like_for_like(conn):
    d = compare(conn, CountSpec("root", "ليل"), CountSpec("root", "نهر"))
    assert d["a"].words == 92 and d["b"].words == 113
    assert d["equal"] is False


def test_spec_rejects_nonsense():
    for bad in [dict(unit="colour", value="x"), dict(unit="root", value="x", numbers=("many",)),
                dict(unit="root", value="x", scope="martian")]:
        with pytest.raises(ValueError):
            CountSpec(**bad)


# --- co-occurrence -----------------------------------------------------------

def test_the_unit_changes_the_answer_and_is_reported(conn):
    """Widening the unit can only add hits, and the unit is always named."""
    terms = [("root", "صبر"), ("root", "جنن")]
    seen = {}
    for unit in ("ayah", "ruku", "surah"):
        d = cooccur(conn, terms, Scope(unit), limit=1)
        assert unit in d["scope"]
        seen[unit] = d["total"]
    assert seen["ayah"] <= seen["ruku"] <= seen["surah"]


def test_cooccurrence_needs_two_terms(conn):
    with pytest.raises(ValueError, match="at least two"):
        cooccur(conn, [("root", "صبر")])


# --- lexical fields ----------------------------------------------------------

def test_every_field_member_matches_something(conn):
    """A member that matches nothing is nearly always a diacritic typo, and the
    silence looks exactly like a real zero."""
    empty = conn.execute("""
        SELECT f.slug, m.value FROM lexical_field_member m
        JOIN lexical_field f ON f.id = m.field_id WHERE m.matched = 0""").fetchall()
    assert not empty, [(r["slug"], r["value"]) for r in empty]


def test_every_field_declares_an_author_and_method(conn):
    """Field membership is editorial; it may never be anonymous."""
    bad = conn.execute(
        "SELECT slug FROM lexical_field WHERE author = '' OR method = ''").fetchall()
    assert not bad


def test_field_definitions_on_disk_are_well_formed():
    for f in load_definitions():
        assert f["members"], f["slug"]
        for m in f["members"]:
            assert m["kind"] in ("root", "lemma")
            assert 0 < float(m.get("confidence", 1.0)) <= 1.0


def test_fawasil_rule_excludes_the_narrative_aziz(conn):
    """al-'Aziz in Surat Yusuf is an Egyptian official, not a divine name.
    The positional rule must exclude it without a hand-written blacklist."""
    in_yusuf = conn.execute("""
        SELECT COUNT(*) FROM v_field_word v
        WHERE v.field = 'divine-names' AND v.surah = 12 AND v.via_value LIKE 'عَزِيز%'
    """).fetchone()[0]
    assert in_yusuf == 0


def test_rabb_is_excluded_from_surat_yusuf(conn):
    """rabb there means a human master (Q12:41, 42, 50)."""
    n = conn.execute("""
        SELECT COUNT(*) FROM v_field_word v
        WHERE v.field = 'divine-names' AND v.surah = 12 AND v.via_value LIKE 'رَبّ%'
    """).fetchone()[0]
    assert n == 0


def test_lexical_field_finds_the_paraphrase_root_search_misses(conn):
    """Q13:24 promises the reward of patience as 'the excellent final home' and
    contains neither core root. It is the reason the field layer exists."""
    fields = {r[0] for r in conn.execute("""
        SELECT DISTINCT v.field FROM v_field_word v JOIN ayah a ON a.id = v.ayah_id
        WHERE a.surah = 13 AND a.number = 24""")}
    assert {"patience", "paradise"} <= fields
