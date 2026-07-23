import json
import shutil
import sys
from pathlib import Path

import pytest

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
    _is_path_within_resolved_root,
    default_synthetic_knowledge_root,
)
from palnavi.infrastructure.sqlite_knowledge_repository import SQLiteKnowledgeRepository


def _record_text_reads(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    opened_paths: list[Path] = []
    original_read_text = Path.read_text

    def recording_read_text(
        path: Path,
        encoding: str | None = None,
        errors: str | None = None,
    ) -> str:
        opened_paths.append(path)
        return original_read_text(path, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", recording_read_text)
    return opened_paths


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


@pytest.mark.parametrize(
    "content_file",
    [
        "../private.md",
        r"..\private.md",
        r"subdir\guide.md",
        r"C:\private.md",
        r"\\server\share\private.md",
        "",
        "   ",
        "/private.md",
        "//server/share/private.md",
        "C:/private.md",
        "C:private.md",
        "nested/C:private.md",
        "nested/C:/private.md",
        r"\private.md",
        ".",
        "..",
        "./guide.md",
        "nested/./guide.md",
        "nested/../guide.md",
        "guide.pdf",
    ],
)
def test_corpus_manifest_rejects_unsafe_content_paths_without_exposing_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    content_file: str,
) -> None:
    root = tmp_path / "private-corpus-location"
    shutil.copytree(default_synthetic_knowledge_root(), root)
    private_document = tmp_path / "private.md"
    private_document.write_text("Private material must not be opened.\n", encoding="utf-8")
    resolved_root = root.resolve(strict=True)
    resolved_private_document = private_document.resolve(strict=True)
    resolved_tmp_path = tmp_path.resolve(strict=True)

    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["documents"] = [manifest["documents"][0]]
    manifest["documents"][0]["content_file"] = content_file
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    resolve_calls: list[Path] = []
    original_resolve = Path.resolve

    def recording_resolve(path: Path, strict: bool = False) -> Path:
        resolve_calls.append(path)
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", recording_resolve)
    opened_paths = _record_text_reads(monkeypatch)
    outcomes = LocalSyntheticKnowledgeCorpus(root).load()

    assert len(outcomes) == 1
    assert isinstance(outcomes[0], KnowledgeImportFailure)
    issue = outcomes[0].issues[0]
    assert issue.code is KnowledgeValidationCode.MALFORMED_MANIFEST
    assert resolve_calls == [root]
    assert opened_paths == [resolved_root / "manifest.json"]
    if content_file.strip() and content_file not in {".", ".."}:
        assert content_file not in issue.message
    for secret in (
        root.name,
        private_document.name,
        str(resolved_root),
        str(resolved_private_document),
        str(resolved_tmp_path),
    ):
        assert secret not in issue.message
    assert "OSError" not in issue.message
    assert "Traceback" not in issue.message


def test_corpus_manifest_accepts_nested_posix_content_path(tmp_path: Path) -> None:
    root = tmp_path / "synthetic-v1"
    shutil.copytree(default_synthetic_knowledge_root(), root)
    nested = root / "nested"
    nested.mkdir()
    shutil.copyfile(root / "guide-a.md", nested / "guide.md")

    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["documents"] = [manifest["documents"][0]]
    manifest["documents"][0]["content_file"] = "nested/guide.md"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    outcomes = LocalSyntheticKnowledgeCorpus(root).load()

    assert len(outcomes) == 1
    assert isinstance(outcomes[0], KnowledgeImportSuccess)


def test_corpus_manifest_rejects_resolved_symlink_escape_without_exposing_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "private-corpus-location"
    shutil.copytree(default_synthetic_knowledge_root(), root)
    outside_document = tmp_path / "outside-private-document.md"
    shutil.copyfile(root / "guide-a.md", outside_document)
    link = root / "linked-guide.md"

    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["documents"] = [manifest["documents"][0]]
    manifest["documents"][0]["content_file"] = link.name
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    try:
        link.symlink_to(outside_document)
    except (NotImplementedError, OSError):
        assert not _is_path_within_resolved_root(
            outside_document.resolve(strict=True),
            root.resolve(strict=True),
        )
        return

    resolved_root = root.resolve(strict=True)
    resolved_outside = outside_document.resolve(strict=True)
    resolved_link = link.resolve(strict=True)
    assert resolved_link == resolved_outside
    assert not _is_path_within_resolved_root(resolved_link, resolved_root)

    opened_paths = _record_text_reads(monkeypatch)
    outcomes = LocalSyntheticKnowledgeCorpus(root).load()

    assert len(outcomes) == 1
    assert isinstance(outcomes[0], KnowledgeImportFailure)
    issue = outcomes[0].issues[0]
    assert issue.code is KnowledgeValidationCode.MALFORMED_MANIFEST
    assert opened_paths == [resolved_root / "manifest.json"]
    for secret in (
        link.name,
        root.name,
        outside_document.name,
        str(link),
        str(resolved_root),
        str(resolved_outside),
    ):
        assert secret not in issue.message
    assert "OSError" not in issue.message
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
