from __future__ import annotations

import asyncio
import hashlib
import json
import os
import socket
import subprocess
from dataclasses import replace
from pathlib import Path
from threading import Event
from typing import Any, NoReturn, cast

import anyio
import httpx
import pytest

from palnavi.application import (
    OfficialSourceAcquisitionService,
    canonical_json_bytes,
    snapshot_manifest_document,
    snapshot_manifest_sha256,
)
from palnavi.domain.official_sources import (
    OfficialSourceFetchRequest,
    SanitizedResponseMetadata,
    SnapshotAcquisitionMode,
    SourceFetchFailure,
    SourceFetchOutcomeKind,
    SourceFetchSuccess,
)
from palnavi.infrastructure.official_sources import (
    AUTHORIZED_SOURCE_URLS,
    DeterministicMockClock,
    DeterministicMockOfficialSourceTransport,
    OfficialSourceRegistryError,
    SnapshotWriteError,
    load_official_source_registry,
    parse_official_source_registry,
    validate_official_source_request,
    write_snapshot_manifest,
)
from palnavi.infrastructure.official_sources.cli import main as snapshot_cli
from palnavi.infrastructure.official_sources.transport import (
    _fetch_with_mock_transport,
)


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("official-source tests forbid ambient network and subprocesses")

    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    monkeypatch.setattr(socket, "gethostbyname", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "sendto", denied)
    monkeypatch.setattr(asyncio, "open_connection", denied)
    monkeypatch.setattr(subprocess, "Popen", denied)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def registry_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "official-sources-v1.json"


def registry_document() -> dict[str, object]:
    value = json.loads(registry_path().read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def repair_registry_digest(document: dict[str, object]) -> None:
    payload = {key: value for key, value in document.items() if key != "registry_sha256"}
    document["registry_sha256"] = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def source_request(source_id: str = "palworld-server-guide") -> OfficialSourceFetchRequest:
    return OfficialSourceFetchRequest(
        source_id=source_id,
        canonical_url=AUTHORIZED_SOURCE_URLS[source_id],
    )


def test_checked_in_registry_has_exact_canonical_identity_and_sources() -> None:
    registry = load_official_source_registry(registry_path())

    assert registry.registry_sha256 == (
        "599104fc01705e6e0ccc058ea44f7ddee1b25846f8c77bd1819cfcd533f32e46"
    )
    assert tuple(source.source_id for source in registry.sources) == tuple(
        sorted(AUTHORIZED_SOURCE_URLS)
    )
    assert {source.canonical_url for source in registry.sources} == set(
        AUTHORIZED_SOURCE_URLS.values()
    )
    assert all(
        source.content_capture_policy.value == "metadata_only" for source in registry.sources
    )
    assert all(source.live_probe_permitted for source in registry.sources)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda document: document.update({"unknown": True}),
        lambda document: document.pop("schema_version"),
        lambda document: document.update({"schema_version": True}),
        lambda document: document.update({"schema_version": 2}),
        lambda document: document.update({"registry_sha256": "f" * 64}),
        lambda document: document.update({"sources": list(reversed(document["sources"]))}),
        lambda document: document.update({"sources": document["sources"][:-1]}),
        lambda document: document.update(
            {"sources": [*document["sources"], document["sources"][0]]}
        ),
    ],
)
def test_registry_rejects_malformed_root_and_identity(mutation: object) -> None:
    document = registry_document()
    assert callable(mutation)
    mutation(document)
    if document.get("registry_sha256") != "f" * 64:
        repair_registry_digest(document)

    with pytest.raises(OfficialSourceRegistryError):
        parse_official_source_registry(document)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_id", "Bad ID"),
        ("canonical_url", "https://docs.palworldgame.com/unknown/"),
        ("publisher", ""),
        ("source_kind", "other"),
        ("observed_version", ""),
        ("content_sensitivity", "unknown"),
        ("content_capture_policy", "full_body"),
        ("usage_review_status", "approved"),
        ("usage_note", ""),
        ("live_probe_permitted", 1),
        ("verified_at", "2026-07-23T20:04:09+00:00"),
    ],
)
def test_registry_rejects_every_malformed_entry_field(field: str, value: object) -> None:
    document = registry_document()
    sources = document["sources"]
    assert isinstance(sources, list)
    entry = sources[0]
    assert isinstance(entry, dict)
    entry[field] = value
    repair_registry_digest(document)

    with pytest.raises(OfficialSourceRegistryError):
        parse_official_source_registry(document)


def test_registry_loader_rejects_duplicate_keys_invalid_utf8_and_oversize(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
    invalid = tmp_path / "invalid.json"
    invalid.write_bytes(b"\xff")
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b" " * (128 * 1024 + 1))

    for path in (duplicate, invalid, oversized):
        with pytest.raises(OfficialSourceRegistryError):
            load_official_source_registry(path)


def test_registry_loader_rejects_symlinks_and_special_files(tmp_path: Path) -> None:
    valid = tmp_path / "valid.json"
    valid.write_bytes(registry_path().read_bytes())
    link = tmp_path / "link.json"
    link.symlink_to(valid)
    fifo = tmp_path / "registry.fifo"
    os.mkfifo(fifo)

    for path in (link, fifo):
        with pytest.raises(OfficialSourceRegistryError):
            load_official_source_registry(path)


@pytest.mark.parametrize(
    "url",
    [
        "http://docs.palworldgame.com/",
        "https://user@docs.palworldgame.com/",
        "https://docs.palworldgame.com:443/",
        "https://docs.palworldgame.com/?source=test",
        "https://docs.palworldgame.com/#fragment",
        "https://docs.palworldgame.com.evil.invalid/",
        "https://evil-docs.palworldgame.com/",
        "https://127.0.0.1/",
        "https://[::1]/",
        "https://docs.palworldgame.com/players",
        "https://docs.palworldgame.com/info",
        "https://docs.palworldgame.com/../players",
    ],
)
def test_request_boundary_rejects_arbitrary_runtime_and_lookalike_urls(url: str) -> None:
    with pytest.raises(ValueError):
        validate_official_source_request("palworld-server-guide", url)


def test_request_boundary_rejects_valid_url_with_wrong_source_id() -> None:
    with pytest.raises(ValueError):
        validate_official_source_request(
            "palworld-news",
            AUTHORIZED_SOURCE_URLS["palworld-server-guide"],
        )


def test_authorized_source_mapping_is_immutable() -> None:
    with pytest.raises(TypeError):
        cast(Any, AUTHORIZED_SOURCE_URLS)["palworld-server-guide"] = (
            "https://unexpected.fixture.invalid/"
        )


@pytest.mark.anyio
async def test_http_transport_sends_one_credential_free_fixed_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []
    body = b"SYNTHETIC TRANSPORT BODY"
    monkeypatch.setenv("HTTP_PROXY", "http://ambient-proxy.fixture.invalid/")
    monkeypatch.setenv("HTTPS_PROXY", "http://ambient-proxy.fixture.invalid/")
    monkeypatch.setenv("ALL_PROXY", "socks5://ambient-proxy.fixture.invalid/")

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            headers={
                "content-type": "text/plain; charset=UTF-8",
                "content-length": str(len(body)),
                "set-cookie": "session=must-not-propagate",
            },
            content=body,
            request=request,
        )

    outcome = await _fetch_with_mock_transport(
        source_request(),
        httpx.MockTransport(handler),
    )

    assert outcome.kind is SourceFetchOutcomeKind.SUCCESS
    assert len(seen) == 1
    assert seen[0].method == "GET"
    assert str(seen[0].url) == AUTHORIZED_SOURCE_URLS["palworld-server-guide"]
    assert seen[0].content == b""
    assert "authorization" not in seen[0].headers
    assert "proxy-authorization" not in seen[0].headers
    assert "cookie" not in seen[0].headers
    assert seen[0].headers["accept-encoding"] == "identity"
    assert not hasattr(outcome, "body")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (
            httpx.Response(302, headers={"location": "https://redirect.fixture.invalid/"}),
            SourceFetchOutcomeKind.REDIRECT_REJECTED,
        ),
        (
            httpx.Response(
                200,
                headers={
                    "location": "https://redirect.fixture.invalid/",
                    "content-type": "text/plain",
                },
                content=b"synthetic",
            ),
            SourceFetchOutcomeKind.REDIRECT_REJECTED,
        ),
        (httpx.Response(201, content=b"synthetic"), SourceFetchOutcomeKind.UNAVAILABLE),
        (
            httpx.Response(
                200,
                headers={"content-type": "application/json"},
                content=b"{}",
            ),
            SourceFetchOutcomeKind.CONTENT_TYPE_REJECTED,
        ),
        (
            httpx.Response(
                200,
                headers={"content-type": "text/plain;;charset=utf-8"},
                content=b"synthetic",
            ),
            SourceFetchOutcomeKind.CONTENT_TYPE_REJECTED,
        ),
        (
            httpx.Response(
                200,
                headers={"content-type": 'text/plain; charset="utf-8'},
                content=b"synthetic",
            ),
            SourceFetchOutcomeKind.CONTENT_TYPE_REJECTED,
        ),
        (
            httpx.Response(
                200,
                headers={"content-type": "text/plain; charset=utf-8; extra=x"},
                content=b"synthetic",
            ),
            SourceFetchOutcomeKind.CONTENT_TYPE_REJECTED,
        ),
        (
            httpx.Response(
                200,
                headers={
                    "content-type": "text/plain",
                    "content-length": str(2 * 1024 * 1024 + 1),
                },
            ),
            SourceFetchOutcomeKind.RESPONSE_TOO_LARGE,
        ),
        (
            httpx.Response(
                200,
                headers={"content-type": "text/plain"},
                content=b"\xff",
            ),
            SourceFetchOutcomeKind.MALFORMED_ENCODING,
        ),
        (
            httpx.Response(
                200,
                headers={"content-type": "text/plain", "content-length": "99"},
                content=b"short",
            ),
            SourceFetchOutcomeKind.UNAVAILABLE,
        ),
        (
            httpx.Response(
                200,
                headers=[
                    ("content-type", "text/plain"),
                    ("etag", '"first"'),
                    ("etag", '"second"'),
                ],
                content=b"synthetic",
            ),
            SourceFetchOutcomeKind.UNAVAILABLE,
        ),
        (
            httpx.Response(
                200,
                headers={"content-type": "text/plain"},
                content=b"",
            ),
            SourceFetchOutcomeKind.UNAVAILABLE,
        ),
    ],
)
async def test_http_transport_fail_closed_response_classification(
    response: httpx.Response,
    expected: SourceFetchOutcomeKind,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        response.request = request
        return response

    outcome = await _fetch_with_mock_transport(
        source_request(),
        httpx.MockTransport(handler),
    )

    assert outcome.kind is expected


@pytest.mark.anyio
async def test_connect_timeout_and_read_failures_are_sanitized() -> None:
    error_types = (
        (httpx.ConnectError, SourceFetchOutcomeKind.NETWORK_RESTRICTED),
        (httpx.ReadTimeout, SourceFetchOutcomeKind.TIMEOUT),
        (httpx.ReadError, SourceFetchOutcomeKind.UNAVAILABLE),
    )
    for error_type, expected in error_types:

        def handler(
            request: httpx.Request,
            error_type: type[httpx.RequestError] = error_type,
        ) -> httpx.Response:
            raise error_type("private machine detail", request=request)

        outcome = await _fetch_with_mock_transport(
            source_request(),
            httpx.MockTransport(handler),
        )
        assert outcome == SourceFetchFailure(expected)
        assert "private machine detail" not in repr(outcome)


class NeverClosingStream(httpx.AsyncByteStream):
    release = Event()

    async def __aiter__(self):
        if False:
            yield b""

    async def aclose(self) -> None:
        while not self.release.is_set():
            await asyncio.sleep(0.01)


class NeverReadingStream(httpx.AsyncByteStream):
    async def __aiter__(self):
        await asyncio.Event().wait()
        if False:
            yield b""

    async def aclose(self) -> None:
        return


class ChunkedStream(httpx.AsyncByteStream):
    def __init__(self, chunks: tuple[bytes, ...]) -> None:
        self._chunks = chunks

    async def __aiter__(self):
        for chunk in self._chunks:
            yield chunk

    async def aclose(self) -> None:
        return


@pytest.mark.anyio
async def test_established_status_is_not_delayed_by_never_settling_cleanup() -> None:
    NeverClosingStream.release.clear()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, stream=NeverClosingStream(), request=request)

    with anyio.fail_after(0.2):
        outcome = await _fetch_with_mock_transport(
            source_request(),
            httpx.MockTransport(handler),
        )
    NeverClosingStream.release.set()

    assert outcome.kind is SourceFetchOutcomeKind.UNAVAILABLE


@pytest.mark.anyio
async def test_outer_wall_timeout_bounds_a_stalled_stream() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/plain"},
            stream=NeverReadingStream(),
            request=request,
        )

    request = OfficialSourceFetchRequest(
        source_id="palworld-server-guide",
        canonical_url=AUTHORIZED_SOURCE_URLS["palworld-server-guide"],
        timeout_seconds=0.1,
    )
    with anyio.fail_after(0.3):
        outcome = await _fetch_with_mock_transport(
            request,
            httpx.MockTransport(handler),
        )

    assert outcome.kind is SourceFetchOutcomeKind.TIMEOUT


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("chunks", "expected"),
    [
        ((b"123", b"45"), SourceFetchOutcomeKind.RESPONSE_TOO_LARGE),
        ((b"\xe2", b"\x28\xa1"), SourceFetchOutcomeKind.MALFORMED_ENCODING),
    ],
)
async def test_streamed_boundaries_are_fail_closed(
    chunks: tuple[bytes, ...],
    expected: SourceFetchOutcomeKind,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/plain"},
            stream=ChunkedStream(chunks),
            request=request,
        )

    request = OfficialSourceFetchRequest(
        source_id="palworld-server-guide",
        canonical_url=AUTHORIZED_SOURCE_URLS["palworld-server-guide"],
        max_response_bytes=4,
    )
    outcome = await _fetch_with_mock_transport(
        request,
        httpx.MockTransport(handler),
    )

    assert outcome.kind is expected


@pytest.mark.anyio
async def test_mock_acquisition_is_deterministic_mixed_and_content_free() -> None:
    registry = load_official_source_registry(registry_path())

    async def acquire():
        return await OfficialSourceAcquisitionService(
            registry=registry,
            transport=DeterministicMockOfficialSourceTransport(),
            clock=DeterministicMockClock(),
            mode=SnapshotAcquisitionMode.SYNTHETIC_MOCK,
        ).acquire()

    first = await acquire()
    second = await acquire()

    assert first == second
    assert first.manifest_sha256 == second.manifest_sha256
    assert len(first.records) == 9
    assert {record.outcome for record in first.records} == set(SourceFetchOutcomeKind)
    serialized = json.dumps(snapshot_manifest_document(first), sort_keys=True)
    assert "PALNAVI SYNTHETIC TRANSPORT FIXTURE" not in serialized
    assert "NOT PALWORLD KNOWLEDGE" not in serialized
    assert '"content_persisted": true' not in serialized
    assert all(not record.content_persisted for record in first.records)


@pytest.mark.anyio
async def test_manifest_requires_exact_registered_source_coverage() -> None:
    registry = load_official_source_registry(registry_path())
    manifest = await OfficialSourceAcquisitionService(
        registry=registry,
        transport=DeterministicMockOfficialSourceTransport(),
        clock=DeterministicMockClock(),
        mode=SnapshotAcquisitionMode.SYNTHETIC_MOCK,
    ).acquire()

    with pytest.raises(ValueError):
        replace(manifest, records=manifest.records[:-1])


@pytest.mark.anyio
async def test_acquisition_continues_after_unexpected_transport_failure() -> None:
    registry = load_official_source_registry(registry_path())

    class ThrowingTransport:
        calls = 0

        async def fetch(self, request: OfficialSourceFetchRequest):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("private detail")
            return SourceFetchFailure(SourceFetchOutcomeKind.UNAVAILABLE)

    transport = ThrowingTransport()
    manifest = await OfficialSourceAcquisitionService(
        registry=registry,
        transport=transport,
        clock=DeterministicMockClock(),
        mode=SnapshotAcquisitionMode.SYNTHETIC_MOCK,
    ).acquire()

    assert transport.calls == 9
    assert len(manifest.records) == 9
    assert all(record.outcome is SourceFetchOutcomeKind.UNAVAILABLE for record in manifest.records)


@pytest.mark.anyio
async def test_acquisition_rejects_mismatched_success_metadata() -> None:
    registry = load_official_source_registry(registry_path())

    class MismatchedTransport:
        async def fetch(self, request: OfficialSourceFetchRequest):
            return SourceFetchSuccess(
                kind=SourceFetchOutcomeKind.SUCCESS,
                metadata=SanitizedResponseMetadata(
                    status_code=200,
                    media_type="text/plain",
                    etag=None,
                    last_modified=None,
                    final_url="https://unexpected.fixture.invalid/",
                ),
                response_bytes=1,
                content_sha256=hashlib.sha256(b"x").hexdigest(),
            )

    manifest = await OfficialSourceAcquisitionService(
        registry=registry,
        transport=MismatchedTransport(),
        clock=DeterministicMockClock(),
        mode=SnapshotAcquisitionMode.SYNTHETIC_MOCK,
    ).acquire()

    assert all(record.outcome is SourceFetchOutcomeKind.UNAVAILABLE for record in manifest.records)
    assert all(record.final_url is None for record in manifest.records)


@pytest.mark.anyio
async def test_snapshot_writer_is_atomic_and_refuses_overwrite_and_symlink(
    tmp_path: Path,
) -> None:
    registry = load_official_source_registry(registry_path())
    manifest = await OfficialSourceAcquisitionService(
        registry=registry,
        transport=DeterministicMockOfficialSourceTransport(),
        clock=DeterministicMockClock(),
        mode=SnapshotAcquisitionMode.SYNTHETIC_MOCK,
    ).acquire()
    output = tmp_path / "snapshot.json"

    write_snapshot_manifest(output, manifest)
    original = output.read_bytes()
    assert output.stat().st_mode & 0o777 == 0o600
    with pytest.raises(SnapshotWriteError):
        write_snapshot_manifest(output, manifest)
    assert output.read_bytes() == original
    write_snapshot_manifest(output, manifest, replace=True)
    assert output.read_bytes() == original
    with pytest.raises(SnapshotWriteError):
        write_snapshot_manifest(
            output,
            replace(manifest, manifest_sha256="f" * 64),
            replace=True,
        )
    assert output.read_bytes() == original
    wrong_registry = replace(
        manifest,
        registry_sha256="e" * 64,
        manifest_sha256="f" * 64,
    )
    wrong_registry = replace(
        wrong_registry,
        manifest_sha256=snapshot_manifest_sha256(wrong_registry),
    )
    with pytest.raises(SnapshotWriteError):
        write_snapshot_manifest(output, wrong_registry, replace=True)
    assert output.read_bytes() == original

    link = tmp_path / "link.json"
    link.symlink_to(output)
    with pytest.raises(SnapshotWriteError):
        write_snapshot_manifest(link, manifest, replace=True)
    assert output.read_bytes() == original


def test_cli_defaults_to_mock_and_prints_only_sanitized_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "cli-snapshot.json"

    exit_code = snapshot_cli(["--output", str(output)])
    captured = capsys.readouterr()

    assert exit_code == 0
    summary = json.loads(captured.out)
    assert summary["mode"] == "synthetic_mock"
    assert summary["record_count"] == 9
    assert set(summary["outcomes"]) == {kind.value for kind in SourceFetchOutcomeKind}
    assert captured.err == ""
    assert str(output) not in captured.out
    assert "fixture_locator" not in captured.out
    document = json.loads(output.read_text(encoding="utf-8"))
    assert document["manifest_sha256"] == summary["manifest_sha256"]
    assert all(record["content_persisted"] is False for record in document["records"])


def test_cli_refuses_relative_non_json_and_existing_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert snapshot_cli(["--output", "relative.json"]) == 2
    assert snapshot_cli(["--output", str(tmp_path / "snapshot.txt")]) == 2
    output = tmp_path / "snapshot.json"
    output.write_text("owned", encoding="utf-8")
    assert snapshot_cli(["--output", str(output)]) == 2
    assert output.read_text(encoding="utf-8") == "owned"
    assert "failed safely" in capsys.readouterr().err


def test_repository_candidates_contain_no_snapshot_body_or_unauthorized_artifact() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    changed_candidates = [
        repository_root / "README.md",
        repository_root / "config" / "official-sources-v1.json",
        repository_root / "docs" / "architecture.md",
        repository_root / "docs" / "knowledge-retrieval.md",
        repository_root / "docs" / "official-sources.md",
        repository_root
        / "backend"
        / "src"
        / "palnavi"
        / "application"
        / "official_source_acquisition.py",
        *(repository_root / "backend" / "src" / "palnavi" / "domain" / "official_sources").glob(
            "*.py"
        ),
        *(
            repository_root / "backend" / "src" / "palnavi" / "infrastructure" / "official_sources"
        ).glob("*.py"),
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in changed_candidates)

    assert "technology-ID table" not in text
    assert "Authorization: Basic" not in text
    assert "api_key" not in text
    assert "sitemap" not in text
    assert "browser automation" not in text
    assert ".env" not in text
