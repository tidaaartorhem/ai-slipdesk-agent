"""Load SlipDesk's committed data (data/raw/*.json)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"


def _load(name: str):
    with open(RAW / name, encoding="utf-8") as f:
        return json.load(f)


def load_queue() -> dict:
    return _load("queue.json")


def load_config() -> dict:
    return _load("scoring-config.json")


def load_golden() -> dict:
    return _load("golden_set.json")


def load_corpus() -> dict:
    return _load("corpus_stats.json")


def load_vectors() -> dict:
    return _load("test-vectors.json")
