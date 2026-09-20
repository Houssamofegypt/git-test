# quranlab — reproducible infrastructure for Quranic text research.
#
# `make` from a clean checkout fetches the pinned sources, builds the database,
# checks every data invariant, and re-runs the claim ledger. If any of those
# fail, the build fails.

PY ?= python3

.PHONY: all fetch build verify claims test check clean distclean serve stats help

all: check

fetch:                ## download pinned sources into data/raw
	$(PY) -m quranlab fetch

build: fetch          ## build data/quran.db
	$(PY) -m quranlab build

verify: build         ## assert every data invariant
	$(PY) -m quranlab verify

claims: build         ## re-run every recorded claim
	$(PY) -m quranlab claims

test:                 ## run the test suite
	$(PY) -m pytest tests/ -q

check: verify claims test  ## the full gate
	@echo "\nall green"

serve: build          ## local read-only web explorer
	$(PY) -m quranlab serve

stats: build          ## summarize the database
	$(PY) -m quranlab stats

clean:                ## remove the database, keep the raw sources
	rm -f data/quran.db data/quran.db-wal data/quran.db-shm

distclean: clean      ## also remove fetched sources
	rm -rf data/raw

help:
	@grep -E '^[a-z]+:.*?##' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "};{printf "  %-10s %s\n", $$1, $$2}'
