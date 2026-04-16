"""
BlueprintQueryAgent — Tool-based blueprint generation for codebases of any size.

Inspired by Claude Code's query.ts architecture:
- Starts with a compact codebase anchor (compact_summary + repo_tree)
- Uses Glob / Grep / FileRead tools to iteratively explore the workspace
- ToolBudget caps total reads/searches so exploration terminates predictably
- ContextCompactor auto-summarises conversation history; anchor is re-injected
  post-compact so the agent never loses codebase orientation
- For very large repos (10K+ files) a Coordinator spawns parallel workers:
    BackendWorker  — routes, models, services
    FrontendWorker — components, routing, state
    InfraWorker    — docker, CI, env config
  and synthesises their findings into the final blueprint JSON.

Routing (called from views.generate_blueprint_sync):
  workspace + usable AI  -> BlueprintQueryAgent.generate() for normal repos
  >= 10 000 total files  -> BlueprintQueryAgent.generate_parallel() for huge repos
  no workspace / no AI   -> ArchitectAgent fallback
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from agents.base import BaseAgent, normalize_ai_config
from agents.compaction import ContextCompactor  # noqa: E402 used by _AnchorAwareCompactor
from agents.prompts import PromptBuilder
from agents.query_engine import QueryEngine
from agents.tools.base_tool import ToolBudget, ToolContext
from agents.tools.file_read import FileReadTool
from agents.tools.glob_tool import GlobTool
from agents.tools.grep_tool import GrepTool
from agents.tools.list_dir import ListDirTool
from agents.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

BLUEPRINT_SYSTEM_PROMPT = """\
You are an expert software architect. Your job: explore a codebase with tools,
then generate a complete engineering blueprint JSON.

You have tools: list_dir, glob, grep, file_read.

═══════════════════════════════════════════
PHASE 1 — EXPLORE
═══════════════════════════════════════════

You are a senior engineer on day one at a new company.
You don't know the tech stack yet. Discover it yourself.

Exploration strategy:
  1. Start with list_dir(".") — always, no exceptions.
     This tells you what kind of project this is: languages, frameworks,
     monorepo vs single service, frontend vs backend vs CLI vs library.

  2. Read the key manifest/config files you see
     (go.mod, Cargo.toml, package.json, pyproject.toml, pom.xml, mix.exs,
      Gemfile, composer.json, *.csproj, Dockerfile, docker-compose.yml…)

  3. Find service boundaries — glob for manifest files if it looks like
     a monorepo (multiple services / packages).

  4. Read entry points — you know what the entry point is for the
     detected stack. Read it.

  5. Discover the API surface — use grep/glob to find route definitions,
     endpoint handlers, URL configs. You know the patterns for the framework.

  6. Discover data models — find model/schema/entity definitions.
     You know the ORM/framework conventions.

  7. Read infrastructure config — Dockerfile, CI pipelines, .env.example.

  8. If there's a frontend, explore it briefly.

Tool usage discipline:
  - Use grep(names_only=true) for cheap discovery passes.
  - Use include globs to narrow searches fast, e.g. src/**/*.ts or *.{ts,tsx}.
  - Use max_matches_per_file when one file is noisy and you need breadth.
  - After discovery, read only the best few candidate files.

Budget: 40 file reads, 20 search/glob calls.
When you see [BUDGET] warnings → stop exploring, go to Phase 2 immediately.
Stop early when you have enough evidence — don't exhaust the budget reading
things that won't change the blueprint output.

Key rules during exploration:
  • Adapt to what you actually find — don't assume Django, React, or any
    specific framework. Let the files tell you.
  • Prioritise breadth over depth (one file per area > five files in one area).
  • Never read files you don't need (test fixtures, lock files, migrations,
    vendored code, generated files).

═══════════════════════════════════════════
PHASE 2 — GENERATE
═══════════════════════════════════════════

Output ONLY a single valid JSON object with the schema from the user message.

Rules:
  • Only describe what you actually found — no invented endpoints, models,
    or services.
  • Sections you couldn't explore → empty array [] or "Not detected."
  • tech_stack_details must reflect the actual stack you discovered.
  • Return ONLY JSON — no markdown, no prose, no ```json wrapper.
"""

# The user-turn message template injected at the start of the engine run.
_EXPLORATION_USER_TEMPLATE = """\
Generate a complete engineering blueprint for this project.

Project name: {project_name}
Tech stack: {tech_stack}
File count: {file_count} files across {dir_count} top-level directories

═══ CODEBASE ANCHOR ════════════════════════════════════════════
{compact_summary}
════════════════════════════════════════════════════════════════

Repository tree:
{repo_tree}

Feature context:
{feature_summary}

═══ OUTPUT SCHEMA ══════════════════════════════════════════════
Return ONLY one valid JSON object with ALL of these keys:

{{
  "project_summary": "...",
  "architecture_overview": "...",
  "mermaid_architecture": "graph TD ...",
  "mermaid_service_dependencies": "graph TD ...",
  "mermaid_erd": "erDiagram ...",
  "data_flow": "...",
  "sequence_flows": [{{"title":"","description":"","mermaid_sequence":"sequenceDiagram ...","touchpoints":[]}}],
  "tech_stack_details": [{{"tech":"","purpose":"","why_chosen":"","version":"","category":"language|framework|database|tool|library"}}],
  "services": [{{"name":"","type":"frontend|backend|database|cache|queue|worker|proxy","description":"","port":null,"tech":"","health_endpoint":null,"dependencies":[],"key_files":[]}}],
  "api_endpoints": [{{"method":"GET","path":"/api/...","description":"","request_body":null,"response":"","auth_required":true,"curl_example":""}}],
  "database_schema": [{{"table":"","description":"","key_fields":[{{"name":"","type":"","constraints":"","description":""}}],"relationships":"","indexes":[]}}],
  "key_components": [{{"name":"","file_path":"","purpose":"","complexity":"low|medium|high","dependencies":[],"exports":"","lines_estimate":""}}],
  "directory_guide": [{{"path":"","purpose":"","key_files":[],"pattern":""}}],
  "repo_tree": "project-name/\\n|- src/",
  "repository_map": [{{"area":"","description":"","important_files":[],"relationships":[]}}],
  "file_structure_visualizer": [{{"folder":"","summary":"","files":[{{"path":"","role":"","purpose":"","why":"","how":"","related_symbols":[]}}]}}],
  "change_guide": [{{"area":"","where":[],"notes":""}}],
  "setup_steps": [{{"step":"","command":"","explanation":"","os_note":""}}],
  "environment_variables": [{{"name":"","description":"","required":true,"default":null,"example":"","category":"api_key|database|config|feature_flag"}}],
  "security_considerations": [{{"area":"","description":"","severity":"high|medium|low"}}],
  "performance_notes": [{{"area":"","description":"","impact":"high|medium|low"}}],
  "testing_strategy": {{"unit":"","integration":"","e2e":"","coverage_target":"","run_command":""}},
  "code_quality_standards": [{{"tool":"","purpose":"","config_file":""}}],
  "common_workflows": [{{"title":"","steps":[]}}],
  "feature_inventory": [{{"title":"","status":"backlog|development|testing|done|unknown","description":"","implementation_notes":""}}],
  "sdlc_pipeline": {{"stages":[],"approval_gates":[],"ai_capabilities":[],"team_workflow":""}},
  "integration_points": [{{"name":"","type":"internal|external","description":"","evidence":[],"failure_modes":[]}}],
  "faq": [{{"question":"","answer":""}}],
  "gotchas": [],
  "onboarding_checklist": [{{"task":"","category":"environment|codebase|processes|tools|team","estimated_time":"","why_important":"","instructions":""}}],
  "key_concepts": [{{"concept":"","explanation":"","why_important":"","related_code":"","related_concepts":[]}}]
}}
════════════════════════════════════════════════════════════════

Start Phase 1 now: call list_dir(".") first, then explore and generate.
"""

# Worker-specific prompts for the parallel coordinator path
_BACKEND_WORKER_PROMPT = """\
You are exploring the BACKEND / SERVER-SIDE of a codebase.
Tools: list_dir, glob, grep, file_read.

Start with list_dir(".") — discover the tech stack from the files, don't assume it.
Then explore: entry points, API routes/handlers, data models/schemas/ORMs,
auth/middleware, background jobs, key config.

Project root: {workspace_root}
Repo tree (partial):
{repo_tree}

Return ONLY a JSON object:
{{
  "services": [...],
  "api_endpoints": [...],
  "database_schema": [...],
  "key_backend_files": ["path/to/file"],
  "backend_tech_stack": [...],
  "auth_mechanism": "...",
  "background_jobs": [...],
  "data_flow_notes": "..."
}}
"""

_FRONTEND_WORKER_PROMPT = """\
You are exploring the FRONTEND / CLIENT-SIDE of a codebase.
Tools: list_dir, glob, grep, file_read.

Start with list_dir(".") — if no frontend exists (pure API, CLI, library),
return minimal findings. Do not invent UI that isn't there.
Otherwise explore: app entry point, routing, state management, API client layer,
key components, build config.

Project root: {workspace_root}
Repo tree (partial):
{repo_tree}

Return ONLY a JSON object:
{{
  "frontend_services": [...],
  "routing_structure": [...],
  "state_management": "...",
  "api_client_pattern": "...",
  "key_components": [...],
  "frontend_tech_stack": [...],
  "build_tool": "...",
  "key_frontend_files": ["path/to/file"]
}}
"""

_INFRA_WORKER_PROMPT = """\
You are exploring the INFRASTRUCTURE and deployment of a codebase.
Tools: list_dir, glob, grep, file_read.

Start with list_dir("."), list_dir(".github") if present.
Explore: containerisation (Dockerfile, compose), CI/CD pipelines, environment
config (.env.example), IaC (Terraform, K8s, Helm), build/task runners
(Makefile, justfile), README setup instructions.

Project root: {workspace_root}
Repo tree (partial):
{repo_tree}

Return ONLY a JSON object:
{{
  "deployment_method": "...",
  "services_in_compose": [...],
  "ci_cd_pipeline": "...",
  "environment_variables": [...],
  "setup_steps": [...],
  "infrastructure_notes": "...",
  "key_infra_files": ["path/to/file"]
}}
"""

_COORDINATOR_SYNTHESIS_PROMPT = """\
You are synthesizing findings from three exploration workers into a complete
engineering blueprint.  The workers have already explored the codebase —
you should NOT call any more tools.

Project name: {project_name}
Tech stack: {tech_stack}
File count: {file_count}

Codebase anchor:
{compact_summary}

Backend worker findings:
{backend_result}

Frontend worker findings:
{frontend_result}

Infrastructure worker findings:
{infra_result}

Output ONLY a single valid JSON object with the full blueprint schema.
The schema is identical to the one used by the standard blueprint generator —
every key must be present.  Use the workers' findings as primary evidence.
Populate sections the workers didn't cover with "Not clearly detected."
Return ONLY JSON.
"""


# ---------------------------------------------------------------------------
# BlueprintQueryAgent
# ---------------------------------------------------------------------------

class BlueprintQueryAgent:
    """
    Tool-based blueprint generator.

    For repos with 300–9 999 files, runs a single QueryEngine loop where the
    LLM uses glob / grep / file_read to explore and then generates JSON.

    For repos with 10 000+ files, runs a Coordinator with three parallel
    read-only workers (backend, frontend, infra) then synthesises.
    """

    # Thresholds
    SINGLE_AGENT_MAX_FILES = 10_000
    MAX_TURNS = 45

    def __init__(self, workspace_path: Path, ai_config: dict):
        self.workspace_path = workspace_path
        self.ai_config = normalize_ai_config(ai_config)

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def generate(
        self,
        project_name: str,
        tech_stack: list[str],
        compact_summary: str,
        repo_tree: str,
        feature_summary: str = "",
        file_count: int = 0,
        dir_count: int = 0,
    ) -> dict:
        """Single-agent tool-based blueprint generation (300–9 999 files)."""
        user_message = _EXPLORATION_USER_TEMPLATE.format(
            project_name=project_name,
            tech_stack=", ".join(tech_stack) if tech_stack else "Not specified",
            file_count=file_count,
            dir_count=dir_count,
            compact_summary=(compact_summary or "")[:12_000],
            repo_tree=(repo_tree or "")[:6_000],
            feature_summary=(feature_summary or "")[:2_000],
        )

        engine = self._build_engine(anchor_context=compact_summary)
        result = engine.run(
            user_message=user_message,
            system_prompt=BLUEPRINT_SYSTEM_PROMPT,
            max_turns=self.MAX_TURNS,
        )

        if result.error:
            logger.error("BlueprintQueryAgent failed: %s", result.error)
            return {"_error": result.error}

        return _parse_blueprint_json(result.response)

    def generate_parallel(
        self,
        project_name: str,
        tech_stack: list[str],
        compact_summary: str,
        repo_tree: str,
        feature_summary: str = "",
        file_count: int = 0,
    ) -> dict:
        """
        Coordinator + parallel workers for huge monorepos (10 000+ files).
        BackendWorker, FrontendWorker, and InfraWorker run concurrently via
        the existing Coordinator / Worker infrastructure, then the coordinator
        synthesises their findings.
        """
        try:
            from agents.coordinator import Coordinator
        except ImportError:
            logger.warning("Coordinator not available — falling back to single-agent path")
            return self.generate(
                project_name=project_name,
                tech_stack=tech_stack,
                compact_summary=compact_summary,
                repo_tree=repo_tree,
                feature_summary=feature_summary,
                file_count=file_count,
            )

        repo_tree_short = (repo_tree or "")[:4_000]
        workspace_root = str(self.workspace_path)

        backend_prompt = _BACKEND_WORKER_PROMPT.format(
            workspace_root=workspace_root,
            repo_tree=repo_tree_short,
        )
        frontend_prompt = _FRONTEND_WORKER_PROMPT.format(
            workspace_root=workspace_root,
            repo_tree=repo_tree_short,
        )
        infra_prompt = _INFRA_WORKER_PROMPT.format(
            workspace_root=workspace_root,
            repo_tree=repo_tree_short,
        )

        coordinator_message = (
            f"Generate a complete engineering blueprint for '{project_name}'.\n\n"
            f"File count: {file_count}\n"
            f"Tech stack: {', '.join(tech_stack) if tech_stack else 'Not specified'}\n\n"
            "Dispatch THREE parallel read-only workers:\n"
            f'1. task="BackendWorker" read_only=true prompt="""{backend_prompt}"""\n'
            f'2. task="FrontendWorker" read_only=true prompt="""{frontend_prompt}"""\n'
            f'3. task="InfraWorker" read_only=true prompt="""{infra_prompt}"""\n\n'
            "After all workers complete, call the synthesis tool with their results "
            "to produce the final blueprint JSON.\n\n"
            f"Codebase anchor:\n{(compact_summary or '')[:8_000]}"
        )

        coordinator = Coordinator(
            workspace_id="blueprint",
            workspace_path=self.workspace_path,
            ai_config=self.ai_config,
        )
        coord_result = coordinator.handle_request(
            user_message=coordinator_message,
            max_turns=60,
        )

        if coord_result.error:
            logger.error("Coordinator failed for blueprint: %s", coord_result.error)
            # Fall back to single-agent
            return self.generate(
                project_name=project_name,
                tech_stack=tech_stack,
                compact_summary=compact_summary,
                repo_tree=repo_tree,
                feature_summary=feature_summary,
                file_count=file_count,
            )

        return _parse_blueprint_json(coord_result.response)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_engine(self, anchor_context: str = "") -> QueryEngine:
        """Build a QueryEngine wired with read-only tools + a ToolBudget."""
        registry = ToolRegistry()
        registry.register(FileReadTool())
        registry.register(GlobTool())
        registry.register(GrepTool())
        registry.register(ListDirTool())

        budget = ToolBudget(max_reads=40, max_searches=20)

        # Patch the registry's execute method to inject the budget into each call
        _inject_budget_into_registry(registry, self.workspace_path, budget)

        compactor = _AnchorAwareCompactor(anchor_context=anchor_context)
        prompt_builder = PromptBuilder()

        return QueryEngine(
            tool_registry=registry,
            prompt_builder=prompt_builder,
            compactor=compactor,
            ai_config=self.ai_config,
            workspace_path=self.workspace_path,
        )


# ---------------------------------------------------------------------------
# Anchor-aware compactor
# ---------------------------------------------------------------------------

class _AnchorAwareCompactor(ContextCompactor):
    """
    Subclass of ContextCompactor that automatically passes the blueprint
    anchor_context to compact() so it gets re-injected after every
    compaction — mirrors Claude Code's post-compact file re-injection.
    """

    def __init__(self, anchor_context: str = ""):
        super().__init__()
        self._anchor = anchor_context

    def compact(self, messages, model, generate_fn, anchor_context=None):
        return super().compact(
            messages,
            model,
            generate_fn,
            anchor_context=anchor_context or self._anchor,
        )


# ---------------------------------------------------------------------------
# Budget injection helper
# ---------------------------------------------------------------------------

def _inject_budget_into_registry(
    registry: ToolRegistry,
    workspace_path: Path,
    budget: ToolBudget,
) -> None:
    """
    Monkey-patch ToolRegistry.execute to inject a shared ToolBudget into
    every ToolContext, and ensure workspace_path is always set correctly.

    This avoids threading a budget through every call site — the registry
    becomes the single point of enforcement.
    """
    original_execute = registry.execute

    def _execute_with_budget(name: str, input_data: dict, context: ToolContext):
        # Always use the correct workspace; always attach the budget
        enriched = ToolContext(
            workspace_id=context.workspace_id,
            workspace_path=workspace_path,
            agent_id=context.agent_id,
            budget=budget,
        )
        return original_execute(name, input_data, enriched)

    registry.execute = _execute_with_budget  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# JSON extraction helper
# ---------------------------------------------------------------------------

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _parse_blueprint_json(text: str) -> dict:
    """
    Extract and parse the blueprint JSON from the LLM response.

    Tries, in order:
    1. Direct JSON parse of the full response
    2. Extract first ```json ... ``` block
    3. Find the outermost { ... } span
    Returns an empty dict on total failure.
    """
    if not text:
        return {}

    text = text.strip()

    # 1 — direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2 — fenced code block
    m = _JSON_BLOCK_RE.search(text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 3 — outermost braces
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    logger.warning("BlueprintQueryAgent: could not parse JSON from LLM response (len=%d)", len(text))
    return {}
