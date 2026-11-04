# Muṣḥaf viewer

A small illuminated muṣḥaf with two tabs. Each tab has an index (search by surah, by reference such as `39:53`, or by any word in the translation; filter by theme and, under Selections, by strength) and a reader that shows one passage at a time with Previous/Next and the ← → keys.

- **Selections**: seven hand-picked passages plus every passage the whole-text scan found (`scan.py`), in the order of the Book. Tick **Keep** to move one into your repository.
- **My Repository**: your kept passages, placed by their position in the Book. Kept passages from the same surah whose ranges overlap or touch are joined into one continuous reading.
  - **Remove from repository** (tap twice to confirm): a proposed passage goes back to Selections, and one you added yourself is deleted.
  - **Add a passage**: pick any surah and verse range, with an optional title and note.
  - **Export backup / Import backup**: a JSON file of everything, which moves your repository between copies.

The page carries the whole Qur'an (Arabic and Yusuf Ali), about 2 MB. Every passage is rebuilt from that canonical text, so stored and imported data only contribute ranges, titles and notes.

**One file, two homes.** The same `mushaf.html` works:
- on claude.ai, where it saves to the artifact's store in your account;
- opened directly as a local file, offline, where it saves in that browser's storage (back it up with Export) and starts with the proposals built into it.

The published page is the claude.ai artifact <https://claude.ai/artifact/6r76bacwitFQg26BMWp8Xz>.
The passages and your Keep choices are **not** in this repo. They live in that artifact's database, in the `passages` collection, and only the owner can write to it.

```
make mushaf        # writes mushaf/out/mushaf.html and mushaf/out/seed/*.json
```

- `passages.py` holds the proposed passages: range, core verse, titles and notes.
- `build.py` reads the text from `data/quran.db`. It writes the page, with the full text and the proposals embedded, plus one seed document per passage for the claude.ai store, with ids like `q055-001-013`.
- To propose new passages, add them to `passages.py`, rebuild, and write only the new seed documents into the store. Re-seeding an existing document would reset its `kept` flag.

Fonts: Amiri Quran comes from the pinned `fonts` source. Reem Kufi (OFL, `fonts/`) was taken from google/fonts at the same commit.

## The scan

`scan.py` scores every verse for the reader's three themes from the morphology:
- **mercy**: raḥma, maghfira, ʿafw, tawba, raʾfa, wudd and related lemmas;
- **reward**: the Garden and its furniture, ajr, fawz, riḍwān, bushrā;
- **names & qualities**: divine-attribute lemmas, plus formulas of self-description read off the text, such as *lā ilāha illā huwa*, *huwa Allāh*, *tabāraka*, *Allāhu nūr* and *laysa ka-mithlihi shayʾ*.

It then takes the densest non-overlapping windows of 3 to 9 verses, so each passage keeps its context.

The weights are written-down judgement. Legal and battle vocabulary is penalised, because those passages close on "forgiving, merciful" but are rulings. The epithet that ends a long legal verse is discounted. Punishment counts mildly against a passage.

Run `python3 mushaf/scan.py` for a summary. Stars are score terciles (top 25%, next 40%, rest). The scan reads words, not meaning, so one-star picks deserve a sceptical eye.
