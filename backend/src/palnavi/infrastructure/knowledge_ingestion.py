"""Deterministic validation, identity, and Markdown chunking for knowledge documents."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from urllib.parse import urlsplit

from palnavi.domain.knowledge import (
    KnowledgeChunk,
    KnowledgeChunkId,
    KnowledgeClassification,
    KnowledgeContentIdentity,
    KnowledgeDocument,
    KnowledgeDocumentId,
    KnowledgeDocumentInput,
    KnowledgeDocumentMetadata,
    KnowledgeEvidenceQuality,
    KnowledgeImportFailure,
    KnowledgeImportOutcome,
    KnowledgeImportSuccess,
    KnowledgeSourceType,
    KnowledgeValidationCode,
    KnowledgeValidationIssue,
    KnowledgeValidationStatus,
    KnowledgeVersionScopeKind,
    LanguageIdentifier,
)

_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class KnowledgeDocumentImporter:
    max_chunk_chars: int = 500

    def __post_init__(self) -> None:
        if not 100 <= self.max_chunk_chars <= 4000:
            raise ValueError("knowledge chunk size must be between 100 and 4000")

    def import_document(self, source: KnowledgeDocumentInput) -> KnowledgeImportOutcome:
        issues = _validate_source(source)
        normalized_content = normalize_knowledge_content(source.content)
        if not normalized_content:
            issues.append(
                _issue(
                    KnowledgeValidationCode.BLANK_CONTENT,
                    "content",
                    "knowledge document content must not be blank",
                )
            )

        document_id: KnowledgeDocumentId | None = None
        language: LanguageIdentifier | None = None
        try:
            document_id = KnowledgeDocumentId(source.document_id)
        except ValueError:
            issues.append(
                _issue(
                    KnowledgeValidationCode.INVALID_DOCUMENT_ID,
                    "document_id",
                    "knowledge document identifier has an invalid format",
                )
            )
        try:
            language = LanguageIdentifier(source.language)
        except ValueError:
            issues.append(
                _issue(
                    KnowledgeValidationCode.INVALID_LANGUAGE,
                    "language",
                    "knowledge language identifier has an invalid format",
                )
            )

        digest = (
            knowledge_content_sha256(source, normalized_content, language)
            if language is not None
            else "0" * 64
        )
        if _SHA256_PATTERN.fullmatch(source.declared_content_sha256) is None:
            issues.append(
                _issue(
                    KnowledgeValidationCode.INVALID_CONTENT_IDENTITY,
                    "declared_content_sha256",
                    "declared content identity must be a lowercase SHA-256 digest",
                )
            )
        elif source.declared_content_sha256 != digest:
            issues.append(
                _issue(
                    KnowledgeValidationCode.CONTENT_IDENTITY_MISMATCH,
                    "declared_content_sha256",
                    "declared content identity does not match canonical document content",
                )
            )

        if issues or document_id is None or language is None:
            return KnowledgeImportFailure(tuple(issues))

        chunks = _chunk_markdown(
            document_id=document_id,
            digest=digest,
            content=normalized_content,
            max_chars=self.max_chunk_chars,
        )
        if not chunks:
            return KnowledgeImportFailure(
                (
                    _issue(
                        KnowledgeValidationCode.BLANK_CONTENT,
                        "content",
                        "knowledge document must contain retrievable text",
                    ),
                )
            )
        return KnowledgeImportSuccess(
            KnowledgeDocument(
                metadata=KnowledgeDocumentMetadata(
                    document_id=document_id,
                    title=source.title.strip(),
                    language=language,
                    classification=source.classification,
                    game_version_scope=source.game_version_scope,
                    provenance=source.provenance,
                    imported_at=source.imported_at,
                    schema_version=source.schema_version,
                    importer_version=source.importer_version.strip(),
                    validation_status=KnowledgeValidationStatus.VALIDATED,
                    content_identity=KnowledgeContentIdentity("sha256", digest),
                ),
                normalized_content=normalized_content,
                chunks=chunks,
            )
        )


def normalize_knowledge_content(content: str) -> str:
    normalized = unicodedata.normalize("NFC", content.replace("\r\n", "\n").replace("\r", "\n"))
    lines = [line.rstrip() for line in normalized.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def knowledge_content_sha256(
    source: KnowledgeDocumentInput,
    normalized_content: str | None = None,
    language: LanguageIdentifier | None = None,
) -> str:
    content = (
        normalize_knowledge_content(source.content)
        if normalized_content is None
        else normalized_content
    )
    normalized_language = LanguageIdentifier(source.language) if language is None else language
    canonical = json.dumps(
        {
            "document_id": source.document_id,
            "title": source.title.strip(),
            "language": normalized_language.value,
            "classification": source.classification.value,
            "game_version_scope": {
                "kind": source.game_version_scope.kind.value,
                "value": source.game_version_scope.value,
            },
            "provenance": {
                "source_id": source.provenance.source_id,
                "source_type": source.provenance.source_type.value,
                "locator": source.provenance.locator,
                "retrieved_at": source.provenance.retrieved_at.isoformat(),
                "license_or_usage_note": source.provenance.license_or_usage_note,
                "evidence_quality": source.provenance.evidence_quality.value,
            },
            "imported_at": source.imported_at.isoformat(),
            "schema_version": source.schema_version,
            "importer_version": source.importer_version.strip(),
            "content": content,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validate_source(source: KnowledgeDocumentInput) -> list[KnowledgeValidationIssue]:
    issues: list[KnowledgeValidationIssue] = []
    if not source.title.strip() or len(source.title.strip()) > 200:
        issues.append(_issue(KnowledgeValidationCode.BLANK_TITLE, "title", "title is required"))
    if source.schema_version != 1:
        issues.append(
            _issue(
                KnowledgeValidationCode.UNSUPPORTED_SCHEMA_VERSION,
                "schema_version",
                "knowledge document schema version is unsupported",
            )
        )
    if not source.importer_version.strip() or len(source.importer_version) > 64:
        issues.append(
            _issue(
                KnowledgeValidationCode.INVALID_IMPORTER_VERSION,
                "importer_version",
                "knowledge importer version is required and bounded",
            )
        )
    if source.imported_at.tzinfo is None or source.imported_at.utcoffset() is None:
        issues.append(
            _issue(
                KnowledgeValidationCode.INVALID_TIMESTAMP,
                "imported_at",
                "knowledge import timestamp must include a timezone",
            )
        )
    provenance = source.provenance
    if (
        not provenance.source_id.strip()
        or len(provenance.source_id) > 64
        or not provenance.license_or_usage_note.strip()
        or len(provenance.license_or_usage_note) > 500
        or provenance.retrieved_at.tzinfo is None
        or provenance.retrieved_at.utcoffset() is None
    ):
        issues.append(
            _issue(
                KnowledgeValidationCode.INVALID_PROVENANCE,
                "provenance",
                "knowledge provenance fields and timezone-aware retrieval time are required",
            )
        )
    if source.classification is KnowledgeClassification.SYNTHETIC and (
        provenance.source_type is not KnowledgeSourceType.LOCAL_SYNTHETIC_FIXTURE
        or provenance.evidence_quality is not KnowledgeEvidenceQuality.SYNTHETIC_ONLY
    ):
        issues.append(
            _issue(
                KnowledgeValidationCode.INVALID_PROVENANCE,
                "provenance",
                "synthetic knowledge requires synthetic fixture provenance",
            )
        )
    if (
        source.game_version_scope.kind is KnowledgeVersionScopeKind.SYNTHETIC_TEST_ONLY
        and source.classification is not KnowledgeClassification.SYNTHETIC
    ):
        issues.append(
            _issue(
                KnowledgeValidationCode.INVALID_VERSION_SCOPE,
                "game_version_scope",
                "synthetic-only version scope requires synthetic classification",
            )
        )
    if not _safe_source_locator(provenance.locator):
        issues.append(
            _issue(
                KnowledgeValidationCode.UNSAFE_SOURCE_LOCATOR,
                "provenance.locator",
                "knowledge source locator is invalid or unsafe",
            )
        )
    return issues


def _safe_source_locator(locator: str) -> bool:
    if not locator.strip() or len(locator) > 500:
        return False
    if PurePosixPath(locator).is_absolute() or PureWindowsPath(locator).is_absolute():
        return False
    try:
        parsed = urlsplit(locator)
        _ = parsed.port
    except ValueError:
        return False
    if parsed.scheme == "file":
        return False
    if parsed.scheme:
        if parsed.username is not None or parsed.password is not None:
            return False
        if parsed.query or parsed.fragment:
            return False
    return True


def _chunk_markdown(
    *,
    document_id: KnowledgeDocumentId,
    digest: str,
    content: str,
    max_chars: int,
) -> tuple[KnowledgeChunk, ...]:
    sections: list[tuple[tuple[str, ...], str]] = []
    section_stack: list[str] = []
    body_lines: list[str] = []

    def flush() -> None:
        body = "\n".join(body_lines).strip()
        if body:
            sections.append((tuple(section_stack), body))
        body_lines.clear()

    for line in content.split("\n"):
        heading = _HEADING_PATTERN.fullmatch(line)
        if heading is None:
            body_lines.append(line)
            continue
        flush()
        level = len(heading.group(1))
        title = heading.group(2).strip()
        del section_stack[level - 1 :]
        while len(section_stack) < level - 1:
            section_stack.append("")
        section_stack.append(title)
    flush()

    chunks: list[KnowledgeChunk] = []
    for section_path, body in sections:
        for text in _bounded_text_parts(body, max_chars):
            order = len(chunks)
            chunks.append(
                KnowledgeChunk(
                    chunk_id=KnowledgeChunkId(f"{document_id.value}-{digest[:16]}-{order:04d}"),
                    document_id=document_id,
                    order=order,
                    section_path=tuple(item for item in section_path if item),
                    text=text,
                )
            )
    return tuple(chunks)


def _bounded_text_parts(text: str, max_chars: int) -> tuple[str, ...]:
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
    atomic: list[str] = []
    for paragraph in paragraphs:
        atomic.extend(_split_oversized_paragraph(paragraph, max_chars))

    parts: list[str] = []
    current = ""
    for item in atomic:
        candidate = item if not current else f"{current}\n\n{item}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                parts.append(current)
            current = item
    if current:
        parts.append(current)
    return tuple(parts)


def _split_oversized_paragraph(paragraph: str, max_chars: int) -> tuple[str, ...]:
    if len(paragraph) <= max_chars:
        return (paragraph,)
    words = paragraph.split()
    if len(words) <= 1:
        return tuple(
            paragraph[index : index + max_chars] for index in range(0, len(paragraph), max_chars)
        )
    parts: list[str] = []
    current = ""
    for word in words:
        if len(word) > max_chars:
            if current:
                parts.append(current)
                current = ""
            parts.extend(
                word[index : index + max_chars] for index in range(0, len(word), max_chars)
            )
            continue
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            parts.append(current)
            current = word
    if current:
        parts.append(current)
    return tuple(parts)


def _issue(
    code: KnowledgeValidationCode,
    field: str,
    message: str,
) -> KnowledgeValidationIssue:
    return KnowledgeValidationIssue(code=code, field=field, message=message)
