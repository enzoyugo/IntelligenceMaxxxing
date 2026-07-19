"""Import boundary tests (Constitution Art. 4-A; Technical Architecture §2).

These scan real source files, so a violation anywhere fails even if the
offending module is never imported by other tests.
"""

import ast
from pathlib import Path

from tests.conftest import REPO_ROOT

CORE_SRC = REPO_ROOT / "src" / "intelligence_maxxxing"
SDK_SRC = REPO_ROOT / "sdk" / "python" / "intelligence_maxxxing_client"

# Names of applications that are external clients of the Engine, forever.
APPLICATION_MODULE_MARKERS = (
    "lifemaxxxing",
    "life_maxxxing",
    "tradingmaxxxing",
    "trading_maxxxing",
    "betting_bot",
    "bettingbot",
    "intelligence_maxxxing_client",
)

SDK_ALLOWED_TOP_LEVEL = {
    "intelligence_maxxxing_client",
    "httpx",
    "pydantic",
    # stdlib
    "uuid",
    "typing",
    "datetime",
    "json",
    "collections",
    "abc",
    "enum",
}


def _imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def _python_files(root: Path) -> list[Path]:
    files = sorted(root.rglob("*.py"))
    assert files, f"no python files found under {root}"
    return files


def test_core_has_no_application_imports() -> None:
    violations = []
    for file in _python_files(CORE_SRC):
        for module in _imports_of(file):
            lowered = module.lower()
            if any(marker in lowered for marker in APPLICATION_MODULE_MARKERS):
                violations.append(f"{file.relative_to(REPO_ROOT)} imports {module}")
    assert not violations, "The Core must never import application code or the SDK:\n" + "\n".join(
        violations
    )


def test_sdk_uses_public_http_contract_only() -> None:
    violations = []
    for file in _python_files(SDK_SRC):
        for module in _imports_of(file):
            top_level = module.split(".")[0]
            if top_level == "intelligence_maxxxing":
                violations.append(f"{file.name} imports the Engine Core: {module}")
            elif top_level not in SDK_ALLOWED_TOP_LEVEL:
                violations.append(f"{file.name} imports unexpected module: {module}")
    assert not violations, "The SDK may only consume the public HTTP contract:\n" + "\n".join(
        violations
    )


def test_domain_has_no_fastapi_import() -> None:
    violations = [
        f"{file.relative_to(REPO_ROOT)} imports {module}"
        for file in _python_files(CORE_SRC / "domain")
        for module in _imports_of(file)
        if module.split(".")[0] in {"fastapi", "starlette"}
    ]
    assert not violations, "domain must be web-framework free:\n" + "\n".join(violations)


def test_domain_has_no_sqlalchemy_import() -> None:
    violations = [
        f"{file.relative_to(REPO_ROOT)} imports {module}"
        for file in _python_files(CORE_SRC / "domain")
        for module in _imports_of(file)
        if module.split(".")[0] in {"sqlalchemy", "alembic", "psycopg"}
    ]
    assert not violations, "domain must be persistence free:\n" + "\n".join(violations)


def test_domain_has_no_network_or_infra_import() -> None:
    forbidden = {"httpx", "requests", "socket", "urllib"}
    violations = [
        f"{file.relative_to(REPO_ROOT)} imports {module}"
        for file in _python_files(CORE_SRC / "domain")
        for module in _imports_of(file)
        if module.split(".")[0] in forbidden
        or module.startswith(("intelligence_maxxxing.infrastructure", "intelligence_maxxxing.api"))
    ]
    assert not violations, "domain must be pure:\n" + "\n".join(violations)


def test_application_layer_has_no_infrastructure_import() -> None:
    violations = [
        f"{file.relative_to(REPO_ROOT)} imports {module}"
        for file in _python_files(CORE_SRC / "application")
        for module in _imports_of(file)
        if module.split(".")[0] in {"sqlalchemy", "fastapi", "psycopg"}
        or module.startswith("intelligence_maxxxing.infrastructure")
    ]
    assert not violations, (
        "application layer depends on ports, never on concrete infrastructure:\n"
        + "\n".join(violations)
    )


def test_api_does_not_access_tables_directly() -> None:
    """API modules never import ORM tables or build SQL statements."""
    forbidden_markers = (
        "intelligence_maxxxing.infrastructure.database.tables",
        "EngineEventRow",
        "AuditRecordRow",
        "IdempotencyKeyRow",
    )
    violations = []
    for file in _python_files(CORE_SRC / "api"):
        content = file.read_text(encoding="utf-8")
        for marker in forbidden_markers:
            if marker in content:
                violations.append(f"{file.relative_to(REPO_ROOT)} references {marker}")
    assert not violations, "the API layer must go through use cases, never tables:\n" + "\n".join(
        violations
    )
