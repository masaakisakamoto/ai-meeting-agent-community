from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Optional


@dataclass(frozen=True)
class PluginMetadata:
    id: str
    name: str
    version: str = "0.1.0"
    kind: str = "generic"
    description: str = ""
    capabilities: tuple[str, ...] = field(default_factory=tuple)


class PluginRegistry:
    """Small registry used by Community plugins and private modules alike."""

    def __init__(self) -> None:
        self._plugins: Dict[str, tuple[PluginMetadata, Any]] = {}

    def register(self, metadata: PluginMetadata, plugin: Any) -> None:
        if metadata.id in self._plugins:
            raise ValueError(f"Plugin already registered: {metadata.id}")
        self._plugins[metadata.id] = (metadata, plugin)

    def get(self, plugin_id: str) -> Any:
        try:
            return self._plugins[plugin_id][1]
        except KeyError as exc:
            raise KeyError(f"Plugin not found: {plugin_id}") from exc

    def metadata(self, plugin_id: str) -> PluginMetadata:
        try:
            return self._plugins[plugin_id][0]
        except KeyError as exc:
            raise KeyError(f"Plugin not found: {plugin_id}") from exc

    def list(self, kind: Optional[str] = None) -> list[PluginMetadata]:
        values = [meta for meta, _ in self._plugins.values()]
        if kind:
            values = [meta for meta in values if meta.kind == kind]
        return sorted(values, key=lambda m: m.id)

    def has(self, plugin_id: str) -> bool:
        return plugin_id in self._plugins


def build_default_registry() -> PluginRegistry:
    from meeting_agent.exporters.markdown import MarkdownExporter
    from meeting_agent.exporters.html import HTMLExporter
    from meeting_agent.exporters.csv_exporter import ActionItemCSVExporter
    from meeting_agent.intelligence.rule_minutes import RuleBasedMinutesGenerator
    from meeting_agent.intelligence.verifier import MinutesVerifier

    registry = PluginRegistry()
    registry.register(
        PluginMetadata(
            id="generator.rule_based_ja",
            name="Rule-based Japanese Minutes Generator",
            kind="minutes_generator",
            capabilities=("decisions", "action_items", "open_questions", "risks", "evidence"),
        ),
        RuleBasedMinutesGenerator(),
    )
    registry.register(
        PluginMetadata(
            id="verifier.basic_grounding",
            name="Basic Grounding Verifier",
            kind="verifier",
            capabilities=("evidence_check", "overlap_check"),
        ),
        MinutesVerifier(),
    )
    registry.register(
        PluginMetadata(
            id="export.markdown",
            name="Markdown Exporter",
            kind="exporter",
            capabilities=("minutes", "evidence"),
        ),
        MarkdownExporter(),
    )
    registry.register(
        PluginMetadata(
            id="export.html",
            name="Evidence-linked HTML Exporter",
            kind="exporter",
            capabilities=("minutes", "evidence", "transcript_anchor_links"),
        ),
        HTMLExporter(),
    )
    registry.register(
        PluginMetadata(
            id="export.action_items_csv",
            name="Action Item CSV Exporter",
            kind="exporter",
            capabilities=("action_items", "csv", "evidence"),
        ),
        ActionItemCSVExporter(),
    )
    return registry
