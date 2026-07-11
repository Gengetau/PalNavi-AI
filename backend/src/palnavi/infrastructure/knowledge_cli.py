"""Developer command for importing the bundled synthetic corpus into local SQLite."""

from __future__ import annotations

import argparse
from pathlib import Path

from palnavi.domain.knowledge import (
    KnowledgeImportFailure,
    KnowledgeImportSuccess,
    KnowledgeStoreSuccess,
)
from palnavi.infrastructure.knowledge_corpus import (
    LocalSyntheticKnowledgeCorpus,
    default_synthetic_knowledge_root,
)
from palnavi.infrastructure.sqlite_knowledge_repository import (
    SQLiteKnowledgeRepository,
    default_knowledge_database_path,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import synthetic knowledge into local SQLite")
    parser.add_argument("--database", type=Path, default=default_knowledge_database_path())
    parser.add_argument("--corpus", type=Path, default=default_synthetic_knowledge_root())
    args = parser.parse_args()

    repository = SQLiteKnowledgeRepository(args.database)
    outcomes = LocalSyntheticKnowledgeCorpus(args.corpus).load()
    exit_code = 0
    for outcome in outcomes:
        if isinstance(outcome, KnowledgeImportFailure):
            codes = ",".join(issue.code.value for issue in outcome.issues)
            print(f"knowledge import rejected safely: {codes}")
            exit_code = 1
            continue
        if not isinstance(outcome, KnowledgeImportSuccess):
            raise AssertionError("knowledge corpus returned an unsupported result type")
        stored = repository.import_document(outcome.document)
        if isinstance(stored, KnowledgeStoreSuccess):
            print(f"{outcome.document.metadata.document_id.value}: {stored.disposition.value}")
        else:
            print("knowledge repository operation failed safely")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
