"""FastAPI dependency providers for immutable application services."""

from typing import Annotated

from fastapi import Depends

from palnavi.application import BreedingPlanningService, KnowledgeRetrievalService
from palnavi.domain.breeding import BreedingRoutePlanner
from palnavi.domain.data import BreedingDatasetRepository
from palnavi.domain.knowledge import KnowledgeRepository
from palnavi.infrastructure.json_dataset_repository import (
    LocalJsonBreedingDatasetRepository,
    default_dataset_root,
)
from palnavi.infrastructure.sqlite_knowledge_repository import (
    SQLiteKnowledgeRepository,
    default_knowledge_database_path,
)


def get_dataset_repository() -> BreedingDatasetRepository:
    return LocalJsonBreedingDatasetRepository(root=default_dataset_root())


def get_breeding_planning_service(
    repository: Annotated[BreedingDatasetRepository, Depends(get_dataset_repository)],
) -> BreedingPlanningService:
    return BreedingPlanningService(repository=repository, planner=BreedingRoutePlanner())


def get_knowledge_repository() -> KnowledgeRepository:
    return SQLiteKnowledgeRepository(default_knowledge_database_path())


def get_knowledge_retrieval_service(
    repository: Annotated[KnowledgeRepository, Depends(get_knowledge_repository)],
) -> KnowledgeRetrievalService:
    return KnowledgeRetrievalService(repository)
