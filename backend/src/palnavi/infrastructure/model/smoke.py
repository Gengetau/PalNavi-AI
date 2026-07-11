"""Explicit, opt-in live smoke command for a configured model provider."""

from __future__ import annotations

import argparse
import asyncio

from palnavi.application import (
    ModelGatewayError,
    ModelGenerationService,
    ModelMessage,
    ModelMessageRole,
)
from palnavi.infrastructure.model.config import load_model_provider_config
from palnavi.infrastructure.model.factory import create_model_gateway


async def _run(message: str) -> int:
    gateway = None
    try:
        config = load_model_provider_config()
        gateway = create_model_gateway(config)
        service = ModelGenerationService(gateway, config.provider_id, config.model_id)
        response = await service.generate(
            (ModelMessage(ModelMessageRole.USER, message),),
            max_output_tokens=config.default_max_output_tokens,
        )
    except ModelGatewayError as error:
        print(f"smoke skipped or failed safely: {error}")
        return 2
    finally:
        if gateway is not None:
            await gateway.aclose()
    print(response.text)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one explicit live model-provider request")
    parser.add_argument("--live", action="store_true", help="acknowledge a real API request")
    parser.add_argument("--message", default="Reply with OK.")
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required; no request was sent")
    return asyncio.run(_run(args.message))


if __name__ == "__main__":
    raise SystemExit(main())
