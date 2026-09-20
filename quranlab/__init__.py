"""quranlab — reproducible infrastructure for Quranic text research.

Layers (see docs/ARCHITECTURE.md):
  L0  data/raw/       immutable, content-addressed upstream bytes
  L1  data/quran.db   derived canonical store — a build artifact, never hand-edited
  L2  annotations/    stand-off annotation, referencing stable IDs
  L3  claims/         findings, each with the query that regenerates it
"""

__version__ = "0.1.0"
