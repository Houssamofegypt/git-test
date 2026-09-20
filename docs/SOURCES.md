# Sources and provenance

Every byte ingested is pinned to a commit and a SHA-256 in `sources.lock.json`,
and every derived row in the database traces back to a row in the `source`
table. `quranlab.fetch.read_source` re-verifies the digest on every read, so
nothing reaches the builder unchecked.

## What is ingested

| Source | Pinned at | Provides |
|---|---|---|
| [`fawazahmed0/quran-api`](https://github.com/fawazahmed0/quran-api) | `47ca096b` | 10 Arabic editions, 1 English translation, verse metadata |
| [`mustafa0x/quran-morphology`](https://github.com/mustafa0x/quran-morphology) | `8f38b390` | 130,030 morphological segments over 77,429 words |

### Editions

`uthmani-hafs` is the reference edition — the word spine is aligned to it.

| slug | riwāyah | orthography |
|---|---|---|
| `uthmani-hafs` | Ḥafṣ ʿan ʿĀṣim | KFGQPC Uthmani |
| `shuba` | Shuʿba ʿan ʿĀṣim | Uthmani |
| `warsh` | Warsh ʿan Nāfiʿ | Uthmani |
| `qalun` | Qālūn ʿan Nāfiʿ | Uthmani |
| `duri` | al-Dūrī ʿan Abī ʿAmr | Uthmani |
| `susi` | al-Sūsī ʿan Abī ʿAmr | Uthmani |
| `bazzi` | al-Bazzī ʿan Ibn Kathīr | Uthmani |
| `qunbul` | Qunbul ʿan Ibn Kathīr | Uthmani |
| `imlaei-simple` | Ḥafṣ | modern imlāʾī |
| `indopak` | Ḥafṣ | Indo-Pak |
| `en-yusufali` | — | English translation |

## On trusting an aggregator

`fawazahmed0/quran-api` is a mirror, not an authority. The Arabic texts
originate with [Tanzil.net](https://tanzil.net) and the King Fahd Glorious
Quran Printing Complex, which are the authorities; the aggregator is used here
because it is the reachable, pinnable form of them.

We do not take that on faith. Every edition is cross-checked against every
other during the build, at the rasm rung. The check that matters is
`claims/0003-riwayah-tree.toml`: the consonantal distances between the nine
riwāyāt reproduce the known transmission tree exactly — each riwāyah's nearest
neighbour is its sibling from the same qāriʾ. A corrupted or mislabelled
edition would not do that. It is a weaker guarantee than collating against a
printed muṣḥaf, and it is stated as such; anyone publishing on the basis of a
specific reading should verify that reading against a primary edition.

The morphology fork applies documented corrections to Quranic Arabic Corpus
v0.4 — root and lemma fixes, retagging, Buckwalter-to-Arabic re-rendering. It
is therefore *not* byte-identical to the corpus release. That divergence is
deliberate and recorded in `sources.toml`; anything depending on corpus v0.4
exactly should ingest v0.4 as a separate source rather than assume this one
matches it.

## Licensing

- **Quranic text**: Tanzil.net and KFGQPC texts are distributed for free
  non-commercial use, on condition that the text is not modified and the
  copyright notice is preserved. `quranlab` never modifies the raw layer, and
  the normalization ladder is stored as derived columns alongside — never in
  place of — the original.
- **Morphology**: derived from the Quranic Arabic Corpus (GNU GPL / CC BY-SA
  3.0, [corpus.quran.com](https://corpus.quran.com)), © Kais Dukes.
- **Aggregator**: Unlicense (public-domain dedication). This covers the
  aggregation, not the underlying texts.
- **This repository's code**: see the repository licence.

Because of these terms, `data/` is **not committed**. The repository carries the
pinned lock file; `make fetch` reconstitutes the raw layer. This also keeps the
repository small and makes the provenance chain auditable as a diff.

## Adding a source

1. Add a `[[source]]` block to `sources.toml` with a **pinned commit**. A source
   that cannot be pinned cannot be ingested.
2. `python -m quranlab fetch --relock` — downloads and records digests.
3. Write an ingest function in `build.py`.
4. Add invariants to `verify.py` that would catch it being wrong. This is the
   step people skip, and it is the one that pays.
5. `make check`.

## When upstream changes

A digest mismatch under a pinned commit fails the fetch loudly. That is either
upstream rewriting history or local corruption, and both need a human. Once
you know which, bump the commit in `sources.toml` and re-lock; the diff on
`sources.lock.json` is the audit trail, and any claim that no longer reproduces
will say so on the next `make check`.
