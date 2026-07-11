"""Load the explicitly fictional development relationship fixture."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from palnavi.domain.breeding import BreedingRelationship, SpeciesId


@dataclass(frozen=True, slots=True)
class BreedingDataset:
    dataset_id: str
    schema_version: int
    game_data_version: str
    relationships: tuple[BreedingRelationship, ...]


def synthetic_fixture_path() -> Path:
    repository_root = Path(__file__).resolve().parents[4]
    return repository_root / "samples" / "synthetic-breeding-data.json"


def load_synthetic_dataset(path: Path | None = None) -> BreedingDataset:
    fixture_path = path or synthetic_fixture_path()
    raw = cast(dict[str, Any], json.loads(fixture_path.read_text(encoding="utf-8")))
    if raw.get("synthetic") is not True:
        raise ValueError("fixture must be explicitly marked synthetic")

    relationship_rows = cast(list[dict[str, str]], raw["relationships"])
    relationships = tuple(
        BreedingRelationship(
            parent_a=SpeciesId(row["parent_a"]),
            parent_b=SpeciesId(row["parent_b"]),
            child=SpeciesId(row["child"]),
        )
        for row in relationship_rows
    )
    return BreedingDataset(
        dataset_id=str(raw["dataset_id"]),
        schema_version=int(raw["schema_version"]),
        game_data_version=str(raw["game_data_version"]),
        relationships=relationships,
    )
