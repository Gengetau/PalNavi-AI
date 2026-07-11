import json
import shutil
import sys
from pathlib import Path

from palnavi.domain.knowledge import (
    KnowledgeClassification,
    KnowledgeImportFailure,
    KnowledgeImportSuccess,
    KnowledgeQuery,
    KnowledgeSearchSuccess,
    KnowledgeValidationCode,
)
from palnavi.infrastructure.knowledge_cli import main as knowledge_cli_main
from palnavi.infrastructure.knowledge_corpus import (
    LocalSyntheticKnowledgeCorpus,
    default_synthetic_knowledge_root,
)
from palnavi.infrastructure.sqlite_knowledge_repository import SQLiteKnowledgeRepository


def test_bundled_corpus_is_synthetic_stable_and_retrievable(tmp_path: Path) -> None:
    corpus = LocalSyntheticKnowledgeCorpus(default_synthetic_knowledge_root())

    first = corpus.load()
    second = corpus.load()

    assert first == second
    assert len(first) == 3
    documents = []
    for outcome in first:
        assert isinstance(outcome, KnowledgeImportSuccess)
        assert outcome.document.metadata.classification is KnowledgeClassification.SYNTHETIC
        assert outcome.document.metadata.game_version_scope.value.startswith("synthetic-")
        assert outcome.document.metadata.provenance.license_or_usage_note
        documents.append(outcome.document)

    repository = SQLiteKnowledgeRepository(tmp_path / "knowledge.sqlite3")
    for document in documents:
        repository.import_document(document)
    version_one = repository.search(
        KnowledgeQuery("crystal moss", exact_game_version="synthetic-1.0", synthetic_only=True)
    )
    version_two = repository.search(
        KnowledgeQuery("amber reeds", exact_game_version="synthetic-2.0", synthetic_only=True)
    )

    assert isinstance(version_one, KnowledgeSearchSuccess)
    assert {item.document_id.value for item in version_one.results} == {
        "synthetic-guide-a",
        "synthetic-guide-ja",
    }
    assert isinstance(version_two, KnowledgeSearchSuccess)
    assert [item.document_id.value for item in version_two.results] == ["synthetic-guide-b"]


def test_corpus_digest_mismatch_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "synthetic-v1"
    shutil.copytree(default_synthetic_knowledge_root(), root)
    with (root / "guide-a.md").open("a", encoding="utf-8") as document:
        document.write("\nTampered synthetic text.\n")

    outcomes = LocalSyntheticKnowledgeCorpus(root).load()

    assert isinstance(outcomes[0], KnowledgeImportFailure)
    assert KnowledgeValidationCode.CONTENT_IDENTITY_MISMATCH in {
        issue.code for issue in outcomes[0].issues
    }


def test_corpus_manifest_rejects_path_escape_without_exposing_paths(tmp_path: Path) -> None:
    root = tmp_path / "private-corpus-location"
    shutil.copytree(default_synthetic_knowledge_root(), root)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["documents"][0]["content_file"] = "../private-document.md"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    outcomes = LocalSyntheticKnowledgeCorpus(root).load()

    assert isinstance(outcomes[0], KnowledgeImportFailure)
    issue = outcomes[0].issues[0]
    assert issue.code is KnowledgeValidationCode.MALFORMED_MANIFEST
    assert "private-corpus-location" not in issue.message
    assert "private-document.md" not in issue.message
    assert "Traceback" not in issue.message


def test_cli_import_is_idempotent_and_does_not_print_local_paths(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    database_path = tmp_path / "private-db-location" / "knowledge.sqlite3"
    corpus_path = default_synthetic_knowledge_root()
    arguments = [
        "knowledge_cli",
        "--database",
        str(database_path),
        "--corpus",
        str(corpus_path),
    ]
    monkeypatch.setattr(sys, "argv", arguments)

    first_exit = knowledge_cli_main()
    first_output = capsys.readouterr()
    second_exit = knowledge_cli_main()
    second_output = capsys.readouterr()

    assert first_exit == second_exit == 0
    assert first_output.err == second_output.err == ""
    assert first_output.out.count(": created") == 3
    assert second_output.out.count(": unchanged") == 3
    combined = first_output.out + second_output.out
    assert str(database_path) not in combined
    assert str(corpus_path) not in combined
