from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DATASET_ROOT = REPOSITORY_ROOT / "datasets" / ("palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47")
ENRICHMENT_ROOT = DATASET_ROOT / "enrichment"
ENRICHMENT_FIELDS = {
    "canonical_paldeck_member",
    "roster_class",
    "elements",
    "male_probability",
    "female_probability",
    "active_skill_learnset",
    "guaranteed_passive_skill_ids",
}


def _load(name: str) -> dict[str, Any]:
    value = json.loads((ENRICHMENT_ROOT / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _run_validator(dataset: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(REPOSITORY_ROOT / "tools" / "build_palworld_enrichment.py"),
            "--validate-only",
            "--dataset",
            str(dataset),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_checked_in_enrichment_passes_offline_validator() -> None:
    completed = _run_validator(DATASET_ROOT)

    assert completed.returncode == 0
    assert "enrichment valid:" in completed.stdout
    assert completed.stderr == ""


def test_manifest_binds_native_acquisition_extractor_and_every_output() -> None:
    manifest = _load("manifest.json")

    assert manifest["runtime_status"] == "stored_not_activated"
    assert manifest["native_acquisition"] == {
        "lock_path": "../native-acquisition-lock.json",
        "lock_sha256": "57e19c299c805995b3efa3b8b442f12040fdd2396d761d638677098388223307",
        "steam_app_id": "2394010",
        "steam_build_id": "24181105",
        "depot_id": "2394012",
        "manifest_id": "2167164727892555341",
        "pak_path": "Pal/Content/Paks/Pal-LinuxServer.pak",
        "pak_bytes": 4_797_040_962,
        "pak_steam_sha1": "b81698aff4e50356b9c2672ecadc59a2dd840ea3",
        "pak_sha256": "cad80fe15c38d74a795779fbab31f04bc2c15c37fb8a2188e4d89f3800fb0e68",
        "mappings": "not_provided_not_required",
    }
    assert manifest["extractor"]["commit"] == ("0385b3fd8bd757240d4a2c79615145122669abd5")
    assert manifest["extractor"]["patch_sha256"] == (
        "555a7ee1df68fbf120a2cac0582f562e4e4761cd35ccc08131bac89a1c93ce1e"
    )
    assert manifest["extractor"]["patched_source_sha256"] == {
        "src/PalworldAtlas.Extractor/AssetCatalog.cs": (
            "04d857ef49bb7ebcbe8323d0bce6287a3f411270d705c98d27dbdcc2d16b1011"
        ),
        "src/PalworldAtlas.Extractor/EnrichmentExtractor.cs": (
            "7156ff482bf11392eb9ad78736b61f6714a12b9e8c7e3494df2eda5bc0c49c09"
        ),
        "src/PalworldAtlas.Extractor/Program.cs": (
            "643d735c16135ccfff41b75cdec371b4aef69653f1be684168a082677b52b257"
        ),
    }
    assert manifest["counts"]["pal_records"] == 299
    assert manifest["counts"]["active_skill_entries"] == 2_356

    for generated in manifest["generated_files"]:
        value = (ENRICHMENT_ROOT / generated["path"]).read_bytes()
        assert len(value) == generated["bytes"]
        assert hashlib.sha256(value).hexdigest() == generated["sha256"]


def test_all_299_records_obey_the_enrichment_field_allowlist() -> None:
    enrichment = _load("pal-enrichment.json")
    records = enrichment["records_by_pal_internal_id"]

    assert enrichment["runtime_status"] == "stored_not_activated"
    assert len(records) == 299
    assert list(records) == sorted(records)
    assert all(set(fields) == ENRICHMENT_FIELDS for fields in records.values())
    assert all(1 <= len(fields["elements"]) <= 2 for fields in records.values())
    assert all(
        round(fields["male_probability"] + fields["female_probability"], 10) == 1
        for fields in records.values()
    )

    roster_counts = Counter(fields["roster_class"] for fields in records.values())
    assert roster_counts == {
        "canonical_paldeck": 287,
        "terraria_collaboration_entity": 11,
        "internal_duplicate_form": 1,
    }
    skill_entries = [
        entry
        for pal_id, fields in records.items()
        for entry in fields["active_skill_learnset"]
        if entry["pal_internal_id"] == pal_id
    ]
    assert len(skill_entries) == 2_356
    assert (
        len(
            {
                (entry["pal_internal_id"], entry["skill_id"], entry["level"])
                for entry in skill_entries
            }
        )
        == 2_356
    )


def test_native_source_rows_are_fully_accounted_and_content_addressed() -> None:
    native = _load("native-pal-fields.json")
    pal_rows = native["pal_source_rows"]
    skill_rows = native["active_skill_source_rows"]

    assert native["aliases"] == {}
    assert len(pal_rows) == 753
    assert Counter(row["join_status"] for row in pal_rows) == {
        "joined": 299,
        "excluded": 454,
    }
    assert len(skill_rows) == 5_772
    assert Counter(row["join_status"] for row in skill_rows) == {
        "joined": 2_356,
        "excluded": 3_416,
    }
    assert all(
        row["exclusion_reason"] is not None
        for row in [*pal_rows, *skill_rows]
        if row["join_status"] == "excluded"
    )
    assert all(len(row["source_row_sha256"]) == 64 for row in [*pal_rows, *skill_rows])


def test_palcalc_native_diff_is_explicit_and_has_no_silent_preference() -> None:
    diff = _load("palcalc-native-diff.json")

    assert diff["compared_records"] == 299
    assert diff["summary"] == {
        "comparisons": 598,
        "matches": 598,
        "differences": 0,
    }
    for record in diff["records"]:
        assert set(record["comparisons"]) == {
            "male_probability_percent",
            "guaranteed_passive_skill_ids",
        }
        for comparison in record["comparisons"].values():
            assert comparison["status"] == "match"
            assert comparison["palcalc"] == comparison["native"]


@pytest.mark.parametrize(
    "name",
    [
        "ATLAS-LICENSE.txt",
        "native-pal-fields.json",
        "pal-enrichment.json",
        "palcalc-native-diff.json",
        "roster-classification.json",
    ],
)
def test_offline_validator_fails_closed_for_output_tampering(
    tmp_path: Path,
    name: str,
) -> None:
    dataset = tmp_path / "dataset"
    shutil.copytree(ENRICHMENT_ROOT, dataset / "enrichment")
    shutil.copy2(DATASET_ROOT / "native-acquisition-lock.json", dataset)
    target = dataset / "enrichment" / name
    target.write_bytes(target.read_bytes() + b"\n")

    completed = _run_validator(dataset)

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert "enrichment validation failed:" in completed.stderr
    assert "/tmp/" not in completed.stderr


def test_offline_validator_fails_closed_for_manifest_tampering(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    shutil.copytree(ENRICHMENT_ROOT, dataset / "enrichment")
    shutil.copy2(DATASET_ROOT / "native-acquisition-lock.json", dataset)
    path = dataset / "enrichment" / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["runtime_status"] = "activated"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    completed = _run_validator(dataset)

    assert completed.returncode == 1
    assert "enrichment validation failed:" in completed.stderr


def test_runtime_source_does_not_import_or_reference_the_enrichment() -> None:
    runtime_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((REPOSITORY_ROOT / "backend" / "src").rglob("*.py"))
    ).casefold()

    assert "pal-enrichment.json" not in runtime_source
    assert "native-pal-fields.json" not in runtime_source
    assert "deterministic-enrichment-v1" not in runtime_source


def test_atlas_patch_modified_hunks_retain_context() -> None:
    patch = (REPOSITORY_ROOT / "tools" / "palworld_atlas_enrichment.patch").read_text(
        encoding="utf-8"
    )
    modified_sections = [
        section for section in patch.split("diff --git ")[1:] if "\nnew file mode " not in section
    ]

    assert len(modified_sections) == 2
    for section in modified_sections:
        hunks = section.split("\n@@ ")[1:]
        assert hunks
        for hunk in hunks:
            body = hunk.split("\n", 1)[1]
            assert any(line.startswith(" ") for line in body.splitlines())
