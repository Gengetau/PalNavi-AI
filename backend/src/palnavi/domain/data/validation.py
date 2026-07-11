"""Shared validation for raw relationships and deterministic content identity."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping

from palnavi.domain.breeding import BreedingRelationship, SpeciesId
from palnavi.domain.data.models import DatasetValidationCode, DatasetValidationIssue

DATASET_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
RELATIONSHIP_FIELDS = frozenset({"parent_a", "parent_b", "child"})


def relationship_content_sha256(
    relationships: tuple[BreedingRelationship, ...],
) -> str:
    """Return a stable digest independent of input row or parent ordering."""

    rows = [
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
    canonical = json.dumps(
        {"relationships": rows},
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
