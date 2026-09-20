# quranlab — reproducible infrastructure for Quranic text research.
#
# `make` from a clean checkout fetches the pinned sources, builds the database,
# checks every data invariant, and re-runs the claim ledger. If any of those
# fail, the build fails.

PY ?= python3

DB  := data/quran.db
# Everything the build READS. fields/*.toml belongs here because fields.load()
# resolves them into the database at build time: leaving them out meant editing
# a field definition did not trigger a rebuild, and the database went quietly
# stale against its own inputs. claims/*.toml are deliberately absent — they are
# run against the finished database, not consumed by the build.
SRC := $(wildcard quranlab/*.py) quranlab/schema.sql sources.lock.json \
       $(wildcard fields/*.toml)

# The database is a real file target, not a phony one: `make check` invokes it
# three times, and rebuilding a 165 MB database each time both wasted half a
# minute per invocation and left every export stale the moment it was made.
$(DB): $(SRC) | fetch
	$(PY) -m quranlab build

.PHONY: all fetch build verify claims test check clean distclean serve site portable stats help

all: check

fetch:                ## download pinned sources into data/raw
	$(PY) -m quranlab fetch

build: $(DB)          ## build data/quran.db

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

site: build           ## export the static showcase into site/
	$(PY) -m quranlab.export_site
	cp quranlab/site/tour.html site/index.html

portable: build       ## export the uploadable bundle into dist/
	$(PY) -m quranlab.export_portable

stats: build          ## summarize the database
	$(PY) -m quranlab stats

clean:                ## remove the database and the static export
	rm -f data/quran.db data/quran.db-wal data/quran.db-shm
	rm -rf site dist

distclean: clean      ## also remove fetched sources
	rm -rf data/raw

help:
	@grep -E '^[a-z]+:.*?##' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "};{printf "  %-10s %s\n", $$1, $$2}'
