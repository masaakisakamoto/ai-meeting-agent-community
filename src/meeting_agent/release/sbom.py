from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback path
    tomllib = None  # type: ignore[assignment]

from meeting_agent.core.schemas import utc_now_iso


@dataclass
class SBOMPackage:
    name: str
    version_constraint: str = ""
    scope: str = "runtime"


@dataclass
class CommunitySBOM:
    name: str
    version: str
    generated_at: str = field(default_factory=utc_now_iso)
    format: str = "community-sbom-v0"
    packages: list[SBOMPackage] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def generate_sbom(project_root: str | Path) -> CommunitySBOM:
    root = Path(project_root)
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.is_file():
        return CommunitySBOM(name=root.name, version="0.0.0", notes=["pyproject.toml not found"])

    text = pyproject_path.read_text(encoding="utf-8")
    if tomllib is not None:
        data = tomllib.loads(text)
        project = data.get("project", {})
        name = project.get("name", root.name)
        version = project.get("version", "0.0.0")
        packages = []
        for dependency in project.get("dependencies", []) or []:
            packages.append(_package_from_requirement(dependency, "runtime"))
        for group, deps in (project.get("optional-dependencies", {}) or {}).items():
            for dependency in deps:
                packages.append(_package_from_requirement(dependency, f"optional:{group}"))
        return CommunitySBOM(
            name=name,
            version=version,
            packages=packages,
            notes=[
                "This lightweight SBOM is generated from pyproject.toml direct dependencies.",
                "For production releases, also generate a full transitive SBOM in CI.",
            ],
        )

    # Fallback parser for Python 3.10 environments without tomli.
    name = _match_value(text, "name") or root.name
    version = _match_value(text, "version") or "0.0.0"
    return CommunitySBOM(
        name=name,
        version=version,
        notes=["Fallback parser used; install Python 3.11+ or tomli for richer dependency parsing."],
    )


def write_sbom(project_root: str | Path, output: str | Path) -> CommunitySBOM:
    sbom = generate_sbom(project_root)
    Path(output).write_text(sbom.to_json(), encoding="utf-8")
    return sbom


def _package_from_requirement(requirement: str, scope: str) -> SBOMPackage:
    name = re.split(r"[<>=!~;\[]", requirement, maxsplit=1)[0].strip()
    version_constraint = requirement[len(name) :].strip()
    return SBOMPackage(name=name, version_constraint=version_constraint, scope=scope)


def _match_value(text: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}\s*=\s*[\"']([^\"']+)[\"']", text, flags=re.MULTILINE)
    return match.group(1) if match else None
