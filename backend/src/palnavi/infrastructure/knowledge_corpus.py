"""Safe local loader for the project-authored synthetic knowledge corpus."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath

from palnavi.domain.knowledge import (
    KnowledgeClassification,
    KnowledgeDocumentInput,
    KnowledgeEvidenceQuality,
    KnowledgeImportFailure,
    KnowledgeImportOutcome,
    KnowledgeProvenance,
    KnowledgeSourceType,
    KnowledgeValidationCode,
    KnowledgeValidationIssue,
    KnowledgeVersionScope,
    KnowledgeVersionScopeKind,
)
from palnavi.infrastructure.knowledge_ingestion import KnowledgeDocumentImporter


@dataclass(frozen=True, slots=True)
class LocalSyntheticKnowledgeCorpus:
    root: Path = field(repr=False)
    importer: KnowledgeDocumentImporter = field(default_factory=KnowledgeDocumentImporter)

    def load(self) -> tuple[KnowledgeImportOutcome, ...]:
        try:
            resolved_root = self.root.resolve(strict=True)
            manifest = json.loads((resolved_root / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, RuntimeError, ValueError):
            return (_manifest_failure("synthetic knowledge manifest is unreadable or malformed"),)
        if not isinstance(manifest, Mapping):
            return (_manifest_failure("synthetic knowledge manifest must be an object"),)
        warning = manifest.get("synthetic_warning")
        records = manifest.get("documents")
        if (
            not isinstance(warning, str)
            or "not Palworld knowledge" not in warning
            or not isinstance(records, list)
            or not records
        ):
            return (_manifest_failure("synthetic knowledge manifest declaration is invalid"),)

        outcomes: list[KnowledgeImportOutcome] = []
        for index, record in enumerate(records):
            source = self._source_from_record(record, resolved_root)
            if source is None:
                outcomes.append(
                    _manifest_failure(f"synthetic knowledge document {index} is malformed")
                )
            else:
                outcomes.append(self.importer.import_document(source))
        return tuple(outcomes)

    def _source_from_record(
        self,
        record: object,
        resolved_root: Path,
    ) -> KnowledgeDocumentInput | None:
        if not isinstance(record, Mapping):
            return None
        try:
            content_file = record["content_file"]
            if (
                not isinstance(content_file, str)
                or not content_file.strip()
                or "\\" in content_file
            ):
                return None

            relative = PurePosixPath(content_file)
            windows_path = PureWindowsPath(content_file)
            components = content_file.split("/")
            if (
                relative.is_absolute()
                or windows_path.drive
                or windows_path.root
                or any(PureWindowsPath(component).anchor for component in components)
                or any(component in {".", ".."} for component in components)
                or relative.suffix.lower() not in {".md", ".txt"}
            ):
                return None

            candidate = resolved_root.joinpath(*relative.parts).resolve(strict=True)
            if not _is_path_within_resolved_root(candidate, resolved_root):
                return None
            content = candidate.read_text(encoding="utf-8")

            provenance = record["provenance"]
            version_scope = record["game_version_scope"]
            if not isinstance(provenance, Mapping) or not isinstance(version_scope, Mapping):
                return None
            classification = KnowledgeClassification(str(record["classification"]))
            if classification is not KnowledgeClassification.SYNTHETIC:
                return None
            return KnowledgeDocumentInput(
                document_id=str(record["document_id"]),
                title=str(record["title"]),
                language=str(record["language"]),
                classification=classification,
                game_version_scope=KnowledgeVersionScope(
                    KnowledgeVersionScopeKind(str(version_scope["kind"])),
                    str(version_scope["value"]) if version_scope.get("value") is not None else None,
                ),
                provenance=KnowledgeProvenance(
                    source_id=str(provenance["source_id"]),
                    source_type=KnowledgeSourceType(str(provenance["source_type"])),
                    locator=str(provenance["locator"]),
                    retrieved_at=datetime.fromisoformat(str(provenance["retrieved_at"])),
                    license_or_usage_note=str(provenance["license_or_usage_note"]),
                    evidence_quality=KnowledgeEvidenceQuality(str(provenance["evidence_quality"])),
                ),
                imported_at=datetime.fromisoformat(str(record["imported_at"])),
                schema_version=int(record["schema_version"]),
                importer_version=str(record["importer_version"]),
                content=content,
                declared_content_sha256=str(record["content_sha256"]),
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return None


def _is_path_within_resolved_root(candidate: Path, resolved_root: Path) -> bool:
    return candidate.is_relative_to(resolved_root)


def default_synthetic_knowledge_root() -> Path:
    repository_root = Path(__file__).resolve().parents[4]
    return repository_root / "samples" / "knowledge" / "synthetic-v1"


def _manifest_failure(message: str) -> KnowledgeImportFailure:
    return KnowledgeImportFailure(
        (
            KnowledgeValidationIssue(
                code=KnowledgeValidationCode.MALFORMED_MANIFEST,
                field="manifest",
                message=message,
            ),
        )
    )
