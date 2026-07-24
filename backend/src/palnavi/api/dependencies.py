"""FastAPI dependency providers for immutable application services."""

from collections.abc import AsyncIterator
from typing import Annotated

import anyio
from fastapi import Depends

from palnavi.application import (
    BreedingPlanningService,
    DirectBreedingService,
    KnowledgeExplanationService,
    KnowledgeRetrievalService,
    ModelGeneration,
    ModelGenerationService,
    ModelMessage,
    ModelResponse,
)
from palnavi.domain.breeding import BreedingRoutePlanner
from palnavi.domain.data import BreedingDatasetRepository, GenderAwareBreedingDatasetRepository
from palnavi.domain.knowledge import KnowledgeRepository
from palnavi.infrastructure.json_dataset_repository import (
    LocalJsonBreedingDatasetRepository,
    default_dataset_root,
)
from palnavi.infrastructure.model.adapters import HttpModelGateway
from palnavi.infrastructure.model.config import load_model_provider_config
from palnavi.infrastructure.model.factory import create_model_gateway
from palnavi.infrastructure.palworld_dataset_repository import (
    LocalPalworldBreedingDatasetRepository,
    default_palworld_dataset_root,
)
from palnavi.infrastructure.sqlite_knowledge_repository import (
    SQLiteKnowledgeRepository,
    default_knowledge_database_path,
)


class _DeferredModelGenerationService(ModelGeneration):
    """Delay optional provider setup until retrieved evidence requires generation."""

    def __init__(self) -> None:
        self._gateway: HttpModelGateway | None = None
        self._service: ModelGenerationService | None = None

    async def generate(
        self,
        messages: tuple[ModelMessage, ...],
        *,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> ModelResponse:
        service = self._service
        if service is None:
            config = load_model_provider_config()
            gateway = create_model_gateway(config)
            self._gateway = gateway
            service = ModelGenerationService(
                gateway=gateway,
                provider_id=config.provider_id,
                model_id=config.model_id,
            )
            self._service = service

        return await service.generate(
            messages,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

    async def aclose(self) -> None:
        gateway = self._gateway
        self._gateway = None
        self._service = None
        if gateway is not None:
            await gateway.aclose()


def get_dataset_repository() -> BreedingDatasetRepository:
    return LocalJsonBreedingDatasetRepository(root=default_dataset_root())


def get_breeding_planning_service(
    repository: Annotated[BreedingDatasetRepository, Depends(get_dataset_repository)],
) -> BreedingPlanningService:
    return BreedingPlanningService(repository=repository, planner=BreedingRoutePlanner())


def get_direct_breeding_repository() -> GenderAwareBreedingDatasetRepository:
    return LocalPalworldBreedingDatasetRepository(root=default_palworld_dataset_root())


def get_direct_breeding_service(
    repository: Annotated[
        GenderAwareBreedingDatasetRepository,
        Depends(get_direct_breeding_repository),
    ],
) -> DirectBreedingService:
    return DirectBreedingService(repository=repository)


def get_knowledge_repository() -> KnowledgeRepository:
    return SQLiteKnowledgeRepository(default_knowledge_database_path())


def get_knowledge_retrieval_service(
    repository: Annotated[KnowledgeRepository, Depends(get_knowledge_repository)],
) -> KnowledgeRetrievalService:
    return KnowledgeRetrievalService(repository)


async def get_knowledge_explanation_service(
    retrieval_service: Annotated[
        KnowledgeRetrievalService,
        Depends(get_knowledge_retrieval_service),
    ],
) -> AsyncIterator[KnowledgeExplanationService]:
    deferred_service = _DeferredModelGenerationService()
    try:
        yield KnowledgeExplanationService(
            retrieval_service=retrieval_service,
            model_generation_service=deferred_service,
        )
    finally:
        with anyio.CancelScope(shield=True):
            await deferred_service.aclose()
