from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = REPOSITORY_ROOT / "tools" / "lock_palworld_server_acquisition.py"
LOCK_PATH = (
    REPOSITORY_ROOT
    / "datasets"
    / "palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47"
    / "native-acquisition-lock.json"
)


def _load_tool() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "lock_palworld_server_acquisition",
        TOOL_PATH,
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _load_lock() -> dict[str, Any]:
    value = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_checked_in_native_acquisition_lock_passes_offline_validator() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL_PATH),
            "--validate-only",
            "--lock",
            str(LOCK_PATH),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0
    assert completed.stdout == "native acquisition lock valid: native-acquisition-lock.json\n"
    assert completed.stderr == ""


def test_native_acquisition_lock_is_sanitized_and_not_runtime_active() -> None:
    lock = _load_lock()
    serialized = LOCK_PATH.read_text(encoding="utf-8").lower()

    assert lock["scope"]["runtime_status"] == "acquisition_provenance_only_not_activated"
    assert lock["extractor"]["probe"]["mappings"] == {
        "status": "mappings_not_required",
        "identity": None,
        "sha256": None,
    }
    assert lock["extractor"]["probe"]["production_gate_passed"] is True
    assert lock["steam"]["selected_file"]["local_sha256"] == (
        "cad80fe15c38d74a795779fbab31f04bc2c15c37fb8a2188e4d89f3800fb0e68"
    )
    assert "/tmp/" not in serialized
    assert "/workspace/" not in serialized
    assert "credential" not in serialized
    assert "access_token" not in serialized


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("steam", "build_id"), "future-build"),
        (("steam", "selected_file", "size_bytes"), 1),
        (("extractor", "commit"), "0" * 40),
        (("extractor", "probe", "production_gate_passed"), False),
        (("extractor", "probe", "mappings", "status"), "unknown"),
        (("integrity", "generated_record_sha256"), "0" * 64),
    ],
)
def test_validator_fails_closed_for_identity_or_probe_tampering(
    path: tuple[str, ...],
    replacement: object,
) -> None:
    tool = _load_tool()
    lock = copy.deepcopy(_load_lock())
    target: dict[str, Any] = lock
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement

    with pytest.raises(tool.AcquisitionError):
        tool.validate_lock(lock)


def test_validator_rejects_rehashed_but_unreviewed_probe_evidence() -> None:
    tool = _load_tool()
    lock = copy.deepcopy(_load_lock())
    probe = lock["extractor"]["probe"]
    probe["tables"][0]["row_count"] += 1
    probe_without_hash = {key: value for key, value in probe.items() if key != "record_sha256"}
    probe["record_sha256"] = tool._record_hash(probe_without_hash)
    dependency_lock = lock["extractor"]["dependency_lock"]
    lock["integrity"]["source_record_sha256"] = tool._record_hash(
        {
            "manifest": lock["steam"]["manifest"],
            "selected_file_sha256": lock["steam"]["selected_file"]["local_sha256"],
            "atlas_dependency_lock": dependency_lock,
            "probe_record_sha256": probe["record_sha256"],
        }
    )
    lock_without_integrity = {key: value for key, value in lock.items() if key != "integrity"}
    lock["integrity"]["generated_record_sha256"] = tool._record_hash(lock_without_integrity)

    with pytest.raises(
        tool.AcquisitionError,
        match="probe evidence is not the reviewed result",
    ):
        tool.validate_lock(lock)


def test_lock_serialization_is_byte_deterministic() -> None:
    tool = _load_tool()
    lock = _load_lock()

    assert tool._pretty_bytes(lock) == tool._pretty_bytes(copy.deepcopy(lock))
    assert tool._record_hash(lock) == tool._record_hash(copy.deepcopy(lock))


def test_generation_commands_pin_manifest_and_omit_mappings() -> None:
    source = TOOL_PATH.read_text(encoding="utf-8")

    assert '"-manifest",\n            MANIFEST_ID' in source
    assert '"-filelist"' in source
    assert '"--build-id",\n            BUILD_ID' in source
    assert '"--mappings"' not in source
    assert '"-manifest",\n            "latest"' not in source
    assert "optional unpinned Oodle binary was unavailable" in source
