# Muṣḥaf viewer

A small illuminated muṣḥaf with two tabs:

- **Selections**: passages proposed for you, in the order of the Book. Tick **Keep** to move one into your repository.
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
