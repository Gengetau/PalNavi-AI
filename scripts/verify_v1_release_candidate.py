"""Offline, read-only verification for the PalNavi AI v1 release candidate."""

from __future__ import annotations

import ast
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

PUBLIC_VERSION = "1.0.0-rc.1"
PYTHON_PACKAGE_VERSION = "1.0.0rc1"
PROGRAM_ID = "palnavi-ai-v1"
DATASET_ID = "palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47"
DATASET_DIGEST = "b7fbe9b7395d2aef6758ff162da8fb738cf1fcd3ec5c7d50133c3d5edafdd30b"
EXPECTED_LOCALES = (
    "de",
    "en",
    "es",
    "es-MX",
    "fr",
    "id",
    "it",
    "ja",
    "ko",
    "pl",
    "pt-BR",
    "ru",
    "th",
    "tr",
    "vi",
    "zh-Hans",
    "zh-Hant",
)
EXPECTED_API_SURFACE = {
    "/api/v1/breeding/capture-ranked-routes": ["post"],
    "/api/v1/breeding/direct": ["post"],
    "/api/v1/breeding/gender-aware-routes": ["post"],
    "/api/v1/breeding/routes": ["post"],
    "/api/v1/knowledge/explain": ["post"],
    "/api/v1/knowledge/search": ["post"],
    "/api/v1/palworld/species-catalog": ["get"],
    "/health": ["get"],
}
EXPECTED_CAPABILITIES = [
    "versioned structured data with provenance",
    "deterministic synthetic breeding routes",
    "production direct breeding lookup",
    "production gender-aware routes from manual owned inventory",
    "production minimum-new-capture routes from explicit user candidates",
    "localized presentation catalog with stable submitted IDs",
    "synthetic local knowledge search",
    "optional retrieval-first citation-grounded synthetic explanation",
    "official-source registry and bounded metadata-only fingerprinting",
    "local FastAPI and standalone Vue source workflows",
]
EXPECTED_UNSUPPORTED = [
    "production Palworld knowledge prose",
    "catchability or encounter availability",
    "map locations or capture difficulty",
    "probability-weighted breeding attempts",
    "cake, incubation, or elapsed-time costs",
    "passive-skill or individual-value planning",
    "automatic game or save integration",
    "gameplay or multiplayer automation",
    "remote deployment",
    "installer or signed binary",
]
EXPECTED_COMMANDS = [
    "python scripts/verify_v1_release_candidate.py",
    "cd backend && python -m pytest",
    "cd backend && python -m ruff format --check .",
    "cd backend && python -m ruff check .",
    "cd backend && python -m mypy src",
    "cd frontend && npm ci",
    "cd frontend && npm run test:unit:no-network",
    "cd frontend && npm run type-check",
    "cd frontend && npm run build",
    "cd frontend && npm audit --audit-level=high",
    "git diff --check",
]
HTTP_METHODS = {"delete", "get", "head", "options", "patch", "post", "put", "trace"}


class VerificationError(Exception):
    """Release-candidate drift that must fail closed."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise VerificationError([f"{path.name}: expected a JSON object"])
    return value


def _literal_assignment(path: Path, name: str) -> str | None:
    module = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return node.value.value
    return None


def _expect(errors: list[str], label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        errors.append(f"{label}: expected {expected!r}, got {actual!r}")


def _expect_keys(
    errors: list[str],
    label: str,
    value: dict[str, Any],
    expected: set[str],
) -> None:
    _expect(errors, f"{label} keys", set(value), expected)


def _load_runtime_api(root: Path) -> tuple[str, dict[str, list[str]]]:
    backend_source = str(root / "backend" / "src")
    if backend_source not in sys.path:
        sys.path.insert(0, backend_source)
    from palnavi.api.main import app

    document = app.openapi()
    surface = {
        path: sorted(method for method in operations if method in HTTP_METHODS)
        for path, operations in document["paths"].items()
    }
    return app.version, surface


def verify(
    root: Path,
    *,
    api_version: str | None = None,
    api_surface: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Verify a candidate tree without writing to it or contacting the network."""

    root = root.resolve()
    manifest_path = root / "release" / f"v{PUBLIC_VERSION}.json"
    dataset_root = root / "datasets" / DATASET_ID
    required_paths = [
        root / "README.md",
        root / "backend" / "pyproject.toml",
        root / "backend" / "src" / "palnavi" / "__init__.py",
        root / "frontend" / "package.json",
        root / "frontend" / "package-lock.json",
        manifest_path,
        dataset_root / "manifest.json",
        dataset_root / "pals.json",
        root / "docs" / "v1-acceptance.md",
        root
        / "reports"
        / "codex"
        / "loop-016-v1-release-candidate-codex-report.md",
    ]
    missing = [
        path.relative_to(root).as_posix()
        for path in required_paths
        if not path.is_file()
    ]
    if missing:
        raise VerificationError([f"required file missing: {path}" for path in missing])

    errors: list[str] = []
    manifest = _read_json(manifest_path)
    _expect_keys(
        errors,
        "release manifest",
        manifest,
        {
            "schema",
            "program_id",
            "product",
            "distribution",
            "runtime",
            "supported_data",
            "api_surface",
            "supported_capabilities",
            "unsupported_capabilities",
            "verification",
            "acceptance",
        },
    )
    _expect(errors, "manifest schema", manifest.get("schema"), "palnavi-release-candidate/v1")
    _expect(errors, "program ID", manifest.get("program_id"), PROGRAM_ID)

    product = manifest.get("product")
    if not isinstance(product, dict):
        errors.append("product: expected an object")
        product = {}
    _expect_keys(
        errors,
        "product",
        product,
        {
            "name",
            "public_version",
            "python_distribution",
            "python_package_version",
            "release_stage",
        },
    )
    _expect(errors, "product name", product.get("name"), "PalNavi AI")
    _expect(errors, "public version", product.get("public_version"), PUBLIC_VERSION)
    _expect(errors, "Python distribution", product.get("python_distribution"), "palnavi")
    _expect(
        errors,
        "Python package version",
        product.get("python_package_version"),
        PYTHON_PACKAGE_VERSION,
    )
    _expect(errors, "release stage", product.get("release_stage"), "release-candidate")

    distribution = manifest.get("distribution")
    expected_distribution = {
        "mode": "source-checkout",
        "deployment": "local-advisory",
        "remote_deployment": False,
        "installer": False,
        "signed_binary": False,
        "final_release": False,
    }
    _expect(errors, "distribution", distribution, expected_distribution)

    runtime = manifest.get("runtime")
    expected_runtime = {
        "python": ">=3.12",
        "node": "^22.18.0 || >=24.12.0",
        "npm": ">=11.9.0 <12",
        "api_module": "palnavi.api.main:app",
        "frontend_package": "frontend",
    }
    _expect(errors, "runtime", runtime, expected_runtime)

    supported_data = manifest.get("supported_data")
    if not isinstance(supported_data, dict):
        errors.append("supported_data: expected an object")
        supported_data = {}
    _expect_keys(
        errors,
        "supported_data",
        supported_data,
        {
            "dataset_id",
            "content_identity",
            "pal_records",
            "breeding_outcomes",
            "source_snapshot",
            "independently_verified_compatible_patch",
            "presentation_locales",
            "production_knowledge_prose",
        },
    )
    _expect(errors, "supported dataset ID", supported_data.get("dataset_id"), DATASET_ID)
    _expect(
        errors,
        "supported content identity",
        supported_data.get("content_identity"),
        {"algorithm": "sha256", "digest": DATASET_DIGEST},
    )
    _expect(errors, "supported Pal count", supported_data.get("pal_records"), 299)
    _expect(errors, "supported outcome count", supported_data.get("breeding_outcomes"), 44851)
    _expect(errors, "source snapshot", supported_data.get("source_snapshot"), "v1.0.0")
    _expect(
        errors,
        "compatible patch",
        supported_data.get("independently_verified_compatible_patch"),
        "v1.0.1",
    )
    _expect(
        errors,
        "presentation locales",
        supported_data.get("presentation_locales"),
        list(EXPECTED_LOCALES),
    )
    _expect(
        errors,
        "production knowledge prose",
        supported_data.get("production_knowledge_prose"),
        False,
    )
    _expect(errors, "manifest API surface", manifest.get("api_surface"), EXPECTED_API_SURFACE)
    _expect(
        errors,
        "supported capabilities",
        manifest.get("supported_capabilities"),
        EXPECTED_CAPABILITIES,
    )
    _expect(
        errors,
        "unsupported capabilities",
        manifest.get("unsupported_capabilities"),
        EXPECTED_UNSUPPORTED,
    )

    verification = manifest.get("verification")
    if not isinstance(verification, dict):
        errors.append("verification: expected an object")
        verification = {}
    _expect(
        errors,
        "verification",
        verification,
        {
            "entrypoint": "scripts/verify_v1_release_candidate.py",
            "network_required": False,
            "commands": EXPECTED_COMMANDS,
        },
    )
    acceptance = manifest.get("acceptance")
    _expect(
        errors,
        "acceptance",
        acceptance,
        {
            "document": "docs/v1-acceptance.md",
            "codex_report": "reports/codex/loop-016-v1-release-candidate-codex-report.md",
            "receipt_contract": "agent-loop-business-receipt/v2",
            "exact_head_bound_by_receipt": True,
            "human_owner_decision_required": True,
        },
    )

    pyproject = tomllib.loads(
        (root / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    )
    _expect(
        errors,
        "pyproject version",
        pyproject.get("project", {}).get("version"),
        PYTHON_PACKAGE_VERSION,
    )
    runtime_version = _literal_assignment(
        root / "backend" / "src" / "palnavi" / "__init__.py",
        "__version__",
    )
    _expect(errors, "runtime package version", runtime_version, PUBLIC_VERSION)
    frontend = _read_json(root / "frontend" / "package.json")
    _expect(errors, "frontend package version", frontend.get("version"), PUBLIC_VERSION)
    lockfile = _read_json(root / "frontend" / "package-lock.json")
    _expect(errors, "frontend lockfile version", lockfile.get("version"), PUBLIC_VERSION)
    lock_root = lockfile.get("packages", {}).get("")
    if not isinstance(lock_root, dict):
        errors.append("frontend lockfile root package: expected an object")
        lock_root = {}
    _expect(errors, "frontend lockfile root version", lock_root.get("version"), PUBLIC_VERSION)

    dataset = _read_json(dataset_root / "manifest.json")
    _expect(errors, "dataset ID", dataset.get("dataset_id"), DATASET_ID)
    _expect(
        errors,
        "dataset content identity",
        dataset.get("content_identity"),
        {"algorithm": "sha256", "digest": DATASET_DIGEST},
    )
    counts = dataset.get("counts")
    if not isinstance(counts, dict):
        errors.append("dataset counts: expected an object")
        counts = {}
    _expect(errors, "dataset Pal count", counts.get("pal_records"), 299)
    _expect(errors, "dataset outcome count", counts.get("source_derived_outcomes"), 44851)
    scope = dataset.get("game_version_scope")
    if not isinstance(scope, dict):
        errors.append("dataset game-version scope: expected an object")
        scope = {}
    _expect(errors, "dataset source snapshot", scope.get("source_snapshot"), "v1.0.0")
    _expect(
        errors,
        "dataset compatible patch",
        scope.get("independently_verified_compatible_patch"),
        "v1.0.1",
    )

    pals = _read_json(dataset_root / "pals.json")
    records = pals.get("records")
    if not isinstance(records, list):
        errors.append("pals records: expected an array")
        records = []
    _expect(errors, "pals record count", len(records), 299)
    locale_sets = {
        tuple(sorted(record.get("localized_names", {})))
        for record in records
        if isinstance(record, dict)
    }
    _expect(errors, "dataset locale sets", locale_sets, {tuple(EXPECTED_LOCALES)})

    if api_version is None or api_surface is None:
        api_version, api_surface = _load_runtime_api(root)
    _expect(errors, "OpenAPI product version", api_version, PUBLIC_VERSION)
    _expect(errors, "runtime API surface", api_surface, EXPECTED_API_SURFACE)

    if errors:
        raise VerificationError(errors)
    return {
        "acceptance_document": "docs/v1-acceptance.md",
        "api_routes": sorted(EXPECTED_API_SURFACE),
        "dataset": {
            "content_sha256": DATASET_DIGEST,
            "id": DATASET_ID,
            "pal_records": 299,
            "breeding_outcomes": 44851,
        },
        "distribution": "source-checkout",
        "network_required": False,
        "product_version": PUBLIC_VERSION,
        "python_package_version": PYTHON_PACKAGE_VERSION,
        "status": "verified",
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        result = verify(root)
    except (OSError, ValueError, VerificationError) as error:
        errors = error.errors if isinstance(error, VerificationError) else [str(error)]
        print(
            json.dumps({"errors": errors, "status": "failed"}, sort_keys=True),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
