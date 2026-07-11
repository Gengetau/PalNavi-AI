"""Shared validation for raw relationships and deterministic content identity."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import datetime

from palnavi.domain.breeding import BreedingRelationship, SpeciesId
from palnavi.domain.data.models import (
    DatasetClassification,
    DatasetValidationCode,
    DatasetValidationIssue,
    GameVersionScope,
    ProvenanceRecord,
    ValidationStatus,
)

DATASET_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
RELATIONSHIP_FIELDS = frozenset({"parent_a", "parent_b", "child"})


def dataset_content_sha256(
    *,
    dataset_id: str,
    schema_version: int,
    classification: DatasetClassification,
    game_version_scope: GameVersionScope,
    created_at: datetime,
    importer_version: str,
    validation_status: ValidationStatus,
    provenance: tuple[ProvenanceRecord, ...],
    relationships: tuple[BreedingRelationship, ...],
) -> str:
    """Return a stable digest for canonical metadata, provenance, and relationships."""

    relationship_rows = [
        {
            "parent_a": relationship.parent_a.value,
            "parent_b": relationship.parent_b.value,
            "child": relationship.child.value,
        }
        for relationship in sorted(
            relationships,
            key=lambda item: (
                item.parent_a.value,
                item.parent_b.value,
                item.child.value,
            ),
        )
    ]
    provenance_rows = [
        {
            "source_id": record.source_id,
            "source_type": record.source_type.value,
            "locator": record.locator,
            "retrieved_at": record.retrieved_at.isoformat(),
            "license_or_usage_note": record.license_or_usage_note,
            "evidence_quality": record.evidence_quality.value,
        }
        for record in sorted(
            provenance,
            key=lambda item: (
                item.source_id,
                item.source_type.value,
                item.locator,
                item.retrieved_at.isoformat(),
                item.license_or_usage_note,
                item.evidence_quality.value,
            ),
        )
    ]
    canonical = json.dumps(
        {
            "dataset_id": dataset_id,
            "schema_version": schema_version,
            "classification": classification.value,
            "game_version_scope": {
                "kind": game_version_scope.kind.value,
                "value": game_version_scope.value,
            },
            "created_at": created_at.isoformat(),
            "importer_version": importer_version,
            "validation_status": validation_status.value,
            "provenance": provenance_rows,
            "relationships": relationship_rows,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def validate_relationship_rows(
    rows: object,
) -> tuple[tuple[BreedingRelationship, ...], tuple[DatasetValidationIssue, ...]]:
    """Validate raw relationship rows for imports and explicit API requests."""

    if not isinstance(rows, (list, tuple)):
        return (), (
            _issue(
                DatasetValidationCode.MALFORMED_RELATIONSHIP,
                "relationships",
                "relationships must be an array of relationship objects",
            ),
        )

    by_parents: dict[tuple[SpeciesId, SpeciesId], BreedingRelationship] = {}
    issues: list[DatasetValidationIssue] = []
    for index, raw_row in enumerate(rows):
        field = f"relationships[{index}]"
        if not isinstance(raw_row, Mapping) or set(raw_row) != RELATIONSHIP_FIELDS:
            issues.append(
                _issue(
                    DatasetValidationCode.MALFORMED_RELATIONSHIP,
                    field,
                    "relationship must contain exactly parent_a, parent_b, and child",
                )
            )
            continue

        raw_values = (raw_row.get("parent_a"), raw_row.get("parent_b"), raw_row.get("child"))
        if not all(isinstance(value, str) for value in raw_values):
            issues.append(
                _issue(
                    DatasetValidationCode.MALFORMED_RELATIONSHIP,
                    field,
                    "relationship identifiers must be strings",
                )
            )
            continue

        try:
            relationship = BreedingRelationship(
                parent_a=SpeciesId(str(raw_values[0])),
                parent_b=SpeciesId(str(raw_values[1])),
                child=SpeciesId(str(raw_values[2])),
            )
        except ValueError:
            issues.append(
                _issue(
                    DatasetValidationCode.INVALID_SPECIES_IDENTIFIER,
                    field,
                    "relationship contains an invalid stable species identifier",
                )
            )
            continue

        existing = by_parents.get(relationship.parent_key)
        if existing is not None and existing.child != relationship.child:
            issues.append(
                _issue(
                    DatasetValidationCode.CONFLICTING_RELATIONSHIP,
                    field,
                    "unordered parent pair maps to conflicting child identifiers",
                )
            )
            continue
        by_parents[relationship.parent_key] = relationship

    ordered = tuple(
        sorted(
            by_parents.values(),
            key=lambda item: (
                item.parent_a.value,
                item.parent_b.value,
                item.child.value,
            ),
        )
    )
    return ordered, tuple(issues)


def _issue(
    code: DatasetValidationCode,
    field: str,
    message: str,
) -> DatasetValidationIssue:
    return DatasetValidationIssue(code=code, field=field, message=message)
