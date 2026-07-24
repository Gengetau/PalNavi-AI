"""Credential-free, fixed-host metadata transport for official public pages."""

from __future__ import annotations

import asyncio
import codecs
import hashlib
from collections.abc import AsyncIterator, Coroutine
from contextlib import suppress
from threading import Thread
from typing import Any

import httpx

from palnavi.domain.official_sources import (
    OfficialSourceFetchRequest,
    SanitizedResponseMetadata,
    SourceFetchFailure,
    SourceFetchOutcome,
    SourceFetchOutcomeKind,
    SourceFetchSuccess,
)
from palnavi.infrastructure.official_sources.registry import (
    validate_official_source_request,
)

_APPROVED_MEDIA_TYPES = frozenset({"text/html", "text/plain", "application/xhtml+xml"})
_MAX_HEADER_CHARS = 500
_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,text/plain;q=0.8",
    "Accept-Encoding": "identity",
    "User-Agent": "PalNavi-Official-Metadata/1.0",
}


class HttpxOfficialSourceTransport:
    async def aclose(self) -> None:
        return

    async def fetch(self, request: OfficialSourceFetchRequest) -> SourceFetchOutcome:
        return await _HttpxOfficialSourceTransportExecutor().fetch(request)


async def _fetch_with_mock_transport(
    request: OfficialSourceFetchRequest,
    transport: httpx.MockTransport,
) -> SourceFetchOutcome:
    return await _HttpxOfficialSourceTransportExecutor(mock_transport=transport).fetch(request)


class _HttpxOfficialSourceTransportExecutor:
    def __init__(
        self,
        *,
        mock_transport: httpx.MockTransport | None = None,
    ) -> None:
        self._mock_transport = mock_transport

    async def fetch(self, request: OfficialSourceFetchRequest) -> SourceFetchOutcome:
        try:
            return await asyncio.wait_for(
                self._fetch_once(request),
                timeout=request.timeout_seconds,
            )
        except TimeoutError:
            return SourceFetchFailure(SourceFetchOutcomeKind.TIMEOUT)

    async def _fetch_once(self, request: OfficialSourceFetchRequest) -> SourceFetchOutcome:
        try:
            validate_official_source_request(request.source_id, request.canonical_url)
        except ValueError:
            return SourceFetchFailure(SourceFetchOutcomeKind.UNAVAILABLE)

        response: httpx.Response | None = None
        client = _new_client(request.timeout_seconds, self._mock_transport)
        try:
            timeout = {
                "connect": request.timeout_seconds,
                "read": request.timeout_seconds,
                "write": request.timeout_seconds,
                "pool": request.timeout_seconds,
            }
            http_request = client.build_request(
                "GET",
                request.canonical_url,
                headers=_REQUEST_HEADERS,
                extensions={"timeout": timeout},
            )
            for sensitive_header in (
                "authorization",
                "proxy-authorization",
                "cookie",
            ):
                if sensitive_header in http_request.headers:
                    del http_request.headers[sensitive_header]
            if http_request.content:
                return SourceFetchFailure(SourceFetchOutcomeKind.UNAVAILABLE)
            response = await client.send(
                http_request,
                stream=True,
                follow_redirects=False,
            )
            if 300 <= response.status_code < 400:
                return SourceFetchFailure(SourceFetchOutcomeKind.REDIRECT_REJECTED)
            if response.status_code != 200:
                return SourceFetchFailure(SourceFetchOutcomeKind.UNAVAILABLE)
            if str(response.url) != request.canonical_url or "location" in response.headers:
                return SourceFetchFailure(SourceFetchOutcomeKind.REDIRECT_REJECTED)

            media_type = _approved_media_type(response.headers.get("content-type"))
            if media_type is None or not _identity_encoding(response.headers):
                return SourceFetchFailure(SourceFetchOutcomeKind.CONTENT_TYPE_REJECTED)

            declared_length = _declared_length(response.headers.get("content-length"))
            if declared_length is None and "content-length" in response.headers:
                return SourceFetchFailure(SourceFetchOutcomeKind.UNAVAILABLE)
            if declared_length is not None and declared_length > request.max_response_bytes:
                return SourceFetchFailure(SourceFetchOutcomeKind.RESPONSE_TOO_LARGE)

            etag_values = response.headers.get_list("etag")
            last_modified_values = response.headers.get_list("last-modified")
            if len(etag_values) > 1 or len(last_modified_values) > 1:
                return SourceFetchFailure(SourceFetchOutcomeKind.UNAVAILABLE)
            etag = _bounded_header(etag_values[0] if etag_values else None)
            last_modified = _bounded_header(
                last_modified_values[0] if last_modified_values else None
            )
            if (
                response.headers.get("etag") is not None
                and etag is None
                or response.headers.get("last-modified") is not None
                and last_modified is None
            ):
                return SourceFetchFailure(SourceFetchOutcomeKind.UNAVAILABLE)

            digest = hashlib.sha256()
            byte_count = 0
            decoder = codecs.getincrementaldecoder("utf-8")(errors="strict")
            try:
                async for chunk in _response_chunks(response):
                    byte_count += len(chunk)
                    if byte_count > request.max_response_bytes:
                        return SourceFetchFailure(SourceFetchOutcomeKind.RESPONSE_TOO_LARGE)
                    if declared_length is None and byte_count >= request.max_response_bytes:
                        return SourceFetchFailure(SourceFetchOutcomeKind.RESPONSE_TOO_LARGE)
                    digest.update(chunk)
                    decoder.decode(chunk, final=False)
                decoder.decode(b"", final=True)
            except UnicodeDecodeError:
                return SourceFetchFailure(SourceFetchOutcomeKind.MALFORMED_ENCODING)
            except httpx.TimeoutException:
                return SourceFetchFailure(SourceFetchOutcomeKind.TIMEOUT)
            except (httpx.RequestError, RuntimeError):
                return SourceFetchFailure(SourceFetchOutcomeKind.UNAVAILABLE)

            if byte_count == 0:
                return SourceFetchFailure(SourceFetchOutcomeKind.UNAVAILABLE)
            if declared_length is not None and byte_count != declared_length:
                return SourceFetchFailure(SourceFetchOutcomeKind.UNAVAILABLE)
            return SourceFetchSuccess(
                kind=SourceFetchOutcomeKind.SUCCESS,
                metadata=SanitizedResponseMetadata(
                    status_code=200,
                    media_type=media_type,
                    etag=etag,
                    last_modified=last_modified,
                    final_url=request.canonical_url,
                ),
                response_bytes=byte_count,
                content_sha256=digest.hexdigest(),
            )
        except httpx.TimeoutException:
            return SourceFetchFailure(SourceFetchOutcomeKind.TIMEOUT)
        except (httpx.ProxyError, httpx.ConnectError):
            return SourceFetchFailure(SourceFetchOutcomeKind.NETWORK_RESTRICTED)
        except (httpx.RequestError, ValueError, RuntimeError):
            return SourceFetchFailure(SourceFetchOutcomeKind.UNAVAILABLE)
        finally:
            _schedule_cleanup(response, client)


def _new_client(
    timeout_seconds: float,
    transport: httpx.MockTransport | None,
) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=transport,
        trust_env=False,
        follow_redirects=False,
        cookies={},
        headers=_REQUEST_HEADERS,
        timeout=httpx.Timeout(timeout_seconds),
        limits=httpx.Limits(max_connections=1, max_keepalive_connections=0),
        http2=False,
    )


def _approved_media_type(value: str | None) -> str | None:
    if value is None or len(value) > _MAX_HEADER_CHARS:
        return None
    parts = [part.strip() for part in value.split(";")]
    if any(not part for part in parts) or len(parts) > 2:
        return None
    media_type = parts[0].lower()
    if media_type not in _APPROVED_MEDIA_TYPES:
        return None
    if len(parts) == 2:
        name, separator, parameter_value = parts[1].partition("=")
        raw_value = parameter_value.strip()
        if raw_value.startswith('"') or raw_value.endswith('"'):
            if len(raw_value) < 2 or not (raw_value.startswith('"') and raw_value.endswith('"')):
                return None
            raw_value = raw_value[1:-1]
            if '"' in raw_value:
                return None
        elif '"' in raw_value:
            return None
        if (
            separator != "="
            or name.strip().lower() != "charset"
            or raw_value.lower() not in {"utf-8", "utf8"}
        ):
            return None
    return media_type


async def _response_chunks(response: httpx.Response) -> AsyncIterator[bytes]:
    if response.is_stream_consumed:
        if response.content:
            yield response.content
        return
    async for chunk in response.aiter_raw(chunk_size=64 * 1024):
        yield chunk


def _identity_encoding(headers: httpx.Headers) -> bool:
    value = headers.get("content-encoding")
    return value is None or value.strip().lower() == "identity"


def _declared_length(value: str | None) -> int | None:
    if value is None:
        return None
    if not value.isascii() or not value.isdigit() or len(value) > 16:
        return None
    return int(value)


def _bounded_header(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped or len(stripped) > _MAX_HEADER_CHARS or not stripped.isascii():
        return None
    if any(ord(character) < 32 and character != "\t" for character in stripped):
        return None
    return stripped


def _schedule_cleanup(
    response: httpx.Response | None,
    client: httpx.AsyncClient,
) -> None:
    async def close_all() -> None:
        if response is not None:
            with suppress(BaseException):
                await response.aclose()
        with suppress(BaseException):
            await client.aclose()

    close_result = close_all()

    def run_close() -> None:
        with suppress(BaseException):
            asyncio.run(close_result)

    try:
        Thread(
            target=run_close,
            name="palnavi-official-source-cleanup",
            daemon=True,
        ).start()
    except BaseException:
        _close_unawaited(close_result)


def _close_unawaited(close_result: Coroutine[Any, Any, None]) -> None:
    with suppress(BaseException):
        close_result.close()
