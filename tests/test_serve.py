"""Tests for the explorer's API.

The contract worth testing is not that the endpoints return 200 — it is that
the UI cannot see a number the database does not hold, and cannot reach
anything it was not given an endpoint for.
"""

import inspect
import json
import sqlite3

import pytest

from quranlab.build import DB_PATH
from quranlab.serve import ROUTES, Api

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="run `make build` first")


@pytest.fixture(scope="module")
def api():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    yield Api(conn)
    conn.close()


def test_every_route_is_a_method(api):
    for name in ROUTES:
        assert callable(getattr(api, name, None)), f"{name} is routed but not implemented"


def test_no_unlisted_public_method_is_reachable(api):
    """A method added without being routed stays unreachable — and vice versa.

    Tested against methods declared on the class, not on the instance:
    `sqlite3.Connection` is itself callable, so an attribute check alone would
    count the database handle as an endpoint.
    """
    declared = {n for n, v in vars(Api).items()
                if not n.startswith("_") and inspect.isfunction(v)}
    assert declared == set(ROUTES)


def test_every_route_is_json_serializable(api):
    for name in ROUTES:
        json.dumps(getattr(api, name)({}), ensure_ascii=False)


def test_every_route_takes_exactly_one_query_argument(api):
    """The dispatcher calls every endpoint as `method(query_dict)`."""
    for name in ROUTES:
        params = list(inspect.signature(getattr(api, name)).parameters)
        assert params == [params[0]] and len(params) == 1, name


def test_ladder_matches_the_database(api):
    """The UI must report exactly what is stored — not a recomputation."""
    d = api.ladder({"ref": ["Q2:2"]})
    ayah = d["ayahs"][0]
    stored = api.conn.execute(
        "SELECT plain, rasm, archigraphemic FROM ayah_text"
        " WHERE edition_id = 1 AND ayah_id = ?", (ayah["ayah_id"],)).fetchone()
    for rung in ("plain", "rasm", "archigraphemic"):
        assert ayah["rungs"][rung] == stored[rung]


def test_ladder_range_is_bounded(api):
    """A whole-surah reference must not become an unbounded export."""
    assert len(api.ladder({"ref": ["Q2"]})["ayahs"]) <= 50


def test_bad_reference_is_reported_not_raised(api):
    from quranlab.refs import RefError
    with pytest.raises(RefError):
        api.ladder({"ref": ["Q999:1"]})


def test_apparatus_separates_reading_from_orthography(api):
    """imlaei/indopak are the same Ḥafṣ reading; they must never be counted
    as variant readings."""
    d = api.apparatus({"ayah_id": ["262"]})       # Q2:255
    assert d["reference_riwayah"] == "hafs"
    for row in d["consonantal"] + d["vocalic"]:
        assert row["riwayah"] != "hafs"
    for row in d["orthographic"]:
        assert row["riwayah"] == "hafs"


def test_ayat_al_kursi_has_no_consonantal_riwayah_variance(api):
    assert api.apparatus({"ayah_id": ["262"]})["consonantal"] == []


def test_skeleton_projects_input_onto_the_stored_rung(api):
    """Searching a dotted word finds the cluster its skeleton belongs to."""
    d = api.skeleton({"q": ["تجري"]})
    assert d["skeleton"] == "ٮحرى"
    assert len(d["readings"]) > 1
    assert any(r["rasm"] == "تجري" for r in d["readings"])


def test_tree_recovers_the_transmission_pairs(api):
    """The tripwire, through the API the UI actually calls."""
    nearest = api.tree({})["nearest"]
    assert nearest["warsh"]["slug"] == "qalun"
    assert nearest["bazzi"]["slug"] == "qunbul"
    assert nearest["duri"]["slug"] == "susi"
    assert nearest["shuba"]["slug"] == "uthmani-hafs"
