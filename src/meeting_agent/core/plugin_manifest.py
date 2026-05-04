from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

PluginKind = Literal[
    "asr_provider",
    "llm_provider",
    "minutes_generator",
    "verifier",
    "exporter",
    "integration",
    "template",
    "storage",
    "agent_action",
    "compliance",
]

_ALLOWED_KINDS = {
    "asr_provider",
    "llm_provider",
    "minutes_generator",
    "verifier",
    "exporter",
    "integration",
    "template",
    "storage",
    "agent_action",
    "compliance",
}

_PLUGIN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,80}$")
_SEMVERISH_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9_.-]+)?$")
_PERMISSIVE_LICENSES = {"Apache-2.0", "MIT", "BSD-3-Clause", "BSD-2-Clause", "ISC"}


@dataclass(frozen=True)
class PluginPermission:
    """Declared permission requested by a plugin.

    The Community edition records permissions but does not yet sandbox plugins at
    runtime. The manifest is intentionally explicit so a future desktop shell,
    marketplace, or hosted platform can enforce it.
    """

    name: str
    reason: str = ""


@dataclass(frozen=True)
class PluginManifest:
    """Public plugin manifest used by Community and commercial plugins."""

    id: str
    name: str
    version: str
    kind: PluginKind
    entrypoint: str
    license: str
    description: str = ""
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    permissions: tuple[PluginPermission, ...] = field(default_factory=tuple)
    min_app_version: str = "0.7.0"
    api_version: str = "0.3"
    source_url: str | None = None
    requires_private_core: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self, *, community_only: bool = False) -> list[str]:
        return validate_plugin_manifest(self, community_only=community_only)


def manifest_from_dict(data: dict[str, Any]) -> PluginManifest:
    payload = dict(data)
    payload["capabilities"] = tuple(str(x) for x in payload.get("capabilities", ()))
    payload["permissions"] = tuple(
        PluginPermission(**permission) for permission in payload.get("permissions", ())
    )
    return PluginManifest(**payload)


def load_manifest(path: str | Path) -> PluginManifest:
    manifest = manifest_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
    errors = manifest.validate()
    if errors:
        raise ValueError("Invalid plugin manifest: " + "; ".join(errors))
    return manifest


def load_plugin_manifest(path: str | Path) -> PluginManifest:
    return load_manifest(path)


def save_manifest(manifest: PluginManifest, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def validate_plugin_manifest(manifest: PluginManifest, *, community_only: bool = False) -> list[str]:
    errors: list[str] = []
    if not _PLUGIN_ID_RE.match(manifest.id):
        errors.append("id must be lowercase and contain only letters, numbers, dots, underscores, or hyphens")
    if not manifest.name.strip():
        errors.append("name is required")
    if not _SEMVERISH_RE.match(manifest.version):
        errors.append("version must be semver-like, for example 0.2.0")
    if manifest.kind not in _ALLOWED_KINDS:
        errors.append(f"kind must be one of: {', '.join(sorted(_ALLOWED_KINDS))}")
    if not manifest.entrypoint.strip() or ":" not in manifest.entrypoint:
        errors.append("entrypoint must use module.path:object format")
    if not manifest.license.strip():
        errors.append("license is required")
    if community_only and manifest.license not in _PERMISSIVE_LICENSES:
        errors.append("community-only plugins should use a permissive license")
    if community_only and manifest.requires_private_core:
        errors.append("community-only plugins must not require private core access")
    seen_permissions: set[str] = set()
    for permission in manifest.permissions:
        if not permission.name.strip():
            errors.append("permission name must not be empty")
        if permission.name in seen_permissions:
            errors.append(f"duplicate permission: {permission.name}")
        seen_permissions.add(permission.name)
    return errors


# Backward-compatible alias.
load_plugin_manifest = load_manifest
