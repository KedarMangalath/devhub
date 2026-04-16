from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from code_review_graph.tools._common import _get_store
from code_review_graph.tools.analysis_tools import (
    get_bridge_nodes_func,
    get_hub_nodes_func,
    get_knowledge_gaps_func,
)
from code_review_graph.tools.build import build_or_update_graph
from code_review_graph.tools.community_tools import (
    get_architecture_overview_func,
    list_communities_func,
)
from code_review_graph.tools.flows_tools import get_flow, list_flows
from code_review_graph.tools.query import (
    get_impact_radius,
    query_graph,
    semantic_search_nodes,
)

logger = logging.getLogger(__name__)


def build_graph(workspace_path: Path):
    graph_dir = workspace_path / ".code-review-graph"
    graph_dir.mkdir(parents=True, exist_ok=True)
    build_or_update_graph(full_rebuild=True, repo_root=str(workspace_path), postprocess="full")
    store, _root = _get_store(str(workspace_path))
    return store


def extract_architecture(repo_root: Path) -> dict[str, Any]:
    architecture = get_architecture_overview_func(repo_root=str(repo_root))
    communities = architecture.get("communities") or []
    layers = [str(item.get("name") or "") for item in communities[:6] if str(item.get("name") or "").strip()]
    return {
        "summary": str(architecture.get("summary") or ""),
        "communities": communities,
        "layers": layers,
        "warnings": architecture.get("warnings") or [],
        "cross_community_edges": architecture.get("cross_community_edges") or [],
    }


def extract_components(repo_root: Path) -> list[dict[str, Any]]:
    hub_nodes = list((get_hub_nodes_func(repo_root=str(repo_root), top_n=10) or {}).get("hub_nodes") or [])
    bridge_nodes = list((get_bridge_nodes_func(repo_root=str(repo_root), top_n=10) or {}).get("bridge_nodes") or [])
    components: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for node in hub_nodes + bridge_nodes:
        name = str(node.get("name") or node.get("qualified_name") or "").strip()
        file_path = str(node.get("file_path") or "").strip()
        key = (name, file_path)
        if not name or key in seen:
            continue
        seen.add(key)
        components.append(
            {
                "name": name,
                "file_path": file_path,
                "purpose": "Graph-identified hub or bridge node in the codebase structure.",
                "complexity": "high",
                "dependencies": [],
                "exports": str(node.get("kind") or ""),
                "lines_estimate": _line_estimate(node),
            }
        )
    return components


def extract_flows(repo_root: Path) -> list[dict[str, Any]]:
    flow_listing = list_flows(repo_root=str(repo_root), limit=5, detail_level="standard")
    flows: list[dict[str, Any]] = []
    for item in flow_listing.get("flows") or []:
        flow_id = item.get("id")
        if flow_id is None:
            continue
        detailed = get_flow(flow_id=int(flow_id), include_source=False, repo_root=str(repo_root))
        flow = detailed.get("flow") or {}
        steps = flow.get("steps") or []
        touchpoints = []
        for step in steps:
            file_name = str(step.get("file") or "").strip()
            function_name = str(step.get("name") or "").strip()
            if function_name and file_name:
                touchpoints.append(f"{function_name} ({file_name})")
            elif function_name:
                touchpoints.append(function_name)
        flows.append(
            {
                "title": str(flow.get("name") or item.get("name") or "Execution flow"),
                "description": f"Criticality {flow.get('criticality') or item.get('criticality')}; {len(steps)} step(s) in graph trace.",
                "mermaid_sequence": _flow_mermaid(flow),
                "touchpoints": touchpoints[:10],
            }
        )
    return flows


def extract_communities(repo_root: Path) -> list[dict[str, Any]]:
    listing = list_communities_func(repo_root=str(repo_root), min_size=1, detail_level="standard")
    repository_map: list[dict[str, Any]] = []
    for community in listing.get("communities") or []:
        repository_map.append(
            {
                "area": str(community.get("name") or "Community"),
                "description": (
                    f"Graph community with {community.get('size') or 0} nodes, "
                    f"cohesion {community.get('cohesion') or 0}, "
                    f"language {community.get('dominant_language') or 'unknown'}."
                ),
                "important_files": list(community.get("top_files") or community.get("files") or [])[:8],
                "relationships": [str(item) for item in (community.get("external_dependencies") or [])[:6]],
            }
        )
    return repository_map


def extract_knowledge_gaps(repo_root: Path) -> list[str]:
    gaps = get_knowledge_gaps_func(repo_root=str(repo_root))
    gap_payload = gaps.get("gaps") or {}
    lines: list[str] = []
    if gap_payload.get("isolated_nodes"):
        lines.append(f"Isolated nodes: {len(gap_payload.get('isolated_nodes') or [])}")
    if gap_payload.get("thin_communities"):
        lines.append(f"Thin communities: {len(gap_payload.get('thin_communities') or [])}")
    if gap_payload.get("untested_hotspots"):
        lines.append(f"Untested hotspots: {len(gap_payload.get('untested_hotspots') or [])}")
    if gap_payload.get("single_file_communities"):
        lines.append(f"Single-file communities: {len(gap_payload.get('single_file_communities') or [])}")
    return lines


def build_graph_context(workspace_path: Path, timeout_seconds: int = 120) -> dict[str, Any]:
    """Build graph context with a timeout to prevent blocking blueprint generation."""
    try:
        store = build_graph(workspace_path)
    except Exception as e:
        logger.warning("Graph build failed (non-fatal): %s", e)
        return {}
    try:
        stats = store.get_stats()
    finally:
        store.close()

    architecture = extract_architecture(workspace_path)
    components = extract_components(workspace_path)
    flows = extract_flows(workspace_path)
    communities = extract_communities(workspace_path)
    knowledge_gaps = extract_knowledge_gaps(workspace_path)

    return {
        "architecture_overview": architecture,
        "repository_map": communities,
        "key_components": components,
        "sequence_flows": flows,
        "knowledge_gaps": knowledge_gaps,
        "graph_summary": _graph_summary_text(architecture, components, flows, communities, knowledge_gaps, stats),
        "graph_stats": {
            "files_count": stats.files_count,
            "total_nodes": stats.total_nodes,
            "total_edges": stats.total_edges,
            "languages": list(stats.languages),
            "last_updated": stats.last_updated,
        },
        "graph_context_debug": {
            "query_graph_available": bool(query_graph),
            "semantic_search_available": bool(semantic_search_nodes),
            "impact_radius_available": bool(get_impact_radius),
        },
    }


def _line_estimate(node: dict[str, Any]) -> str:
    line_start = node.get("line_start")
    line_end = node.get("line_end")
    if isinstance(line_start, int) and isinstance(line_end, int) and line_end >= line_start:
        return str(line_end - line_start + 1)
    return ""


def _flow_mermaid(flow: dict[str, Any]) -> str:
    steps = flow.get("steps") or []
    lines = ["sequenceDiagram"]
    if not steps:
        return "\n".join(lines)
    for index, step in enumerate(steps):
        actor = f"Step{index + 1}"
        next_actor = f"Step{index + 2}" if index + 1 < len(steps) else "Result"
        name = str(step.get("name") or step.get("qualified_name") or "step")
        lines.append(f"    participant {actor} as {name}")
        if index + 1 < len(steps):
            next_name = str(steps[index + 1].get("name") or steps[index + 1].get("qualified_name") or "step")
            lines.append(f"    {actor}->>{next_actor}: {next_name}")
    return "\n".join(lines)


def _graph_summary_text(
    architecture: dict[str, Any],
    components: list[dict[str, Any]],
    flows: list[dict[str, Any]],
    communities: list[dict[str, Any]],
    knowledge_gaps: list[str],
    stats: Any,
) -> str:
    is_large = getattr(stats, "files_count", 0) > 2000
    lines = [
        f"Graph stats: {stats.total_nodes} nodes, {stats.total_edges} edges, {stats.files_count} files.",
        f"Architecture: {architecture.get('summary') or 'Not available.'}",
    ]
    if architecture.get("layers"):
        lines.append("Layers: " + ", ".join(str(item) for item in architecture.get("layers") or []))
    if components:
        comp_lines = []
        for item in components[:10]:
            name = item.get("name") or ""
            fp = item.get("file_path") or ""
            comp_lines.append(f"{name} ({fp})" if fp else name)
        lines.append("Top hub/bridge nodes: " + ", ".join(comp_lines))
    if flows:
        lines.append("Critical flows: " + ", ".join(item.get("title") or "" for item in flows[:5] if item.get("title")))
    if communities:
        if is_large:
            lines.append(f"Code communities ({len(communities)} detected):")
            for community in communities[:12]:
                area = str(community.get("area") or "Community")
                description = str(community.get("description") or "").strip()
                important_files = [str(item) for item in (community.get("important_files") or [])[:5] if str(item).strip()]
                relationships = [str(item) for item in (community.get("relationships") or [])[:4] if str(item).strip()]
                lines.append(f"  [{area}] {description}".rstrip())
                if important_files:
                    lines.append(f"    Key files: {', '.join(important_files)}")
                if relationships:
                    lines.append(f"    Depends on: {', '.join(relationships)}")
        else:
            lines.append("Communities: " + ", ".join(item.get("area") or "" for item in communities[:8] if item.get("area")))
    if knowledge_gaps:
        lines.append("Knowledge gaps: " + "; ".join(knowledge_gaps[:6]))
    return "\n".join(line for line in lines if line.strip())
