from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DATASET_ROOT = REPOSITORY_ROOT / "datasets" / "palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47"


def _load(name: str) -> dict[str, Any]:
    value = json.loads((DATASET_ROOT / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _load_outcomes() -> list[dict[str, Any]]:
    manifest = _load("manifest.json")
    records: list[dict[str, Any]] = []
    for generated in manifest["generated_files"]:
        if generated["path"].startswith("breeding-outcomes/"):
            records.extend(_load(generated["path"])["records"])
    return records


def test_checked_in_dataset_passes_offline_validator() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(REPOSITORY_ROOT / "tools" / "build_palworld_dataset.py"),
            "--validate-only",
            "--output",
            str(DATASET_ROOT),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0
    assert "dataset valid:" in completed.stdout
    assert completed.stderr == ""


def test_manifest_binds_every_generated_machine_artifact() -> None:
    manifest = _load("manifest.json")

    assert manifest["dataset_id"] == "palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47"
    assert manifest["game_version_scope"] == {
        "source_snapshot": "v1.0.0",
        "independently_verified_compatible_patch": "v1.0.1",
        "compatibility_evidence": "secondary_community_audit",
        "compatibility_audited_at": "2026-07-17",
    }
    assert manifest["runtime_status"] == "stored_not_activated"

    for record in manifest["generated_files"]:
        value = (DATASET_ROOT / record["path"]).read_bytes()
        assert len(value) == record["bytes"]
        assert hashlib.sha256(value).hexdigest() == record["sha256"]


def test_normalized_pal_records_preserve_gaps_instead_of_inferring_them() -> None:
    records = _load("pals.json")["records"]

    assert len(records) == 299
    assert len({record["internal_id"] for record in records}) == 299
    assert {len(record["localized_names"]) for record in records} == {17}
    assert all(record["player_visible"] is None for record in records)
    assert all(record["elements"] is None for record in records)
    assert all(record["ranch_outputs"] is None for record in records)
    assert all(record["partner_skill_id"] is None for record in records)
    assert all(record["active_skill_ids"] is None for record in records)

    gumoss_flower = next(record for record in records if record["internal_id"] == "gumoss_flower")
    assert gumoss_flower["source_internal_name"] == "PlantSlime_Flower"
    assert gumoss_flower["is_variant"] is True


def test_all_outcomes_resolve_and_gender_directed_family_is_preserved() -> None:
    pal_ids = {record["internal_id"] for record in _load("pals.json")["records"]}
    outcomes = _load_outcomes()
    kinds = Counter(record["result_kind"] for record in outcomes)

    assert len(outcomes) == 44_851
    assert kinds == {
        "same_species": 299,
        "ordinary_power": 44_418,
        "fixed_special": 132,
        "gender_directed": 2,
    }
    assert all(
        {
            record["parent_1_internal_id"],
            record["parent_2_internal_id"],
            record["child_internal_id"],
        }
        <= pal_ids
        for record in outcomes
    )

    directed = [record for record in outcomes if record["result_kind"] == "gender_directed"]
    assert {
        (
            record["parent_1_internal_id"],
            record["parent_1_gender_constraint"],
            record["parent_2_internal_id"],
            record["parent_2_gender_constraint"],
            record["child_internal_id"],
        )
        for record in directed
    } == {
        ("katress", "female", "wixen", "male", "katress_ignis"),
        ("katress", "male", "wixen", "female", "wixen_noct"),
    }
