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
from typing import Any

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

_LEGACY_BLUEPRINT_SYSTEM_PROMPT = """\
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

# Override the legacy prompt block above with the V3 grounding rules.
BLUEPRINT_SYSTEM_PROMPT = """\
You are an expert software architect. Your job: explore a codebase with tools,
then generate a complete engineering blueprint JSON.

You have tools: list_dir, glob, grep, file_read.

===========================================
PHASE 1 - EXPLORE
===========================================

You are a senior engineer on day one at a new company.
You don't know the tech stack yet. Discover it yourself.

Exploration strategy:
  1. Start with list_dir(".") - always, no exceptions.
     This tells you what kind of project this is: languages, frameworks,
     monorepo vs single service, frontend vs backend vs CLI vs library.

  2. Read README.md (or readme.md) FIRST - it often contains the best
     human-written setup, architecture, and run instructions.

  3. Read the key manifest/config files you see
     (go.mod, Cargo.toml, package.json, pyproject.toml, pom.xml, mix.exs,
      Gemfile, composer.json, *.csproj, Dockerfile, docker-compose.yml...)

  4. Find service boundaries - glob for manifest files if it looks like
     a monorepo (multiple services / packages).

  5. Read entry points - you know what the entry point is for the
     detected stack. Read it.

  6. Discover the API surface:
     a. Find the routing/URL configuration for the detected framework:
        - Django: urls.py (may include() other url files - read ALL of them)
        - Express/Koa/Fastify: router files, app.get/post/put/delete calls
        - FastAPI: decorated handler functions (@app.get, @router.post)
        - Rails: config/routes.rb
        - Spring: @RequestMapping / @GetMapping annotations
        - ASP.NET: [Route] / [HttpGet] attributes
        - Phoenix: router.ex
        - Go: http.HandleFunc / mux.HandleFunc / gin/echo route registration
        - If none of the above: grep for path-like registration patterns
     b. Read the route configuration file(s) completely. This is your source
        of truth for which endpoints exist.
     c. For EACH route, find and read the handler/view function - it may be
        in a DIFFERENT file than the route config. Follow imports.
     d. Determine the HTTP method from handler source code:
        - Decorators: @api_view(["POST"]), @require_POST, @app.post()
        - Guards: request.method == "POST", request.method != "GET"
          (inequality means view ONLY accepts the method being rejected)
        - Class methods: def post(self, ...), def destroy(self, ...)
     e. If a handler supports multiple methods, create one api_endpoints
        entry per method.
     f. NEVER add endpoints from scaffold templates, code generators,
        or string literals that generate code for other projects.

  7. Discover data models - find model/schema/entity definitions.
     You know the ORM/framework conventions.

  8. Read infrastructure config - Dockerfile, CI pipelines, .env.example.

  8b. Environment variables: the anchor context lists env var names
      found in the codebase. For EACH listed variable, include an
      environment_variables entry with: name, description, required,
      category, example value. Don't skip variables just because there
      are many - a complete list is more useful than a short one.

  9. If there's a frontend, explore it briefly.

  LARGE REPO STRATEGY (when file count > 2000):
  1. The graph analysis above breaks the codebase into communities.
     Use them as your navigation map.
  2. Read one representative file from each community to understand its role.
  3. Focus reads on community boundary files with the highest connectivity.
  4. Budget your reads across communities, not within one area:
     - Backend API community -> route config + 2-3 key handlers
     - Data/model community -> main model file
     - Frontend community -> main entry + one page component
     - Infrastructure community -> Dockerfile / CI config

  UNKNOWN FRAMEWORK / LANGUAGE FALLBACK:
  1. Look for build system files: Makefile, CMakeLists.txt, BUILD,
     build.gradle, pom.xml, Cargo.toml, go.mod, mix.exs, *.cabal,
     *.sln, meson.build.
  2. Look for entry points: main.*, index.*, app.*, __main__.py,
     Program.*, Main.*, lib.rs, cmd/*/main.go.
  3. If the graph analysis identified hub nodes, read those files first.
     They are often the most architecturally important regardless of language.
  4. Look for test directories: test/, tests/, spec/, __tests__/.
  5. Build the architecture description from what you actually find,
     not from framework assumptions.

  POORLY DOCUMENTED / CHAOTIC REPO STRATEGY:
  1. If docs are weak or absent, start from the graph analysis.
     Communities and hub nodes give you structure.
  2. Look for the largest files by line count.
  3. Look for files with the most imports/dependencies.
  4. Use grep to find strings like "main", "start", "init", "server", "app".
  5. For setup_steps: if no docs exist, say "No setup documentation found.
     Inspect [build system file] for build instructions." - do not guess.
  6. For environment_variables: still scan code references even when
     no .env.example files exist.
  7. Set section values to "Not detected." for sections you genuinely
     cannot determine. Partial truth is better than hallucination.

Tool usage discipline:
  - Use grep(names_only=true) for cheap discovery passes.
  - Use include globs to narrow searches fast, e.g. src/**/*.ts or *.{ts,tsx}.
  - Use max_matches_per_file when one file is noisy and you need breadth.
  - After discovery, read only the best few candidate files.

Budget: 40 file reads, 20 search/glob calls.
When you see [BUDGET] warnings -> stop exploring, go to Phase 2 immediately.
Stop early when you have enough evidence - don't exhaust the budget reading
things that won't change the blueprint output.

CRITICAL evidence-grounding rules:
  - API endpoints MUST come from route/URL configuration or handler registration,
    not from string literals inside view functions, template generators, or
    scaffold code.
  - HTTP methods must be verified from the actual handler source. Do NOT default
    to GET if you can inspect the code.
  - Environment variables must come from code references, env templates, and
    config files - not from prose examples.
  - File paths in the blueprint must resolve to actual files you have seen via
    list_dir, glob, grep, or file_read. Do NOT invent paths.
  - If a source file generates code or templates for other projects, do NOT
    treat that generated content as part of this project's runtime surface.

Key rules during exploration:
  - Adapt to what you actually find - don't assume Django, React, or any
    specific framework. Let the files tell you.
  - Prioritize breadth over depth (one file per area > five files in one area).
  - Never read files you don't need (test fixtures, lock files, migrations,
    vendored code, generated files).

===========================================
PHASE 2 - GENERATE
===========================================

Output ONLY a single valid JSON object with the schema from the user message.

Rules:
  - Only describe what you actually found - no invented endpoints, models,
    or services.
  - services[].key_files: plain file paths only.
    YES: "backend/api/views.py"
    NO:  "backend/api/views.py - Defines the API endpoints"
  - setup_steps: check these sources IN ORDER for setup instructions:
    1. README.md / CONTRIBUTING.md
    2. Makefile / justfile / Taskfile.yml
    3. docker-compose.yml
    4. package.json "scripts" section
    5. pyproject.toml / setup.py / requirements.txt
    6. Cargo.toml, go.mod, mix.exs, and similar manifest files
    When README documents specific commands, prefer those over inferred
    equivalents. When README is absent or incomplete, use the best evidence
    from the repo files above.
  - testing_strategy: determine the test command from repo files, not the
    current environment:
    1. README documented test commands
    2. Makefile "test" target
    3. package.json "test" script
    4. pyproject.toml [tool.pytest] section or tox.ini
    5. CI config (.github/workflows, .gitlab-ci.yml) test steps
    Do NOT assume a tool is available just because a config file references it.
  - Sections you couldn't explore -> empty array [] or "Not detected."
  - tech_stack_details must reflect the actual stack you discovered.
  - Return ONLY JSON - no markdown, no prose, no ```json wrapper.
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

â•â•â• STRUCTURAL GRAPH ANALYSIS â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
{graph_summary}
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

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
        graph_summary: str = "",
        feature_summary: str = "",
        file_count: int = 0,
        dir_count: int = 0,
    ) -> dict:
        """Single-agent tool-based blueprint generation (300–9 999 files)."""
        graph_cap = 3000
        if file_count > 2000:
            graph_cap = 6000
        if file_count > 5000:
            graph_cap = 10000
        if file_count > 10000:
            graph_cap = 14000
        user_message = _EXPLORATION_USER_TEMPLATE.format(
            project_name=project_name,
            tech_stack=", ".join(tech_stack) if tech_stack else "Not specified",
            file_count=file_count,
            dir_count=dir_count,
            compact_summary=(compact_summary or "")[:12_000],
            graph_summary=(graph_summary or "Not available.")[:graph_cap],
            repo_tree=(repo_tree or "")[:6_000],
            feature_summary=(feature_summary or "")[:2_000],
        )

        engine = self._build_engine(anchor_context=compact_summary, file_count=file_count)
        result = engine.run(
            user_message=user_message,
            system_prompt=BLUEPRINT_SYSTEM_PROMPT,
            max_turns=self.MAX_TURNS,
        )

        if result.error:
            logger.error("BlueprintQueryAgent failed: %s", result.error)
            return {"_error": result.error}

        blueprint = _parse_blueprint_json(result.response)
        blueprint = _validate_and_fill_blueprint(blueprint)
        blueprint = _verify_blueprint(blueprint, self.workspace_path)
        return blueprint

    def generate_parallel(
        self,
        project_name: str,
        tech_stack: list[str],
        compact_summary: str,
        repo_tree: str,
        graph_summary: str = "",
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
                graph_summary=graph_summary,
                feature_summary=feature_summary,
                file_count=file_count,
            )

        repo_tree_short = (repo_tree or "")[:4_000]
        workspace_root = str(self.workspace_path)
        graph_cap = 3000
        if file_count > 2000:
            graph_cap = 6000
        if file_count > 5000:
            graph_cap = 10000
        if file_count > 10000:
            graph_cap = 14000
        graph_summary_short = (graph_summary or "Not available.")[:graph_cap]

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
            f"Structural graph analysis:\n{graph_summary_short}\n\n"
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
                graph_summary=graph_summary,
                feature_summary=feature_summary,
                file_count=file_count,
            )

        blueprint = _parse_blueprint_json(coord_result.response)
        blueprint = _validate_and_fill_blueprint(blueprint)
        blueprint = _verify_blueprint(blueprint, self.workspace_path)
        return blueprint

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_engine(self, anchor_context: str = "", file_count: int = 0) -> QueryEngine:
        """Build a QueryEngine wired with read-only tools + a ToolBudget."""
        registry = ToolRegistry()
        registry.register(FileReadTool())
        registry.register(GlobTool())
        registry.register(GrepTool())
        registry.register(ListDirTool())

        budget = ToolBudget.for_repo(file_count)

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

BLUEPRINT_FIELD_TYPES: dict[str, type] = {
    "project_summary": str,
    "architecture_overview": str,
    "mermaid_architecture": str,
    "mermaid_service_dependencies": str,
    "mermaid_erd": str,
    "data_flow": str,
    "sequence_flows": list,
    "tech_stack_details": list,
    "services": list,
    "api_endpoints": list,
    "database_schema": list,
    "key_components": list,
    "directory_guide": list,
    "repo_tree": str,
    "repository_map": list,
    "file_structure_visualizer": list,
    "change_guide": list,
    "setup_steps": list,
    "environment_variables": list,
    "security_considerations": list,
    "performance_notes": list,
    "testing_strategy": dict,
    "code_quality_standards": list,
    "common_workflows": list,
    "feature_inventory": list,
    "sdlc_pipeline": dict,
    "integration_points": list,
    "faq": list,
    "gotchas": list,
    "onboarding_checklist": list,
    "key_concepts": list,
}

BLUEPRINT_TYPED_DEFAULTS: dict[str, Any] = {
    "testing_strategy": {
        "unit": "",
        "integration": "",
        "e2e": "",
        "coverage_target": "",
        "run_command": "",
    },
    "sdlc_pipeline": {
        "stages": [],
        "approval_gates": [],
        "ai_capabilities": [],
        "team_workflow": "",
    },
}


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


def _typed_default_for_key(key: str, expected_type: type) -> Any:
    if key in BLUEPRINT_TYPED_DEFAULTS:
        return json.loads(json.dumps(BLUEPRINT_TYPED_DEFAULTS[key]))
    if expected_type is list:
        return []
    if expected_type is dict:
        return {}
    return ""


def _coerce_blueprint_value(key: str, value: Any, expected_type: type) -> Any:
    if isinstance(value, expected_type):
        return value
    if expected_type is str:
        return "" if value is None else str(value)
    if expected_type is list:
        if value in (None, "", {}):
            return []
        if isinstance(value, (tuple, set)):
            return list(value)
        return value if isinstance(value, list) else [value]
    if expected_type is dict:
        if isinstance(value, dict):
            return value
        return _typed_default_for_key(key, expected_type)
    return _typed_default_for_key(key, expected_type)


def _validate_and_fill_blueprint(blueprint: dict) -> dict:
    if not isinstance(blueprint, dict):
        logger.warning("BlueprintQueryAgent: blueprint root was %s, coercing to empty dict", type(blueprint).__name__)
        blueprint = {}

    validated = dict(blueprint)
    for key, expected_type in BLUEPRINT_FIELD_TYPES.items():
        if key not in validated:
            validated[key] = _typed_default_for_key(key, expected_type)
            continue
        if not isinstance(validated[key], expected_type):
            logger.warning(
                "BlueprintQueryAgent: blueprint key '%s' had wrong type %s, expected %s",
                key,
                type(validated[key]).__name__,
                expected_type.__name__,
            )
            validated[key] = _coerce_blueprint_value(key, validated[key], expected_type)
    return validated


def _resolve_blueprint_path(workspace_path: Path, raw_path: str, *, expect_dir: bool = False) -> Path | None:
    raw = str(raw_path or "").strip()
    if not raw:
        return None

    candidates: list[Path] = []
    path_obj = Path(raw)
    if path_obj.is_absolute():
        candidates.append(path_obj)

    normalized = raw.replace("\\", "/").lstrip("./")
    candidates.append(workspace_path / normalized)
    if normalized.startswith(f"{workspace_path.name}/"):
        candidates.append(workspace_path / normalized[len(workspace_path.name) + 1 :])

    workspace_root = workspace_path.resolve()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            resolved.relative_to(workspace_root)
        except Exception:
            continue
        if expect_dir and resolved.is_dir():
            return resolved
        if not expect_dir and resolved.exists():
            return resolved
    return None


def _verify_blueprint(blueprint: dict, workspace_path: Path) -> dict:
    verified = dict(blueprint)
    removed_key_components = 0
    removed_service_files = 0
    removed_directory_guides = 0

    key_components: list[dict[str, Any]] = []
    for item in verified.get("key_components") or []:
        if not isinstance(item, dict):
            removed_key_components += 1
            continue
        resolved = _resolve_blueprint_path(workspace_path, str(item.get("file_path") or ""))
        if not resolved:
            removed_key_components += 1
            continue
        key_components.append(item)
    verified["key_components"] = key_components

    services: list[dict[str, Any]] = []
    for item in verified.get("services") or []:
        if not isinstance(item, dict):
            continue
        cleaned = dict(item)
        key_files = []
        for raw_path in item.get("key_files") or []:
            if not isinstance(raw_path, str):
                removed_service_files += 1
                continue
            for separator in (" \u2013 ", " \u2014 ", " : "):
                if separator in raw_path:
                    raw_path = raw_path.split(separator)[0].strip()
                    break
            path_part = raw_path.split(" - ")[0].split(" – ")[0].strip()
            if not path_part or path_part.startswith("Defines") or path_part.startswith("Contains"):
                removed_service_files += 1
                continue
            basename = path_part.replace("\\", "/").split("/")[-1] if path_part else ""
            looks_like_path = (
                bool(path_part)
                and ("/" in path_part or "\\" in path_part or "." in basename)
            )
            if not looks_like_path:
                removed_service_files += 1
                continue
            resolved = _resolve_blueprint_path(workspace_path, path_part)
            if resolved:
                key_files.append(path_part)
            else:
                removed_service_files += 1
        cleaned["key_files"] = key_files
        services.append(cleaned)
    verified["services"] = services

    directory_guide: list[dict[str, Any]] = []
    for item in verified.get("directory_guide") or []:
        if not isinstance(item, dict):
            removed_directory_guides += 1
            continue
        resolved = _resolve_blueprint_path(workspace_path, str(item.get("path") or ""), expect_dir=True)
        if not resolved:
            removed_directory_guides += 1
            continue
        directory_guide.append(item)
    verified["directory_guide"] = directory_guide

    api_endpoints = verified.get("api_endpoints") or []
    if api_endpoints:
        for ep in api_endpoints:
            if not isinstance(ep, dict):
                continue
            params = ep.get("path_params")
            if isinstance(params, list):
                seen_params: set[str] = set()
                deduped_params: list[Any] = []
                for param in params:
                    param_key = str(param).strip() if param else ""
                    if not param_key or param_key in seen_params:
                        continue
                    seen_params.add(param_key)
                    deduped_params.append(param)
                ep["path_params"] = deduped_params
        seen_endpoints: set[tuple[str, str]] = set()
        deduped: list[dict] = []
        for ep in api_endpoints:
            if not isinstance(ep, dict):
                continue
            path = str(ep.get("path") or "").strip()
            norm_path = path.rstrip("/") if len(path) > 1 else path
            key = (
                str(ep.get("method") or "GET").upper(),
                norm_path,
            )
            if key in seen_endpoints:
                continue
            seen_endpoints.add(key)
            deduped.append(ep)
        if len(deduped) < len(api_endpoints):
            logger.info("BlueprintQueryAgent: deduped %d->%d endpoints", len(api_endpoints), len(deduped))
        verified["api_endpoints"] = deduped

    repo_tree = verified.get("repo_tree") or ""
    if "project root/" in repo_tree:
        verified["repo_tree"] = repo_tree.replace("project root/", "./")

    if removed_key_components or removed_service_files or removed_directory_guides:
        logger.info(
            "BlueprintQueryAgent: removed phantom entries key_components=%d service_key_files=%d directory_guide=%d",
            removed_key_components,
            removed_service_files,
            removed_directory_guides,
        )

    return verified
