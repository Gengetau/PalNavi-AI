"""FastAPI dependency providers for immutable application services."""

from typing import Annotated

from fastapi import Depends

from palnavi.application import BreedingPlanningService
from palnavi.domain.breeding import BreedingRoutePlanner
from palnavi.domain.data import BreedingDatasetRepository
from palnavi.infrastructure.json_dataset_repository import (
    LocalJsonBreedingDatasetRepository,
    default_dataset_root,
)


def get_dataset_repository() -> BreedingDatasetRepository:
    return LocalJsonBreedingDatasetRepository(root=default_dataset_root())


def get_breeding_planning_service(
    repository: Annotated[BreedingDatasetRepository, Depends(get_dataset_repository)],
) -> BreedingPlanningService:
    return BreedingPlanningService(repository=repository, planner=BreedingRoutePlanner())
