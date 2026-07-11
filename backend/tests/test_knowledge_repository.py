import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest
from test_knowledge_ingestion import source_document

from palnavi.domain.knowledge import (
    KnowledgeDocumentInput,
    KnowledgeImportSuccess,
    KnowledgeQuery,
    KnowledgeRepositoryFailure,
    KnowledgeSearchSuccess,
    KnowledgeStoreDisposition,
    LanguageIdentifier,
)
from palnavi.infrastructure.knowledge_ingestion import (
    KnowledgeDocumentImporter,
    knowledge_content_sha256,
)
from palnavi.infrastructure.sqlite_knowledge_repository import SQLiteKnowledgeRepository


def build_document(source: KnowledgeDocumentInput):
    outcome = KnowledgeDocumentImporter(max_chunk_chars=180).import_document(source)
    assert isinstance(outcome, KnowledgeImportSuccess)
    return outcome.document


def updated_source(source: KnowledgeDocumentInput, content: str) -> KnowledgeDocumentInput:
    changed = replace(source, content=content, declared_content_sha256="0" * 64)
    return replace(changed, declared_content_sha256=knowledge_content_sha256(changed))


def repository(tmp_path: Path) -> SQLiteKnowledgeRepository:
    return SQLiteKnowledgeRepository(tmp_path / "knowledge.sqlite3")


def test_identical_import_is_idempotent_and_updated_content_replaces_chunks(
    tmp_path: Path,
) -> None:
    store = repository(tmp_path)
    original = source_document(content="# Trail\n\nCrystal moss marks the quiet trail.")
    document = build_document(original)

    created = store.import_document(document)
    unchanged = store.import_document(document)
    replacement_source = updated_source(
        original,
        "# Trail\n\nAmber reeds replace every crystal moss marker.",
    )
    replaced = store.import_document(build_document(replacement_source))

    assert created.disposition is KnowledgeStoreDisposition.CREATED
    assert unchanged.disposition is KnowledgeStoreDisposition.UNCHANGED
    assert replaced.disposition is KnowledgeStoreDisposition.REPLACED
    old_results = store.search(KnowledgeQuery("quiet"))
    new_results = store.search(KnowledgeQuery("amber"))
    assert isinstance(old_results, KnowledgeSearchSuccess)
    assert old_results.results == ()
    assert isinstance(new_results, KnowledgeSearchSuccess)
    assert len(new_results.results) == 1


def test_retrieval_filters_version_and_language_and_returns_complete_citations(
    tmp_path: Path,
) -> None:
    store = repository(tmp_path)
    english = source_document(
        document_id="guide-english-v1",
        version="synthetic-1.0",
        language="en",
        content="# Routes\n\nCrystal moss points toward the cobalt arch.",
    )
    japanese = source_document(
        document_id="guide-japanese-v2",
        version="synthetic-2.0",
        language="ja",
        content="# Routes\n\nCrystal moss marks a fictional paper lantern route.",
        locator="project-authored://synthetic-corpus/guide-ja",
    )
    store.import_document(build_document(english))
    store.import_document(build_document(japanese))

    outcome = store.search(
        KnowledgeQuery(
            "crystal moss",
            language=LanguageIdentifier("en"),
            exact_game_version="synthetic-1.0",
            synthetic_only=True,
        )
    )

    assert isinstance(outcome, KnowledgeSearchSuccess)
    assert len(outcome.results) == 1
    result = outcome.results[0]
    assert result.document_id.value == "guide-english-v1"
    assert result.language.value == "en"
    assert result.game_version_scope.value == "synthetic-1.0"
    assert result.citation.document_id == result.document_id
    assert result.citation.chunk_id == result.chunk_id
    assert result.citation.title == result.title
    assert result.citation.section_path == result.section_path
    assert result.citation.source_id
    assert result.citation.source_locator.startswith("project-authored://")
    assert result.citation.license_or_usage_note


def test_score_ties_are_deterministic_and_limit_is_bounded(tmp_path: Path) -> None:
    store = repository(tmp_path)
    for document_id in ("guide-charlie", "guide-alpha", "guide-bravo"):
        source = source_document(
            document_id=document_id,
            content="# Equal\n\nLantern token appears once.",
            locator=f"project-authored://synthetic-corpus/{document_id}",
        )
        store.import_document(build_document(source))

    outcome = store.search(KnowledgeQuery("lantern", limit=2))

    assert isinstance(outcome, KnowledgeSearchSuccess)
    assert [item.document_id.value for item in outcome.results] == [
        "guide-alpha",
        "guide-bravo",
    ]
    with pytest.raises(ValueError):
        KnowledgeQuery("lantern", limit=21)


def test_no_match_and_invalid_or_inactive_documents_are_excluded(tmp_path: Path) -> None:
    path = tmp_path / "knowledge.sqlite3"
    store = SQLiteKnowledgeRepository(path)
    source = source_document(content="# Trail\n\nCrystal moss appears here.")
    store.import_document(build_document(source))

    no_match = store.search(KnowledgeQuery("nonexistent-token"))
    assert isinstance(no_match, KnowledgeSearchSuccess)
    assert no_match.results == ()

    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE knowledge_documents SET validation_status = 'invalid'")
    excluded = store.search(KnowledgeQuery("crystal"))
    assert isinstance(excluded, KnowledgeSearchSuccess)
    assert excluded.results == ()


def test_failed_replacement_rolls_back_without_mixing_stale_chunks(tmp_path: Path) -> None:
    path = tmp_path / "knowledge.sqlite3"
    store = SQLiteKnowledgeRepository(path)
    original = source_document(content="# Trail\n\nOriginal crystal marker remains active.")
    store.import_document(build_document(original))
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_replacement BEFORE INSERT ON knowledge_chunks
            WHEN NEW.chunk_text LIKE '%replacement%'
            BEGIN SELECT RAISE(ABORT, 'simulated failure'); END
            """
        )
    replacement = updated_source(
        original,
        "# Trail\n\nA replacement amber marker should fail transactionally.",
    )

    failure = store.import_document(build_document(replacement))
    old_result = store.search(KnowledgeQuery("original crystal"))
    new_result = store.search(KnowledgeQuery("replacement amber"))

    assert isinstance(failure, KnowledgeRepositoryFailure)
    assert "simulated" not in failure.message
    assert str(path) not in failure.message
    assert isinstance(old_result, KnowledgeSearchSuccess)
    assert len(old_result.results) == 1
    assert isinstance(new_result, KnowledgeSearchSuccess)
    assert new_result.results == ()


def test_schema_migration_is_idempotent_and_newer_schema_fails_safely(tmp_path: Path) -> None:
    path = tmp_path / "knowledge.sqlite3"
    first = SQLiteKnowledgeRepository(path)
    second = SQLiteKnowledgeRepository(path)
    assert isinstance(first.search(KnowledgeQuery("anything")), KnowledgeSearchSuccess)
    assert isinstance(second.search(KnowledgeQuery("anything")), KnowledgeSearchSuccess)
    with sqlite3.connect(path) as connection:
        version = connection.execute(
            "SELECT schema_version FROM knowledge_schema_meta WHERE singleton = 1"
        ).fetchone()[0]
    assert version == 1

    newer_path = tmp_path / "private-folder-name" / "future.sqlite3"
    newer_path.parent.mkdir()
    with sqlite3.connect(newer_path) as connection:
        connection.execute(
            "CREATE TABLE knowledge_schema_meta "
            "(singleton INTEGER PRIMARY KEY, schema_version INTEGER)"
        )
        connection.execute("INSERT INTO knowledge_schema_meta VALUES (1, 99)")
    unavailable = SQLiteKnowledgeRepository(newer_path)
    failure = unavailable.search(KnowledgeQuery("anything"))
    assert isinstance(failure, KnowledgeRepositoryFailure)
    assert str(newer_path) not in failure.message
    assert str(newer_path) not in repr(unavailable)


def test_database_schema_contains_no_model_credentials(tmp_path: Path) -> None:
    path = tmp_path / "knowledge.sqlite3"
    repository(tmp_path)
    with sqlite3.connect(path) as connection:
        schema = " ".join(
            row[0]
            for row in connection.execute(
                "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name"
            )
        ).lower()

    assert "api_key" not in schema
    assert "authorization" not in schema
    assert "model_provider" not in schema
