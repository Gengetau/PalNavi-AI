from dataclasses import replace
from datetime import UTC, datetime

import pytest

from palnavi.domain.knowledge import (
    KnowledgeClassification,
    KnowledgeDocumentInput,
    KnowledgeEvidenceQuality,
    KnowledgeImportFailure,
    KnowledgeImportSuccess,
    KnowledgeProvenance,
    KnowledgeSourceType,
    KnowledgeValidationCode,
    KnowledgeVersionScope,
    KnowledgeVersionScopeKind,
)
from palnavi.infrastructure.knowledge_ingestion import (
    KnowledgeDocumentImporter,
    knowledge_content_sha256,
)


def source_document(
    *,
    document_id: str = "synthetic-guide-a",
    language: str = "en-US",
    version: str = "synthetic-1.0",
    content: str = (
        "# Synthetic Navigation\n\n"
        "This fictional guide is not Palworld knowledge. Crystal moss marks the quiet trail.\n\n"
        "## Lantern Route\n\n"
        "Carry a paper lantern past the cobalt arch and follow the crystal moss."
    ),
    locator: str = "project-authored://synthetic-corpus/guide-a",
    license_note: str = "Project-authored synthetic fixture; test use only.",
    declared_digest: str = "0" * 64,
) -> KnowledgeDocumentInput:
    source = KnowledgeDocumentInput(
        document_id=document_id,
        title="Synthetic Navigation Guide",
        language=language,
        classification=KnowledgeClassification.SYNTHETIC,
        game_version_scope=KnowledgeVersionScope(
            KnowledgeVersionScopeKind.EXPLICIT_GAME_VERSION,
            version,
        ),
        provenance=KnowledgeProvenance(
            source_id="synthetic-source-a",
            source_type=KnowledgeSourceType.LOCAL_SYNTHETIC_FIXTURE,
            locator=locator,
            retrieved_at=datetime(2026, 7, 11, 0, 0, tzinfo=UTC),
            license_or_usage_note=license_note,
            evidence_quality=KnowledgeEvidenceQuality.SYNTHETIC_ONLY,
        ),
        imported_at=datetime(2026, 7, 11, 0, 5, tzinfo=UTC),
        schema_version=1,
        importer_version="knowledge-markdown-v1",
        content=content,
        declared_content_sha256=declared_digest,
    )
    try:
        digest = knowledge_content_sha256(source)
    except ValueError:
        return source
    return replace(source, declared_content_sha256=digest)


def imported_document(source: KnowledgeDocumentInput | None = None):
    outcome = KnowledgeDocumentImporter(max_chunk_chars=140).import_document(
        source or source_document()
    )
    assert isinstance(outcome, KnowledgeImportSuccess)
    return outcome.document


def test_ingestion_normalizes_content_and_produces_stable_bounded_chunks() -> None:
    first = imported_document()
    crlf_source = source_document(content=source_document().content.replace("\n", "\r\n"))
    second = imported_document(crlf_source)

    assert first.metadata.content_identity == second.metadata.content_identity
    assert first.normalized_content == second.normalized_content
    assert first.chunks == second.chunks
    assert [chunk.order for chunk in first.chunks] == list(range(len(first.chunks)))
    assert all(len(chunk.text) <= 140 for chunk in first.chunks)
    assert first.chunks[-1].section_path == ("Synthetic Navigation", "Lantern Route")


@pytest.mark.parametrize(
    ("source", "expected_code"),
    [
        (source_document(content=" \r\n\t"), KnowledgeValidationCode.BLANK_CONTENT),
        (source_document(document_id="Bad ID"), KnowledgeValidationCode.INVALID_DOCUMENT_ID),
        (source_document(language="invalid"), KnowledgeValidationCode.INVALID_LANGUAGE),
        (
            source_document(license_note=""),
            KnowledgeValidationCode.INVALID_PROVENANCE,
        ),
        (
            source_document(locator="https://user:password@example.test/guide"),
            KnowledgeValidationCode.UNSAFE_SOURCE_LOCATOR,
        ),
        (
            source_document(locator="C:\\private\\guide.md"),
            KnowledgeValidationCode.UNSAFE_SOURCE_LOCATOR,
        ),
    ],
)
def test_malformed_documents_are_rejected(
    source: KnowledgeDocumentInput,
    expected_code: KnowledgeValidationCode,
) -> None:
    outcome = KnowledgeDocumentImporter().import_document(source)

    assert isinstance(outcome, KnowledgeImportFailure)
    assert expected_code in {issue.code for issue in outcome.issues}
    assert all("C:\\private" not in issue.message for issue in outcome.issues)
    assert all("password" not in issue.message for issue in outcome.issues)


def test_digest_mismatch_is_rejected() -> None:
    source = replace(source_document(), declared_content_sha256="f" * 64)

    outcome = KnowledgeDocumentImporter().import_document(source)

    assert isinstance(outcome, KnowledgeImportFailure)
    assert [issue.code for issue in outcome.issues] == [
        KnowledgeValidationCode.CONTENT_IDENTITY_MISMATCH
    ]


def test_unicode_is_normalized_before_identity_and_chunking() -> None:
    composed = source_document(content="# Café\n\nA fictional café uses crystal moss.")
    decomposed = source_document(
        content="# Cafe\u0301\n\nA fictional cafe\u0301 uses crystal moss."
    )

    first = imported_document(composed)
    second = imported_document(decomposed)

    assert first.metadata.content_identity == second.metadata.content_identity
    assert first.chunks == second.chunks
