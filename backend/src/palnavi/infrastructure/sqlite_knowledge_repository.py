"""Transactional SQLite storage with deterministic standard-library lexical retrieval."""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from collections import Counter
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from palnavi.domain.knowledge import (
    KnowledgeChunkId,
    KnowledgeCitation,
    KnowledgeClassification,
    KnowledgeDocument,
    KnowledgeDocumentId,
    KnowledgeEvidenceQuality,
    KnowledgeQuery,
    KnowledgeRepositoryFailure,
    KnowledgeRepositoryFailureKind,
    KnowledgeSearchOutcome,
    KnowledgeSearchResult,
    KnowledgeSearchSuccess,
    KnowledgeSourceType,
    KnowledgeStoreDisposition,
    KnowledgeStoreOutcome,
    KnowledgeStoreSuccess,
    KnowledgeValidationStatus,
    KnowledgeVersionScope,
    KnowledgeVersionScopeKind,
    LanguageIdentifier,
)

_SCHEMA_VERSION = 1
_TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class SQLiteKnowledgeRepository:
    database_path: Path = field(repr=False)
    _initialization_failed: bool = field(init=False, repr=False)

    def __post_init__(self) -> None:
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connect()) as connection, connection:
                _migrate(connection)
        except (OSError, sqlite3.Error, ValueError):
            object.__setattr__(self, "_initialization_failed", True)
        else:
            object.__setattr__(self, "_initialization_failed", False)

    def import_document(self, document: KnowledgeDocument) -> KnowledgeStoreOutcome:
        if self._initialization_failed:
            return _repository_failure("knowledge repository is unavailable")
        metadata = document.metadata
        try:
            with closing(self._connect()) as connection, connection:
                existing = connection.execute(
                    "SELECT content_digest FROM knowledge_documents WHERE document_id = ?",
                    (metadata.document_id.value,),
                ).fetchone()
                if (
                    existing is not None
                    and existing["content_digest"] == metadata.content_identity.digest
                ):
                    return KnowledgeStoreSuccess(
                        document_id=metadata.document_id,
                        content_identity=metadata.content_identity,
                        disposition=KnowledgeStoreDisposition.UNCHANGED,
                    )
                disposition = (
                    KnowledgeStoreDisposition.REPLACED
                    if existing is not None
                    else KnowledgeStoreDisposition.CREATED
                )
                connection.execute(
                    "DELETE FROM knowledge_documents WHERE document_id = ?",
                    (metadata.document_id.value,),
                )
                connection.execute(
                    """
                    INSERT INTO knowledge_documents (
                        document_id, title, language, classification, version_kind,
                        version_value, source_id, source_type, source_locator,
                        retrieved_at, license_note, evidence_quality, imported_at,
                        schema_version, importer_version, validation_status,
                        content_digest, normalized_content, active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        metadata.document_id.value,
                        metadata.title,
                        metadata.language.value,
                        metadata.classification.value,
                        metadata.game_version_scope.kind.value,
                        metadata.game_version_scope.value,
                        metadata.provenance.source_id,
                        metadata.provenance.source_type.value,
                        metadata.provenance.locator,
                        metadata.provenance.retrieved_at.isoformat(),
                        metadata.provenance.license_or_usage_note,
                        metadata.provenance.evidence_quality.value,
                        metadata.imported_at.isoformat(),
                        metadata.schema_version,
                        metadata.importer_version,
                        metadata.validation_status.value,
                        metadata.content_identity.digest,
                        document.normalized_content,
                    ),
                )
                connection.executemany(
                    """
                    INSERT INTO knowledge_chunks (
                        chunk_id, document_id, chunk_order, section_path, chunk_text
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            chunk.chunk_id.value,
                            chunk.document_id.value,
                            chunk.order,
                            json.dumps(
                                chunk.section_path, ensure_ascii=True, separators=(",", ":")
                            ),
                            chunk.text,
                        )
                        for chunk in document.chunks
                    ],
                )
            return KnowledgeStoreSuccess(
                document_id=metadata.document_id,
                content_identity=metadata.content_identity,
                disposition=disposition,
            )
        except (OSError, sqlite3.Error):
            return _repository_failure("knowledge document import failed")

    def search(self, query: KnowledgeQuery) -> KnowledgeSearchOutcome:
        if self._initialization_failed:
            return _repository_failure("knowledge repository is unavailable")
        query_tokens = _lexical_tokens(query.text)
        if not query_tokens:
            return KnowledgeSearchSuccess(())
        sql = """
            SELECT
                d.document_id, d.title, d.language, d.classification,
                d.version_kind, d.version_value, d.source_id, d.source_type,
                d.source_locator, d.retrieved_at, d.license_note,
                d.evidence_quality, c.chunk_id, c.chunk_order,
                c.section_path, c.chunk_text
            FROM knowledge_documents AS d
            JOIN knowledge_chunks AS c ON c.document_id = d.document_id
            WHERE d.active = 1 AND d.validation_status = ?
        """
        parameters: list[object] = [KnowledgeValidationStatus.VALIDATED.value]
        if query.language is not None:
            sql += " AND d.language = ?"
            parameters.append(query.language.value)
        if query.exact_game_version is not None:
            sql += " AND d.version_kind = ? AND d.version_value = ?"
            parameters.extend(
                [
                    KnowledgeVersionScopeKind.EXPLICIT_GAME_VERSION.value,
                    query.exact_game_version,
                ]
            )
        if query.synthetic_only:
            sql += " AND d.classification = ?"
            parameters.append(KnowledgeClassification.SYNTHETIC.value)
        try:
            with closing(self._connect()) as connection:
                rows = connection.execute(sql, parameters).fetchall()
            scored = [result for row in rows if (result := _scored_result(row, query_tokens))]
            scored.sort(
                key=lambda item: (
                    -item.score,
                    item.document_id.value,
                    item.chunk_id.value,
                )
            )
            return KnowledgeSearchSuccess(tuple(scored[: query.limit]))
        except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return _repository_failure("knowledge search failed")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def default_knowledge_database_path() -> Path:
    repository_root = Path(__file__).resolve().parents[4]
    return repository_root / ".local" / "knowledge.sqlite3"


def _migrate(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_schema_meta (
            singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
            schema_version INTEGER NOT NULL
        )
        """
    )
    row = connection.execute(
        "SELECT schema_version FROM knowledge_schema_meta WHERE singleton = 1"
    ).fetchone()
    if row is None:
        connection.execute(
            "INSERT INTO knowledge_schema_meta (singleton, schema_version) VALUES (1, 0)"
        )
        version = 0
    else:
        version = int(row["schema_version"])
    if version > _SCHEMA_VERSION:
        raise ValueError("knowledge database schema is newer than supported")
    if version == 0:
        connection.executescript(
            """
            CREATE TABLE knowledge_documents (
                document_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                language TEXT NOT NULL,
                classification TEXT NOT NULL,
                version_kind TEXT NOT NULL,
                version_value TEXT,
                source_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_locator TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                license_note TEXT NOT NULL,
                evidence_quality TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                schema_version INTEGER NOT NULL,
                importer_version TEXT NOT NULL,
                validation_status TEXT NOT NULL,
                content_digest TEXT NOT NULL,
                normalized_content TEXT NOT NULL,
                active INTEGER NOT NULL CHECK (active IN (0, 1))
            );
            CREATE TABLE knowledge_chunks (
                chunk_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL REFERENCES knowledge_documents(document_id)
                    ON DELETE CASCADE,
                chunk_order INTEGER NOT NULL,
                section_path TEXT NOT NULL,
                chunk_text TEXT NOT NULL,
                UNIQUE (document_id, chunk_order)
            );
            CREATE INDEX knowledge_documents_filters
                ON knowledge_documents(active, validation_status, language, classification,
                                       version_kind, version_value);
            CREATE INDEX knowledge_chunks_document ON knowledge_chunks(document_id);
            """
        )
        connection.execute(
            "UPDATE knowledge_schema_meta SET schema_version = ? WHERE singleton = 1",
            (_SCHEMA_VERSION,),
        )


def _scored_result(
    row: sqlite3.Row,
    query_tokens: tuple[str, ...],
) -> KnowledgeSearchResult | None:
    section_data = json.loads(str(row["section_path"]))
    if not isinstance(section_data, list) or not all(
        isinstance(item, str) for item in section_data
    ):
        raise ValueError("invalid stored section path")
    section_path = tuple(section_data)
    text_counts = Counter(_lexical_tokens(str(row["chunk_text"])))
    title_counts = Counter(_lexical_tokens(str(row["title"])))
    section_counts = Counter(_lexical_tokens(" ".join(section_path)))
    score = sum(
        text_counts[token] + (2 * title_counts[token]) + (1.5 * section_counts[token])
        for token in query_tokens
    )
    if score <= 0:
        return None
    document_id = KnowledgeDocumentId(str(row["document_id"]))
    chunk_id = KnowledgeChunkId(str(row["chunk_id"]))
    title = str(row["title"])
    provenance_type = KnowledgeSourceType(str(row["source_type"]))
    evidence_quality = KnowledgeEvidenceQuality(str(row["evidence_quality"]))
    # Enum conversion validates persisted values even though only citation-safe fields are returned.
    _ = (provenance_type, evidence_quality)
    citation = KnowledgeCitation(
        document_id=document_id,
        chunk_id=chunk_id,
        title=title,
        section_path=section_path,
        source_id=str(row["source_id"]),
        source_locator=str(row["source_locator"]),
        retrieved_at=datetime.fromisoformat(str(row["retrieved_at"])),
        license_or_usage_note=str(row["license_note"]),
    )
    return KnowledgeSearchResult(
        score=float(score),
        document_id=document_id,
        chunk_id=chunk_id,
        title=title,
        section_path=section_path,
        text=str(row["chunk_text"]),
        language=LanguageIdentifier(str(row["language"])),
        classification=KnowledgeClassification(str(row["classification"])),
        game_version_scope=KnowledgeVersionScope(
            kind=KnowledgeVersionScopeKind(str(row["version_kind"])),
            value=str(row["version_value"]) if row["version_value"] is not None else None,
        ),
        citation=citation,
    )


def _lexical_tokens(value: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return tuple(_TOKEN_PATTERN.findall(normalized))


def _repository_failure(message: str) -> KnowledgeRepositoryFailure:
    return KnowledgeRepositoryFailure(
        kind=KnowledgeRepositoryFailureKind.UNAVAILABLE,
        message=message,
    )
