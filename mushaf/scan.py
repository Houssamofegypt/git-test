"""Scan the whole text for passages on the reader's three themes.

    python3 mushaf/scan.py            # prints a summary; build.py imports scan()

Themes (the reader's own words): God's MERCY, the REWARD of the faithful, and
God's NAMES and qualities. Every verse gets a weight per theme from the
morphology (lemmas, so رَحْمَة and رَحِيم count but أَرْحام "wombs" does not), plus a
few unmistakable formulas of self-description read off the unvocalized text.
Strong verses seed passages, and each seed grows into its neighbours until it
reads as a unit (enough words, staying inside the traditional rukūʿ section
where it can). Passages are scored by theme weight per √word, so the long
legal verses that merely close on "God is forgiving, merciful" do not win on
length alone.

This is a recall instrument with judgement written down as weights. It
finds candidates; the reader decides what to keep.
"""
import math, re, sqlite3, sys, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / "quran.db"

MERCY = {"رَحْمَة": 1, "رَحِمَ": 1, "رَحْمٰن": 1, "رَحِيم": 1, "أَرْحَم": 1, "راحِم": 1,
         "غَفُور": 1, "غَفَرَ": 1, "مَغْفِرَة": 1, "غَفّار": 1, "غافِر": 1, "غُفْران": 1, "اسْتَغْفَرَ": .6,
         "عَفا": .8, "عَفُوّ": 1, "رَءُوف": 1, "رَأْفَة": 1, "وَدُود": 1, "تَوّاب": 1, "تابَ": .7, "تَوْبَة": .7,
         "لَطِيف": .6, "حَلِيم": .6, "فَضْل": .5, "يُسْر": .6, "يُسْرَى": .6, "تَوْب": .7, "نِعْمَة": .5, "أَنْعَمَ": .5}
REWARD = {"جَنَّة": 1, "فِرْدَوْس": 1, "نَعِيم": 1, "رِضْوان": 1, "أَجْر": .8, "فَوْز": 1, "فائِز": 1,
          "بُشْرَى": .8, "عُقْبَى": .6, "خُلْد": .5, "عَدْن": 1, "ثَواب": .8, "طُوبَى": 1, "خُلُود": .5, "رَضِيَ": .6, "راضِيَة": .6, "سَلام": .4,
          # the furniture of the Garden: these words describe paradise and little else
          "سُرُر": .6, "أَرائِك": .6, "حُور": .6, "كَأْس": .5, "فاكِهَة": .4, "سُندُس": .6, "إِسْتَبْرَق": .6,
          "سَلْسَبِيل": .6, "كافُور": .5, "زَنجَبِيل": .6, "رَحِيق": .6, "تَسْنِيم": .6, "حَرِير": .5, "نَضْرَة": .6,
          "ناضِرَة": .6, "مُتَّكِئ": .6, "قُطُوف": .6, "دانِيَة": .4, "نَمارِق": .6, "زَرابِيّ": .6, "ياقُوت": .6}
NAMES = set("""رَحْمٰن رَحِيم غَفُور غَفّار عَفُوّ رَءُوف وَدُود تَوّاب عَلِيم عَلّام حَكِيم عَزِيز سَمِيع بَصِير
  قَدِير مُقْتَدِر خَبِير لَطِيف حَلِيم حَمِيد مَجِيد قُدُّوس مُهَيْمِن خالِق خَلّاق بارِئ مُصَوِّر قَيُّوم عَلِيّ
  واسِع غَنِيّ رَزّاق فَتّاح وَهّاب قَهّار صَمَد رَقِيب حَسِيب مُقِيت مُجِيب قَوِيّ مَتِين فاطِر بَدِيع
  شَكُور ظاهِر باطِن""".split())
PUNISH = {"عَذاب": 1, "عَذَّبَ": 1, "جَهَنَّم": 1, "جَحِيم": 1, "سَعِير": 1, "سَقَر": 1, "لَظَى": 1}
# legal and battle vocabulary: those passages close on "forgiving, merciful" but are rulings
LEGAL = {"طَلَّقَ": 1, "مُطَلَّقَة": 1, "طَلاق": 1, "نَكَحَ": 1, "نِكاح": 1, "عِدَّة": 1, "مَحِيض": 1, "أَرْضَعَتْ": 1,
         "رَضاعَة": 1, "قِصاص": 1, "دِيَة": 1, "رِبا": 1, "مِيراث": 1, "وَصِيَّة": .6, "دَيْن": 1, "سارِق": 1,
         "سارِقَة": 1, "زانِيَة": 1, "زان": 1, "قاتَلَ": .6, "قِتال": .6, "قَتَلَ": .6, "غَنِمَ": 1, "حَرَّمَ": .5, "أَحَلَّ": .5,
         "ظاهَرُ": 1, "فِدْيَة": 1, "كَفّارَة": 1, "تُنكِحُ": 1, "يَسْتَنكِحَ": 1,
         "كاتِبُ": 1, "سُكارَى": 1, "جُنُب": 1, "تَيَمَّمُ": 1, "غائِط": 1}
FAITHFUL = {"مُؤْمِن", "صابِر", "صَبَرَ", "صَبْر", "مُتَّقي", "اتَّقَى", "مُحْسِن", "صالِحَة", "خاشِع"}
# formulas of self-description, matched on normalized unvocalized text
FORMULAS = [("لا اله الا هو", "lā ilāha illā huwa"), ("هو الذي", "huwa alladhī"), ("هو الله", "huwa Allāh"),
            ("تبرك", "tabāraka"), ("سبحن", "subḥāna"), ("سبح ", "sabbaḥa"), ("يسبح", "yusabbiḥu"),
            ("له الملك", "lahu al-mulk"), ("له الحمد", "lahu al-ḥamd"), ("الاسماء الحسنى", "al-asmāʾ al-ḥusnā"),
            ("رب العلمين", "rabb al-ʿālamīn"), ("الحمد لله", "al-ḥamdu lillāh"),
            ("الله نور", "Allāhu nūr"), ("ليس كمثله", "laysa ka-mithlihi shayʾ"), ("الحي القيوم", "al-ḥayy al-qayyūm")]
RARE = {"lā ilāha illā huwa", "Allāhu nūr", "laysa ka-mithlihi shayʾ", "al-ḥayy al-qayyūm", "al-asmāʾ al-ḥusnā",
        "huwa Allāh", "tabāraka"}
RARE_FORMULA, COMMON_FORMULA = 2.5, 1.2
LABEL = {"mercy": "Mercy", "reward": "Reward", "names": "Names & qualities"}

MIN_WORDS, MAX_WORDS, MAX_VERSES = 45, 140, 9
SEED_MIN = 1.6          # an ayah must weigh this much to seed a passage
PASS_MIN = 0.36         # passage score (weight / sqrt(words)) to be kept


def norm(t):
    t = "".join(ch for ch in unicodedata.normalize("NFD", t) if not unicodedata.combining(ch))
    for a, b in (("ٱ", "ا"), ("آ", "ا"), ("أ", "ا"), ("إ", "ا"), ("‏", ""), ("ٓ", "")):
        t = t.replace(a, b)
    return " " + re.sub(r"\s+", " ", t).strip() + " "


def load(c):
    ayahs = c.execute("""select a.id, a.surah, a.number, a.ruku, t.unvocalized from ayah a
        join ayah_text t on t.ayah_id=a.id join edition e on e.id=t.edition_id and e.slug='uthmani-hafs'
        order by a.id""").fetchall()
    words = defaultdict(list)
    for aid, pos, lemma in c.execute("select ayah_id, position, lemma from word order by ayah_id, position"):
        words[aid].append(lemma)
    out = []
    for aid, s, n, ruku, unv in ayahs:
        lem = words[aid]
        nw = len(lem)
        m = r = p = 0.0
        hits = {"mercy": Counter(), "reward": Counter(), "names": Counter()}
        faithful = 0
        legal = 0.0
        legal_verse = any(l in LEGAL for l in lem)
        for i, l in enumerate(lem):
            if not l:
                continue
            fawasil_formula = nw > 22 and i >= nw - 3 and l in NAMES and legal_verse   # "…God is forgiving, merciful" closing a long verse
            k = .4 if fawasil_formula else 1.0
            if l in MERCY:
                m += MERCY[l] * k; hits["mercy"][l] += 1
            if l in REWARD:
                r += REWARD[l]; hits["reward"][l] += 1
            if l in NAMES:
                hits["names"][l] += 1
            if l in PUNISH:
                p += PUNISH[l]
            if l in LEGAL:
                legal += LEGAL[l]
            if l in FAITHFUL:
                faithful += 1
        names_w = sum(.5 * min(v, 2) for v in hits["names"].values()) * (.4 if legal_verse else .8 if nw > 30 else 1)
        t = norm(unv)
        formulas = [label for pat, label in FORMULAS if pat in t]
        names_w += sum(RARE_FORMULA if f in RARE else COMMON_FORMULA for f in formulas)
        if r and faithful:
            r *= 1.25
        w = m + r + names_w - .3 * p - .8 * legal
        out.append(dict(id=aid, surah=s, n=n, ruku=ruku, words=nw, m=m, r=r, names=names_w, p=p, w=w,
                        hits=hits, formulas=formulas))
    return out


def scan(c, taken=()):
    """Densest non-overlapping windows. Every run of 3-9 verses inside one surah
    that reads as a unit (at least 25 words, or at least 5 short verses, at most
    MAX_WORDS) is scored by theme weight per √word; the best windows are taken
    greedily, so each hot spot yields its single best framing."""
    A = load(c)
    blocked = set()
    for s, a, b in taken:                      # hand-picked passages, already proposed
        for i, x in enumerate(A):
            if x["surah"] == s and a - 1 <= x["n"] <= b + 1:
                blocked.add(i)
    cands = []
    for lo in range(len(A)):
        words = total = 0.0
        best = lo
        for hi in range(lo, min(lo + MAX_VERSES, len(A))):
            if A[hi]["surah"] != A[lo]["surah"]:
                break
            words += A[hi]["words"]; total += A[hi]["w"]
            if A[hi]["w"] > A[best]["w"]:
                best = hi
            if words > MAX_WORDS and hi > lo:
                break
            nv = hi - lo + 1
            whole = A[lo]["n"] == 1 and (hi + 1 == len(A) or A[hi + 1]["surah"] != A[lo]["surah"])
            if not whole and (nv < 3 or not (words >= 25 or nv >= 5)):
                continue
            score = total / math.sqrt(max(words, 25))
            if A[hi]["ruku"] != A[lo]["ruku"]:
                score *= .92                   # crossing a traditional section break
            first = A[lo]["n"] == 1
            last = hi + 1 == len(A) or A[hi + 1]["surah"] != A[lo]["surah"]
            if (best == lo and not first) or (best == hi and not last):
                score *= .9                    # the strongest verse should have context on both sides
            cands.append((score, lo, hi))
    cands.sort(reverse=True)
    passages, used = [], set(blocked)
    for score, lo, hi in cands:
        if score < PASS_MIN:
            break
        if any(j in used for j in range(lo, hi + 1)):
            continue
        # a short surah taken almost whole is read whole
        first = next(i for i in range(lo, -1, -1) if i == 0 or A[i - 1]["surah"] != A[lo]["surah"])
        last = next(i for i in range(hi, len(A)) if i + 1 == len(A) or A[i + 1]["surah"] != A[lo]["surah"])
        if (last - first + 1 <= MAX_VERSES + 3 and (lo - first) + (last - hi) <= 2
                and not any(j in used for j in range(first, last + 1))):
            lo, hi = first, last
        used.update(range(lo, hi + 1))
        span = A[lo:hi + 1]
        heart = max(span, key=lambda x: x["w"])
        theme_w = {"mercy": sum(x["m"] for x in span), "reward": sum(x["r"] for x in span),
                   "names": sum(x["names"] for x in span)}
        top = max(theme_w.values())
        themes = [k for k in ("mercy", "reward", "names") if theme_w[k] >= max(1.0, .45 * top)] or \
                 [max(theme_w, key=theme_w.get)]
        hits = {k: Counter() for k in theme_w}
        for x in span:
            for k in hits:
                hits[k].update(x["hits"][k])
        formulas = sorted({f for x in span for f in x["formulas"]})
        passages.append(dict(surah=span[0]["surah"], frm=span[0]["n"], to=span[-1]["n"], heart=heart["n"],
                             score=round(score, 3), themes=themes, words=int(sum(x["words"] for x in span)),
                             hits={k: [[l, n] for l, n in hits[k].most_common(6)] for k in hits},
                             formulas=formulas, punish=round(sum(x["p"] for x in span), 1)))
    passages.sort(key=lambda p: (p["surah"], p["frm"]))
    return passages


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from passages import PASSAGES
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    P = scan(c, [(s, a, b) for s, a, b, *_ in PASSAGES])
    th = Counter(t for p in P for t in p["themes"])
    print(len(P), "passages;", dict(th), "; verses:", sum(p["to"] - p["frm"] + 1 for p in P))
    print("by surah:", len({p["surah"] for p in P}), "surahs")
    for p in sorted(P, key=lambda p: -p["score"])[: int(sys.argv[1]) if len(sys.argv) > 1 else 25]:
        print(f'{p["score"]:.2f} Q{p["surah"]}:{p["frm"]}-{p["to"]} heart {p["heart"]} {p["themes"]} {p["formulas"][:3]} '
              f'{[l for l,_ in p["hits"]["mercy"][:3]]} {[l for l,_ in p["hits"]["reward"][:3]]} {[l for l,_ in p["hits"]["names"][:4]]}')
