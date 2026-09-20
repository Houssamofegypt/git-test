import pytest

from quranlab.refs import Ref, RefError, parse


@pytest.mark.parametrize("text,expected", [
    ("Q2:255", "Q2:255"),
    ("2:255", "Q2:255"),
    ("q2:255", "Q2:255"),
    ("Q112", "Q112"),
    ("Q2:255:1", "Q2:255:1"),
    ("Q2:255:1:2", "Q2:255:1:2"),
])
def test_round_trip(text, expected):
    assert str(parse(text).start) == expected


def test_range_inherits_surah():
    r = parse("Q2:255-257")
    assert (str(r.start), str(r.end)) == ("Q2:255", "Q2:257")


def test_range_across_surahs():
    r = parse("Q2:285-3:1")
    assert (str(r.start), str(r.end)) == ("Q2:285", "Q3:1")


def test_levels():
    assert Ref(2).level == "surah"
    assert Ref(2, 255).level == "ayah"
    assert Ref(2, 255, 1).level == "word"
    assert Ref(2, 255, 1, 2).level == "segment"


@pytest.mark.parametrize("bad", ["Q0:1", "Q115:1", "Q2:0", "nonsense", "", "Q2:-1"])
def test_rejects_impossible(bad):
    with pytest.raises(RefError):
        parse(bad)


def test_rejects_non_contiguous():
    with pytest.raises(RefError):
        Ref(2, None, 5)


def test_rejects_backwards_range():
    with pytest.raises(RefError):
        parse("Q3:1-2:1")
