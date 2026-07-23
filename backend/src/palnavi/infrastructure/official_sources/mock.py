"""Deterministic synthetic transport for offline snapshot development."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from palnavi.domain.official_sources import (
    Clock,
    OfficialSourceFetchRequest,
    SourceFetchOutcome,
    SourceFetchOutcomeKind,
)
from palnavi.infrastructure.official_sources.registry import (
    validate_official_source_request,
)
from palnavi.infrastructure.official_sources.transport import (
    _fetch_with_mock_transport,
)

_MOCK_OUTCOMES = {
    "palworld-mod-guideline": SourceFetchOutcomeKind.SUCCESS,
    "palworld-news": SourceFetchOutcomeKind.SUCCESS,
    "palworld-rest-info-doc": SourceFetchOutcomeKind.TIMEOUT,
    "palworld-rest-introduction": SourceFetchOutcomeKind.REDIRECT_REJECTED,
    "palworld-rest-players-doc": SourceFetchOutcomeKind.CONTENT_TYPE_REJECTED,
    "palworld-server-guide": SourceFetchOutcomeKind.NETWORK_RESTRICTED,
    "palworld-server-mods": SourceFetchOutcomeKind.RESPONSE_TOO_LARGE,
    "palworld-technology-ids": SourceFetchOutcomeKind.MALFORMED_ENCODING,
    "pocketpair-derivative-work": SourceFetchOutcomeKind.UNAVAILABLE,
}


class DeterministicMockOfficialSourceTransport:
    async def fetch(self, request: OfficialSourceFetchRequest) -> SourceFetchOutcome:
        validate_official_source_request(request.source_id, request.canonical_url)

        def handler(http_request: httpx.Request) -> httpx.Response:
            kind = _MOCK_OUTCOMES[request.source_id]
            if kind is SourceFetchOutcomeKind.NETWORK_RESTRICTED:
                raise httpx.ConnectError("synthetic restriction", request=http_request)
            if kind is SourceFetchOutcomeKind.TIMEOUT:
                raise httpx.ReadTimeout("synthetic timeout", request=http_request)
            if kind is SourceFetchOutcomeKind.UNAVAILABLE:
                raise httpx.ReadError("synthetic unavailable", request=http_request)
            if kind is SourceFetchOutcomeKind.REDIRECT_REJECTED:
                return httpx.Response(
                    302,
                    headers={"location": "https://redirect.fixture.invalid/"},
                    request=http_request,
                )
            if kind is SourceFetchOutcomeKind.CONTENT_TYPE_REJECTED:
                return httpx.Response(
                    200,
                    headers={"content-type": "application/octet-stream"},
                    content=b"SYNTHETIC FIXTURE ONLY",
                    request=http_request,
                )
            if kind is SourceFetchOutcomeKind.RESPONSE_TOO_LARGE:
                return httpx.Response(
                    200,
                    headers={
                        "content-type": "text/plain; charset=utf-8",
                        "content-length": str(request.max_response_bytes + 1),
                    },
                    request=http_request,
                )
            if kind is SourceFetchOutcomeKind.MALFORMED_ENCODING:
                return httpx.Response(
                    200,
                    headers={"content-type": "text/plain; charset=utf-8"},
                    content=b"SYNTHETIC FIXTURE ONLY\n\xff",
                    request=http_request,
                )
            body = _synthetic_body(request.source_id)
            return httpx.Response(
                200,
                headers={
                    "content-type": "text/plain; charset=utf-8",
                    "etag": f'"synthetic-{request.source_id}"',
                    "last-modified": "Thu, 23 Jul 2026 00:00:00 GMT",
                    "content-length": str(len(body)),
                },
                content=body,
                request=http_request,
            )

        return await _fetch_with_mock_transport(
            request,
            httpx.MockTransport(handler),
        )


def _synthetic_body(source_id: str) -> bytes:
    body = (
        "PALNAVI SYNTHETIC TRANSPORT FIXTURE\n"
        "NOT PALWORLD KNOWLEDGE\n"
        f"source_id={source_id}\n"
        f"fixture_locator=https://{source_id}.fixture.invalid/\n"
    ).encode()
    return body


class DeterministicMockClock(Clock):
    def __init__(self) -> None:
        self._values = (
            datetime(2026, 7, 23, 0, 0, 0, tzinfo=UTC),
            datetime(2026, 7, 23, 0, 0, 1, tzinfo=UTC),
        )
        self._index = 0

    def now(self) -> datetime:
        value = self._values[min(self._index, len(self._values) - 1)]
        self._index += 1
        return value
