"""
Multi-stage scaffold pipeline.

Stage 1  — SpecAgent:          description + stack → rich product spec JSON
Stage 1.5— WireframeAgent:     spec → per-page section wireframes with concrete props
Stage 1.6— APIContractDeriver: spec → typed API contract (both ends read the same)
Stage 2  — FilePlanAgent:      spec + wireframes + contract → ordered file plan
Stage 2.5— TemplateBootstrap:  copy pre-baked UI primitives (never LLM-written)
Stage 3  — FileCodeAgent:      generate each file (parallel within layer)
Stage 4  — SingleStackGuard:   reject plans that mix two frontend stacks
Stage 5  — ExecValidator:      syntax → imports → jsx-ext → build → frontend import check
Stage 6  — RepairAgent:        errors → LLM fixes → repeat up to MAX_REPAIR_ROUNDS
"""
from __future__ import annotations

import ast
import json
import logging
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from agents.core.base import BaseAgent
from agents.coding.spec_agent import SpecAgent
from agents.coding.file_plan_agent import FilePlanAgent
from agents.coding.repair_agent import RepairAgent
from agents.coding.wireframe_agent import WireframeAgent
from agents.coding.design_agent import DesignAgent
from agents.coding.template_bootstrap import get_template_files, get_frozen_paths, write_templates
from agents.coding.stack_resolver import resolve_conventions
from agents.coding.stack_conventions import (
    build_constraint_block,
    get_vite_config,
    get_react_tailwind_config,
    get_react_index_css,
)

logger = logging.getLogger(__name__)

MAX_PARALLEL_FILES = 6
MAX_REPAIR_ROUNDS = 3

# Pairs that must NOT coexist in a file plan
_DUAL_STACK_CONFLICTS = [
    ("vite.config", "next.config"),
    ("src/App.", "app/page."),
    ("src/main.", "app/layout."),
]


# ---------------------------------------------------------------------------
# Derive API contract from spec (Pass 4)
# ---------------------------------------------------------------------------

def _derive_api_contract(spec: dict) -> dict:
    """
    Normalise spec api_endpoints into a typed contract dict.
    Both backend codegen and frontend API client receive the same object.
    """
    endpoints = []
    types: dict = {}

    for ep in spec.get("api_endpoints", []):
        if not isinstance(ep, dict):
            continue
        method = str(ep.get("method", "GET")).upper()
        path = str(ep.get("path", "/api/resource/"))
        handler = ep.get("handler", "")
        purpose = ep.get("purpose", "")
        req = ep.get("request_body") or {}
        resp = ep.get("response_shape") or {}
        auth = bool(ep.get("auth_required", False))

        # Derive a camelCase function name for the frontend client
        path_parts = re.sub(r"[{}/]", "_", path.strip("/")).split("_")
        func_name = method.lower() + "".join(p.capitalize() for p in path_parts if p)

        endpoints.append({
            "id": func_name,
            "method": method,
            "path": path,
            "handler": handler,
            "purpose": purpose,
            "auth_required": auth,
            "request_body": req,
            "response_shape": resp,
        })

        # Register named types from response
        for model in spec.get("data_models", []):
            if isinstance(model, dict) and model.get("name"):
                mname = model["name"]
                if mname not in types:
                    types[mname] = {f["name"]: f["type"] for f in model.get("fields", []) if isinstance(f, dict)}

    return {
        "endpoints": endpoints,
        "types": types,
        "auth_model": spec.get("auth_model", "none"),
    }


def _contract_to_prompt_block(contract: dict) -> str:
    """Render the API contract as a compact block for LLM prompts."""
    if not contract.get("endpoints"):
        return ""
    lines = ["## API contract (authoritative — both ends must match)"]
    for ep in contract["endpoints"]:
        lines.append(
            f"  {ep['method']} {ep['path']} → {ep['id']}()  "
            f"req:{json.dumps(ep['request_body'])[:80]}  "
            f"resp:{json.dumps(ep['response_shape'])[:80]}"
        )
    if contract.get("types"):
        lines.append("## Domain types")
        for name, fields in contract["types"].items():
            lines.append(f"  {name}: {json.dumps(fields)[:120]}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# FileCodeAgent
# ---------------------------------------------------------------------------

class FileCodeAgent(BaseAgent):
    """Generates a single file given spec, wireframe, contract, and dependency content."""

    def __init__(self, ai_config: dict | None = None):
        super().__init__(
            role="Senior Software Engineer",
            system_instruction=(
                "You are a senior engineer writing one specific file for a project. "
                "You receive exact architectural constraints, a precise file contract, "
                "the content of every file this file depends on, and — for page files — "
                "a concrete section-by-section wireframe with populated prop data.\n\n"
                "ABSOLUTE RULES FOR PAGE FILES:\n"
                "1. SELF-CONTAINED: Write ALL section JSX/HTML inline in this file's return(). "
                "   Do NOT extract sections into separate components or new files. "
                "   The landing page gets its hero, features, stats, testimonials, pricing, FAQ, "
                "   CTA, and footer ALL written out inline in LandingPage.jsx.\n"
                "2. MINIMUM LENGTH: Pages must be AT LEAST 400 lines. If your output would be "
                "   shorter, add more sections, more detail, more content, more interactivity.\n"
                "3. REAL DATA EVERYWHERE: Every list, grid, card, table, or feed must be populated "
                "   with real data imported from mockData. Zero empty states in the initial render.\n"
                "4. WIREFRAME FIDELITY: If a wireframe is provided, render EVERY section listed "
                "   in the exact order given, using the exact prop data provided.\n"
                "5. INTERACTIONS: Every page needs local useState for at least: search/filter, "
                "   active tab, selected item, form state, or modal open/close.\n"
                "6. UI PRIMITIVES: Import Button, Card, Badge, Tabs, Input, etc. from components/ui/ "
                "   whenever they fit — never use raw <button> or unstyled elements.\n\n"
                "RULES FOR ALL FILES:\n"
                "- Write COMPLETE, WORKING code. No TODO, no placeholder, no 'coming soon'.\n"
                "- Every import must reference a real package or a file listed in the plan.\n"
                "- Return ONLY raw file content — no JSON wrapper, no markdown fences."
            ),
            ai_config=ai_config,
        )

    def generate_file(
        self,
        file_path: str,
        file_desc: dict,
        spec: dict,
        dep_contents: dict[str, str],
        constraint_block: str,
        full_plan_paths: list[str],
        wireframe: dict | None = None,
        api_contract: dict | None = None,
    ) -> str:
        ext = Path(file_path).suffix
        lang_map = {
            ".py": "Python", ".jsx": "React JSX", ".tsx": "React TSX",
            ".js": "JavaScript", ".ts": "TypeScript", ".json": "JSON",
            ".css": "CSS", ".html": "HTML", ".txt": "plain text", ".md": "Markdown",
            ".vue": "Vue SFC", ".svelte": "Svelte", ".prisma": "Prisma schema",
        }
        lang = lang_map.get(ext, "")

        description = file_desc.get("description", f"File at {file_path}")
        exact_imports = file_desc.get("exact_imports", [])
        max_lines = file_desc.get("max_lines", 250)

        deps_section = ""
        if dep_contents:
            deps_section = "\n\n## Dependency files (read carefully before writing)\n"
            for dep_path, dep_content in dep_contents.items():
                shown = dep_content if len(dep_content) < 4000 else dep_content[:4000] + "\n... (truncated)"
                deps_section += f"\n### {dep_path}\n```\n{shown}\n```"

        wireframe_section = ""
        if wireframe and isinstance(wireframe, dict) and wireframe.get("sections"):
            wireframe_section = f"""
## Page wireframe — render EXACTLY these sections IN ORDER

{json.dumps(wireframe, indent=2)[:6000]}

CRITICAL: Your output must render every section listed above, in the listed order,
using the exact headlines, body, CTAs, items, and data provided. Do not invent new
section content. Pull item data from mockData when section items reference collections.
"""

        contract_section = _contract_to_prompt_block(api_contract) if api_contract else ""

        all_paths_str = "\n".join(f"  {p}" for p in full_plan_paths)

        # Detect if we have UI primitives available
        has_react_ui = any("components/ui/" in p for p in full_plan_paths)
        ui_import_hint = ""
        if has_react_ui and lang in ("React JSX", "React TSX"):
            ui_import_hint = (
                "\n## Available UI primitives (import from these paths)\n"
                "Button, Card/CardHeader/CardTitle/CardDescription/CardContent/CardFooter, "
                "Badge, Input, Label, Textarea, Separator, Avatar, Skeleton, Progress, "
                "Tabs/TabsList/TabsTrigger/TabsContent, Select/SelectItem, Dialog/DialogContent/..., "
                "Sheet/SheetContent/...\n"
                "Import example: import { Button } from '../components/ui/button'\n"
                "Use these primitives instead of raw <button> or inline Tailwind one-offs.\n"
            )

        prompt = f"""Write the file `{file_path}`.

{constraint_block}

## File contract
{description}

## Exact imports to use (copy verbatim)
{chr(10).join(f'  {imp}' for imp in exact_imports) if exact_imports else '  (derive from dependency files and constraint block)'}

## All project file paths (for accurate relative imports)
{all_paths_str}
{ui_import_hint}
{wireframe_section}
{contract_section}
{deps_section}

## Product context
Product: {spec.get('product_name', '')} — {spec.get('tagline', '')}
Auth: {spec.get('auth_model', 'none')}
Models: {', '.join(m['name'] for m in spec.get('data_models', []) if isinstance(m, dict))}

## Design system
{json.dumps(spec.get('design_system', {}), indent=2)[:2000]}

## Content bank
{json.dumps(spec.get('content_bank', {}), indent=2)[:1500]}

## Instructions
- Write complete {lang} code for `{file_path}`
- Target ~{max_lines} lines (seed files may be longer; stay focused for components/pages)
- For pages: render EVERY wireframe section using the exact prop data provided
- For React/UI files: import primitives from components/ui/; use the design system palette;
  avoid generic blue-gray dashboard aesthetic; every section must be populated, never empty
- Local state only for search/filter/tabs/forms — never block render on API data
- Return ONLY the raw file content. No JSON. No markdown fences. No preamble.
"""
        content = self.generate(prompt=prompt)
        return _strip_fences(content, file_path)


# ---------------------------------------------------------------------------
# Single-stack invariant guard (Pass 5)
# ---------------------------------------------------------------------------

def _enforce_single_stack(file_plan: list[dict], conventions: dict) -> list[dict]:
    """
    Remove files that would create a dual-stack project.
    Keeps only files within declared frontend_dir / backend_dir.
    Also blocks any conflicting config file pairs.
    """
    frontend_dir = conventions.get("frontend_dir") or "."
    backend_dir = conventions.get("backend_dir")

    paths_in_plan = [str(e.get("path", "")).replace("\\", "/") for e in file_plan]

    # Detect conflict pairs
    for a_frag, b_frag in _DUAL_STACK_CONFLICTS:
        has_a = any(a_frag in p for p in paths_in_plan)
        has_b = any(b_frag in p for p in paths_in_plan)
        if has_a and has_b:
            # Keep whichever aligns with declared frontend_dir
            vite_style = frontend_dir in (".", None) or "vite" in str(conventions.get("frontend_framework", "")).lower()
            if vite_style:
                # Drop Next.js style paths
                file_plan = [e for e in file_plan if b_frag not in str(e.get("path", ""))]
                logger.warning("SingleStackGuard: dropped %s paths (dual-stack conflict)", b_frag)
            else:
                # Drop Vite style paths
                file_plan = [e for e in file_plan if a_frag not in str(e.get("path", ""))]
                logger.warning("SingleStackGuard: dropped %s paths (dual-stack conflict)", a_frag)

    # Drop backend files if frontend-only
    if not backend_dir:
        file_plan = [
            e for e in file_plan
            if not any(
                str(e.get("path", "")).startswith(bd + "/")
                for bd in ("backend", "server", "api_server")
            )
        ]

    return file_plan


# ---------------------------------------------------------------------------
# ExecValidator — Passes 5 & 6
# ---------------------------------------------------------------------------

class ExecValidator:
    """
    Validates generated files by actually running checks.
    Does not use heuristics — reads real output.
    """

    def __init__(self, project_root: Path, conventions: dict, on_event: Callable | None = None):
        self.root = project_root
        self.conv = conventions
        self.on_event = on_event

    def _emit(self, msg: str) -> None:
        logger.info("[validator] %s", msg)
        if self.on_event:
            try:
                self.on_event({"type": "validate", "message": msg})
            except Exception:
                pass

    def _run(self, cmd: str, cwd: str | None = None, timeout: int = 60) -> dict:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=cwd or str(self.root),
            )
            return {
                "command": cmd, "exit_code": result.returncode,
                "stdout": result.stdout[:5000], "stderr": result.stderr[:5000],
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {"command": cmd, "exit_code": -1, "stdout": "", "stderr": f"Timeout after {timeout}s", "success": False}
        except Exception as exc:
            return {"command": cmd, "exit_code": -1, "stdout": "", "stderr": str(exc), "success": False}

    def run_all(self) -> list[dict]:
        errors = []
        errors += self._phase_python_syntax()
        errors += self._phase_backend_import_check()
        errors += self._phase_jsx_in_ts()
        errors += self._phase_frontend_imports()
        errors += self._phase_api_routes()
        return errors

    def run_build_gate(self) -> list[dict]:
        """
        Run npm install + build for JS projects.
        Separate from run_all — called once after final codegen write.
        """
        errors = []
        errors += self._phase_frontend_install_build()
        return errors

    def _phase_python_syntax(self) -> list[dict]:
        errors = []
        backend_dir = self.root / self.conv.get("backend_dir", "backend")
        if not backend_dir.exists():
            return errors

        self._emit("Checking Python syntax...")
        for py_file in backend_dir.rglob("*.py"):
            if any(skip in str(py_file) for skip in (".venv", "__pycache__", "migrations")):
                continue
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                ast.parse(source)
            except SyntaxError as exc:
                rel = str(py_file.relative_to(self.root)).replace("\\", "/")
                errors.append({
                    "phase": "python_syntax",
                    "command": f"ast.parse({rel})",
                    "exit_code": 1,
                    "stderr": f"SyntaxError in {rel} line {exc.lineno}: {exc.msg}\nLine: {exc.text or ''}",
                    "stdout": "",
                })
        if not errors:
            self._emit("Python syntax OK")
        return errors

    def _phase_backend_import_check(self) -> list[dict]:
        errors = []
        backend_dir = self.root / self.conv.get("backend_dir", "backend")
        startup_check = self.conv.get("startup_check_backend")
        if not startup_check or not backend_dir.exists():
            return errors

        self._emit("Checking backend imports...")
        result = self._run(startup_check, cwd=str(backend_dir), timeout=30)
        if not result["success"]:
            result["phase"] = "backend_import_check"
            errors.append(result)
            self._emit(f"Import error: {result['stderr'][:150]}")
        else:
            self._emit("Backend imports OK")
        return errors

    def _phase_jsx_in_ts(self) -> list[dict]:
        errors = []
        frontend_dir = self.root / (self.conv.get("frontend_dir") or ".")
        if not frontend_dir.exists():
            return errors

        jsx_pattern = re.compile(r'return\s*\(\s*\n?\s*<|<[A-Z][a-zA-Z]+[\s/>]|React\.FC|JSX\.Element')
        self._emit("Checking .ts file extensions...")
        for ts_file in frontend_dir.rglob("*.ts"):
            if any(skip in str(ts_file) for skip in ("node_modules", "dist", ".next", "d.ts")):
                continue
            if ts_file.name.endswith(".d.ts"):
                continue
            try:
                content = ts_file.read_text(encoding="utf-8", errors="replace")
                if jsx_pattern.search(content):
                    rel = str(ts_file.relative_to(self.root)).replace("\\", "/")
                    errors.append({
                        "phase": "jsx_in_ts",
                        "command": f"check_ext({rel})",
                        "exit_code": 1,
                        "stderr": (
                            f"File `{rel}` has JSX syntax but .ts extension. "
                            f"Must be renamed to .tsx."
                        ),
                        "stdout": content[:300],
                        "file_to_rename": {"from": rel, "to": rel[:-3] + ".tsx"},
                    })
            except Exception:
                pass
        return errors

    def _phase_frontend_imports(self) -> list[dict]:
        errors = []
        frontend_dir = self.root / (self.conv.get("frontend_dir") or ".")
        if not frontend_dir.exists():
            return errors

        known: set[str] = set()
        for f in frontend_dir.rglob("*"):
            if f.is_file() and "node_modules" not in str(f) and "dist" not in str(f):
                known.add(str(f.relative_to(frontend_dir)).replace("\\", "/"))

        exts = ("", ".jsx", ".tsx", ".js", ".ts", ".css", ".json",
                "/index.jsx", "/index.tsx", "/index.js", "/index.ts")

        self._emit("Checking frontend imports...")
        for rel_str in list(known):
            if not any(rel_str.endswith(e) for e in (".jsx", ".tsx", ".js", ".ts")):
                continue
            abs_path = frontend_dir / rel_str
            try:
                content = abs_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            file_dir = str(abs_path.parent.relative_to(frontend_dir)).replace("\\", "/")

            for m in re.finditer(r"""(?:import|from)\s+['"](\.[^'"]+)['"]""", content):
                imp = m.group(1)
                if file_dir == ".":
                    resolved = imp.lstrip("./")
                else:
                    resolved = str(Path(file_dir) / imp).replace("\\", "/").lstrip("./")

                found = any(
                    resolved + ext in known or resolved in known
                    for ext in exts
                )
                if not found:
                    errors.append({
                        "phase": "frontend_import",
                        "command": f"check_import({rel_str})",
                        "exit_code": 1,
                        "stderr": (
                            f"Broken import in `{rel_str}`: `from '{imp}'` resolves to "
                            f"`{resolved}` but no matching file found. "
                            f"Available: {[k for k in known if resolved.split('/')[-1] in k][:5]}"
                        ),
                        "stdout": "",
                    })

        if not errors:
            self._emit("Frontend imports OK")
        return errors

    def _phase_api_routes(self) -> list[dict]:
        errors = []
        frontend_dir = self.root / (self.conv.get("frontend_dir") or ".")
        backend_dir_name = self.conv.get("backend_dir")
        if not backend_dir_name:
            return errors
        backend_dir = self.root / backend_dir_name
        if not frontend_dir.exists() or not backend_dir.exists():
            return errors

        backend_routes: set[str] = set()
        for py_file in backend_dir.rglob("*.py"):
            if any(skip in str(py_file) for skip in (".venv", "__pycache__")):
                continue
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
                for m in re.finditer(r'@\w+\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']', content):
                    backend_routes.add(m.group(2).strip("/").split("{")[0].rstrip("/"))
                for m in re.finditer(r"""path\(['"]([^'"]+)['"]""", content):
                    backend_routes.add(m.group(1).strip("/").split("<")[0].rstrip("/"))
                for m in re.finditer(r"""router\.register\(r?['"]([^'"]+)['"]""", content):
                    backend_routes.add(m.group(1).strip("/"))
            except Exception:
                pass

        if not backend_routes:
            return errors

        for js_file in frontend_dir.rglob("*.js"):
            if "node_modules" in str(js_file) or "dist" in str(js_file):
                continue
            try:
                content = js_file.read_text(encoding="utf-8", errors="replace")
                for m in re.finditer(
                    r"""(?:axios|api|client)\.(get|post|put|delete|patch)\s*\(\s*[`'"](\/api\/[^`'"?]+)""",
                    content,
                ):
                    url = m.group(2).strip("/").replace("api/", "").strip("/").split("?")[0].split("${")[0].rstrip("/")
                    if url and not any(
                        url == r or r.startswith(url) or url.startswith(r)
                        for r in backend_routes
                    ):
                        rel = str(js_file.relative_to(self.root)).replace("\\", "/")
                        errors.append({
                            "phase": "api_route_mismatch",
                            "command": f"check_routes({rel})",
                            "exit_code": 1,
                            "stderr": (
                                f"Frontend call in `{rel}` to `/api/{url}` has no matching backend route. "
                                f"Backend routes: {sorted(backend_routes)[:10]}"
                            ),
                            "stdout": "",
                        })
            except Exception:
                pass

        return errors

    def _phase_frontend_install_build(self) -> list[dict]:
        """Run npm install + npm run build. Only on projects that have a package.json."""
        errors = []
        frontend_dir = self.root / (self.conv.get("frontend_dir") or ".")
        pkg_json = frontend_dir / "package.json"
        if not pkg_json.exists():
            return errors

        build_script = self.conv.get("package_json_scripts", {}).get("build", "build")
        # Use a shorter timeout for CI-like installs
        self._emit("Running npm install...")
        install_result = self._run(
            "npm install --prefer-offline --legacy-peer-deps",
            cwd=str(frontend_dir),
            timeout=180,
        )
        if not install_result["success"]:
            install_result["phase"] = "npm_install"
            errors.append(install_result)
            self._emit(f"npm install failed: {install_result['stderr'][:200]}")
            return errors

        self._emit(f"Running npm run {build_script}...")
        build_result = self._run(
            f"npm run {build_script} 2>&1",
            cwd=str(frontend_dir),
            timeout=120,
        )
        if not build_result["success"]:
            build_result["phase"] = "frontend_build"
            # Trim output to most useful part
            combined = (build_result.get("stdout", "") + "\n" + build_result.get("stderr", ""))
            # Find first error line
            error_lines = [l for l in combined.split("\n") if "error" in l.lower() or "Error" in l][:15]
            build_result["stderr"] = "\n".join(error_lines) or combined[:1000]
            errors.append(build_result)
            self._emit(f"Build failed: {build_result['stderr'][:200]}")
        else:
            self._emit("Frontend build OK")

        return errors


# ---------------------------------------------------------------------------
# ScaffoldPipeline
# ---------------------------------------------------------------------------

class ScaffoldPipeline:
    """
    Orchestrates the 6-pass scaffold pipeline.

    Usage:
        pipeline = ScaffoldPipeline(ai_config=ai_config, on_event=emit_fn)
        result = pipeline.run(
            description="...", tech_stack="React, Django",
            project_root=Path("/path/to/project")
        )
    """

    def __init__(
        self,
        ai_config: dict | None = None,
        on_event: Callable[[dict], None] | None = None,
    ):
        self.ai_config = ai_config
        self.on_event = on_event

    def _emit(self, event_type: str, message: str, data: dict | None = None) -> None:
        if self.on_event:
            try:
                self.on_event({"type": event_type, "message": message, **(data or {})})
            except Exception:
                pass
        logger.info("[pipeline:%s] %s", event_type, message)

    def run(
        self,
        description: str,
        tech_stack: str,
        project_root: Path | None = None,
    ) -> dict:
        # Resolve conventions — uses StackResolverAgent for unknown stacks (Pass 3)
        conventions = resolve_conventions(tech_stack, ai_config=self.ai_config)

        # Stage 1 — Spec
        self._emit("stage", "Stage 1/6: Expanding description into product spec", {"stage": 1})
        spec = self._run_spec(description, tech_stack)
        self._emit("spec_ready", (
            f"Spec: {spec.get('product_name')} — "
            f"{len(spec.get('pages', []))} pages, "
            f"{len(spec.get('data_models', []))} models, "
            f"{len(spec.get('api_endpoints', []))} endpoints"
        ))

        # Stage 1.5 — Wireframes (Pass 1)
        self._emit("stage", "Stage 1.5/6: Generating page wireframes", {"stage": 1})
        wireframes = self._run_wireframe(spec)
        self._emit("wireframe_ready", f"Wireframes: {len(wireframes)} pages")

        # Stage 1.6 — API contract (Pass 4)
        api_contract = _derive_api_contract(spec)
        self._emit("contract_ready", f"Contract: {len(api_contract.get('endpoints', []))} endpoints typed")

        # Stage 1.7 — Design system (domain-matched theme + Google Fonts + optional Stitch)
        has_react = "react" in str(conventions.get("frontend_framework", "")).lower()
        design_context: dict = {}
        if has_react:
            self._emit("stage", "Stage 1.7/6: Generating design system", {"stage": 1})
            design_context = self._run_design(spec, description)
            theme_name = design_context.get("base_theme_name", "default")
            stitch_note = " (Stitch reference generated)" if design_context.get("stitch_reference_url") else ""
            self._emit("design_ready", f"Design: {theme_name} theme, fonts={design_context.get('fonts', {})}{stitch_note}")

        # Stage 2 — File plan
        self._emit("stage", "Stage 2/6: Planning file structure with contracts", {"stage": 2})
        file_plan = self._run_plan(spec, tech_stack, wireframes)
        file_plan = self._adapt_file_plan_for_stack(file_plan, conventions, spec)

        # Pass 5 — Single-stack invariant guard
        file_plan = _enforce_single_stack(file_plan, conventions)
        self._emit("plan_ready", f"File plan: {len(file_plan)} files (stack-validated)")

        if conventions.get("vite_proxy"):
            file_plan = self._ensure_vite_config(file_plan, conventions)

        # Stage 2.5 — Template bootstrap (Pass 2)
        template_files = get_template_files(conventions, spec.get("design_system"))
        frozen_paths = get_frozen_paths(conventions)
        self._emit("templates_ready", f"Bootstrap: {len(template_files)} UI primitives frozen")

        # Stage 3 — Codegen (pass design tokens into constraint block)
        self._emit("stage", "Stage 3/6: Generating files", {"stage": 3})
        files = {**template_files}
        files.update(self._run_codegen(
            spec, file_plan, tech_stack, conventions,
            wireframes=wireframes,
            api_contract=api_contract,
            frozen_paths=frozen_paths,
            design_context=design_context,
        ))
        self._emit("codegen_done", f"Generated {len(files)} files (including {len(template_files)} primitives)")

        # Override config files with guaranteed-correct versions
        if conventions.get("vite_proxy") or conventions.get("import_style") == "frontend_mock":
            vite_path = self._find_vite_config_path(file_plan, conventions)
            files[vite_path] = get_vite_config(
                backend_port=conventions.get("backend_port"),
                frontend_port=conventions.get("frontend_port", 5173),
            )

        if has_react:
            tailwind_path = self._find_file_path(file_plan, "tailwind.config.js", conventions)
            index_css_path = self._find_file_path(file_plan, "src/index.css", conventions)
            # Use DesignAgent output if available, else static defaults
            if design_context.get("rendered_tailwind_config"):
                files[tailwind_path] = design_context["rendered_tailwind_config"]
            else:
                files[tailwind_path] = get_react_tailwind_config()
            if design_context.get("rendered_index_css"):
                files[index_css_path] = design_context["rendered_index_css"]
            else:
                files[index_css_path] = get_react_index_css()

        # Write to disk
        if project_root:
            self._write_files(files, project_root)

        # Stages 4–6 — Validate + Repair (Pass 6)
        if project_root:
            self._emit("stage", "Stage 4/6: Validating and repairing", {"stage": 4})
            files = self._repair_loop(files, spec, tech_stack, file_plan, conventions, project_root, wireframes, api_contract)

            # Build gate — only if frontend exists and we have npm
            self._emit("stage", "Stage 5/6: Build gate", {"stage": 5})
            files = self._build_gate(files, spec, tech_stack, file_plan, conventions, project_root, wireframes, api_contract)

        return {"files": files, "spec": spec, "file_plan": file_plan, "wireframes": wireframes}

    # ── Stages ───────────────────────────────────────────────────────────────

    def _run_spec(self, description: str, tech_stack: str) -> dict:
        try:
            agent = SpecAgent(ai_config=self.ai_config)
            spec = agent.expand(description=description, tech_stack=tech_stack)
            for key in ("pages", "data_models", "api_endpoints"):
                if not isinstance(spec.get(key), list):
                    spec[key] = []
            return spec
        except Exception as exc:
            logger.error("SpecAgent failed: %s", exc)
            return {
                "product_name": "App", "tagline": description,
                "tech_stack": {}, "personas": [], "pages": [],
                "data_models": [], "api_endpoints": [],
                "auth_model": "none", "seed_data_description": "",
                "key_user_flows": [],
            }

    def _run_design(self, spec: dict, description: str = "") -> dict:
        try:
            agent = DesignAgent(ai_config=self.ai_config)
            return agent.generate_design(spec, description)
        except Exception as exc:
            logger.error("DesignAgent failed: %s", exc)
            return {}

    def _run_wireframe(self, spec: dict) -> dict:
        try:
            agent = WireframeAgent(ai_config=self.ai_config)
            wireframes = agent.wireframe(spec)
            return wireframes or {}
        except Exception as exc:
            logger.error("WireframeAgent failed: %s", exc)
            return {}

    def _run_plan(self, spec: dict, tech_stack: str, wireframes: dict | None = None) -> list[dict]:
        try:
            agent = FilePlanAgent(ai_config=self.ai_config)
            plan = agent.plan(spec=spec, tech_stack=tech_stack, wireframes=wireframes)
            if plan:
                return plan
        except Exception as exc:
            logger.error("FilePlanAgent failed: %s", exc)
        return self._fallback_plan(spec, tech_stack)

    def _run_codegen(
        self,
        spec: dict,
        file_plan: list[dict],
        tech_stack: str,
        conventions: dict,
        wireframes: dict | None = None,
        api_contract: dict | None = None,
        frozen_paths: set[str] | None = None,
        design_context: dict | None = None,
    ) -> dict[str, str]:
        constraint_block = build_constraint_block(tech_stack)
        # Append design system info to the constraint block so every file knows the tokens
        if design_context:
            fonts = design_context.get("fonts", {})
            theme_name = design_context.get("base_theme_name", "")
            stitch_ref = design_context.get("stitch_reference_url", "")
            design_addendum = (
                f"\n## Design System\n"
                f"Theme: {theme_name}\n"
                f"Fonts: display='{fonts.get('display', 'Inter')}' body='{fonts.get('body', 'Inter')}'\n"
                f"Google Fonts URL: {design_context.get('google_fonts_url', '')}\n"
                f"CSS tokens available as Tailwind: bg-background, bg-primary, text-foreground, "
                f"bg-card, text-muted-foreground, bg-secondary, text-accent-foreground, border-border\n"
                f"Typography classes: display-xl, display-lg, display-md, display-sm, body-lg, body-md, gradient-text\n"
                f"Use font-display for headings, font-body for body text (both wired in tailwind.config.js).\n"
            )
            if stitch_ref:
                design_addendum += f"Visual reference (Stitch screenshot): {stitch_ref}\n"
            constraint_block += design_addendum

        full_plan_paths = [e["path"] for e in file_plan]
        generated: dict[str, str] = {}
        frozen = frozen_paths or set()

        layer_order = [
            "config", "model", "schema", "serializer", "view", "url",
            "frontend-config", "frontend-api", "component", "page", "entry", "seed", "other",
        ]
        layer_groups: dict[str, list[dict]] = {l: [] for l in layer_order}
        for entry in file_plan:
            layer = entry.get("layer", "other")
            if entry["path"] in frozen:
                continue  # skip frozen template files
            layer_groups.setdefault(layer, []).append(entry)

        parallelisable = {"component", "page", "schema", "serializer"}

        for layer in layer_order:
            entries = layer_groups.get(layer, [])
            if not entries:
                continue
            if layer in parallelisable and len(entries) > 1:
                self._emit("codegen_layer", f"Generating {len(entries)} {layer} files (parallel)")
                self._codegen_parallel(entries, spec, generated, constraint_block, full_plan_paths, wireframes, api_contract)
            else:
                for entry in entries:
                    self._codegen_one(entry, spec, generated, constraint_block, full_plan_paths, wireframes, api_contract)

        return generated

    def _get_page_wireframe(self, file_path: str, wireframes: dict | None) -> dict | None:
        """Match a page file path to its wireframe by route."""
        if not wireframes:
            return None
        file_stem = Path(file_path).stem.lower()
        for route, wf in wireframes.items():
            if not isinstance(wf, dict):
                continue
            wf_name = str(wf.get("name", "")).lower()
            route_slug = route.strip("/").split("/")[0].lower() or "home"
            if file_stem in (wf_name, route_slug, route_slug + "page") or wf_name in file_stem:
                return wf
        if file_stem in ("home", "landing", "index", "landingpage", "homepage"):
            return wireframes.get("/") or wireframes.get("")
        return None

    def _codegen_one(self, entry, spec, generated, constraint_block, full_plan_paths, wireframes, api_contract):
        path = entry["path"]
        dep_contents = {dep: generated[dep] for dep in entry.get("depends_on", []) if dep in generated}
        wireframe = self._get_page_wireframe(path, wireframes)
        self._emit("file_start", f"Generating {path}")
        try:
            agent = FileCodeAgent(ai_config=self.ai_config)
            content = agent.generate_file(
                file_path=path, file_desc=entry, spec=spec,
                dep_contents=dep_contents, constraint_block=constraint_block,
                full_plan_paths=full_plan_paths,
                wireframe=wireframe,
                api_contract=api_contract,
            )
            generated[path] = content
            self._emit("file_done", f"Done: {path}")
        except Exception as exc:
            logger.error("FileCodeAgent failed %s: %s", path, exc)
            self._emit("file_error", f"Failed: {path} — {exc}")

    def _codegen_parallel(self, entries, spec, generated, constraint_block, full_plan_paths, wireframes, api_contract):
        def _task(entry):
            path = entry["path"]
            dep_contents = {dep: generated[dep] for dep in entry.get("depends_on", []) if dep in generated}
            wireframe = self._get_page_wireframe(path, wireframes)
            agent = FileCodeAgent(ai_config=self.ai_config)
            return path, agent.generate_file(
                file_path=path, file_desc=entry, spec=spec,
                dep_contents=dep_contents, constraint_block=constraint_block,
                full_plan_paths=full_plan_paths,
                wireframe=wireframe,
                api_contract=api_contract,
            )

        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_FILES) as ex:
            futures = {ex.submit(_task, e): e["path"] for e in entries}
            for future in as_completed(futures):
                path = futures[future]
                try:
                    fp, content = future.result()
                    generated[fp] = content
                    self._emit("file_done", f"Done: {fp}")
                except Exception as exc:
                    logger.error("Parallel codegen failed %s: %s", path, exc)

    # ── Repair loop ───────────────────────────────────────────────────────────

    def _repair_loop(self, files, spec, tech_stack, file_plan, conventions, project_root, wireframes=None, api_contract=None):
        validator = ExecValidator(project_root, conventions, on_event=self.on_event)

        for round_num in range(1, MAX_REPAIR_ROUNDS + 1):
            self._emit("validate_start", f"Validation round {round_num}/{MAX_REPAIR_ROUNDS}")
            errors = validator.run_all()

            if not errors:
                self._emit("validate_ok", f"Round {round_num}: Clean — no errors")
                break

            renames = [e for e in errors if e.get("file_to_rename")]
            other_errors = [e for e in errors if not e.get("file_to_rename")]

            if renames:
                for rename_info in renames:
                    files = self._apply_rename(rename_info["file_to_rename"], files, project_root)
                if not other_errors:
                    continue

            if not other_errors:
                continue

            self._emit(
                "validate_errors",
                f"Round {round_num}: {len(other_errors)} error(s) — calling RepairAgent",
                {"error_count": len(other_errors)},
            )

            agent = RepairAgent(ai_config=self.ai_config)
            fixes = agent.repair(
                errors=other_errors, all_files=files,
                spec=spec, tech_stack=tech_stack, file_plan=file_plan,
            )

            if not fixes:
                self._emit("repair_no_fixes", f"Round {round_num}: RepairAgent had no fixes")
                break

            for path, content in fixes.items():
                files[path] = content
                target = project_root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                self._emit("file_repaired", f"Repaired: {path}")

            if round_num == MAX_REPAIR_ROUNDS:
                self._emit("repair_exhausted", "Max repair rounds reached")

        return files

    def _build_gate(self, files, spec, tech_stack, file_plan, conventions, project_root, wireframes=None, api_contract=None):
        """Run npm build; if it fails, pass errors to RepairAgent for one more round."""
        frontend_dir = project_root / (conventions.get("frontend_dir") or ".")
        pkg_json = frontend_dir / "package.json"
        if not pkg_json.exists():
            return files

        validator = ExecValidator(project_root, conventions, on_event=self.on_event)
        build_errors = validator.run_build_gate()

        if not build_errors:
            self._emit("build_ok", "Frontend build passed")
            return files

        self._emit("build_failed", f"{len(build_errors)} build error(s) — repair pass", {"error_count": len(build_errors)})
        agent = RepairAgent(ai_config=self.ai_config)
        fixes = agent.repair(
            errors=build_errors, all_files=files,
            spec=spec, tech_stack=tech_stack, file_plan=file_plan,
        )
        if fixes:
            for path, content in fixes.items():
                files[path] = content
                target = project_root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                self._emit("file_repaired", f"Build-repair: {path}")

        return files

    def _apply_rename(self, rename: dict, files: dict, project_root: Path) -> dict:
        from_path, to_path = rename["from"], rename["to"]
        if from_path in files:
            content = files.pop(from_path)
            files[to_path] = content
            old_disk = project_root / from_path
            new_disk = project_root / to_path
            new_disk.parent.mkdir(parents=True, exist_ok=True)
            if old_disk.exists():
                old_disk.rename(new_disk)
            else:
                new_disk.write_text(content, encoding="utf-8")
            self._emit("file_renamed", f"Renamed {from_path} → {to_path}")
        return files

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _write_files(self, files: dict[str, str], project_root: Path) -> None:
        for rel_path, content in files.items():
            target = project_root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    def _ensure_vite_config(self, file_plan: list[dict], conventions: dict) -> list[dict]:
        frontend_dir = conventions.get("frontend_dir", "frontend")
        if not any("vite.config" in e["path"] for e in file_plan):
            file_plan.insert(0, {
                "path": f"{frontend_dir}/vite.config.js",
                "layer": "frontend-config",
                "depends_on": [],
                "description": "Vite config with proxy",
                "exact_imports": [],
                "max_lines": 20,
            })
        return file_plan

    def _find_vite_config_path(self, file_plan: list[dict], conventions: dict) -> str:
        for e in file_plan:
            if "vite.config" in e["path"]:
                return e["path"]
        return f"{conventions.get('frontend_dir', 'frontend')}/vite.config.js"

    def _find_file_path(self, file_plan: list[dict], suffix: str, conventions: dict) -> str:
        suffix = suffix.replace("\\", "/").lstrip("./")
        for e in file_plan:
            path = str(e.get("path", "")).replace("\\", "/")
            if path.endswith(suffix):
                return path
        frontend_dir = conventions.get("frontend_dir") or "."
        if frontend_dir == ".":
            return suffix
        return f"{frontend_dir.rstrip('/')}/{suffix}"

    def _adapt_file_plan_for_stack(self, file_plan: list[dict], conventions: dict, spec: dict | None = None) -> list[dict]:
        """Apply non-negotiable stack constraints after the LLM plan."""
        has_react_frontend = "react" in str(conventions.get("frontend_framework", "")).lower()
        if not has_react_frontend:
            return file_plan

        frontend_only = conventions.get("import_style") == "frontend_mock"
        frontend_dir = conventions.get("frontend_dir") or "."
        prefix = "" if frontend_dir == "." else f"{frontend_dir.strip('/')}/"
        src_prefix = f"{prefix}src/"
        mock_path = f"{src_prefix}mockData.js"

        blocked_layers = {"frontend-api", "model", "schema", "serializer", "view", "url", "seed"} if frontend_only else set()
        blocked_fragments = (
            "backend/", "/backend/", "src/api/", "api/client",
        ) if frontend_only else ()
        kept: list[dict] = []
        for entry in file_plan:
            path = str(entry.get("path", "")).replace("\\", "/").lstrip("./")
            if prefix and path.startswith("src/"):
                path = f"{prefix}{path}"
            elif prefix and path in {"package.json", "vite.config.js", "tailwind.config.js", "postcss.config.js", "index.html"}:
                path = f"{prefix}{path}"
            layer = str(entry.get("layer", ""))
            description = str(entry.get("description", "")).lower()
            if layer in blocked_layers:
                continue
            if any(fragment in path.lower() or fragment in description for fragment in blocked_fragments):
                continue
            entry = {**entry, "path": path}
            kept.append(entry)

        if not any(entry.get("path") == mock_path for entry in kept):
            kept.insert(0, {
                "path": mock_path,
                "layer": "frontend-config",
                "depends_on": [],
                "description": (
                    "Rich frontend demo data for the ENTIRE app — every page imports from this file. "
                    "Export at minimum: primaryItems (30+ records with full fields: id, title, description, "
                    "category, status, image, rating, price/date, tags, metadata relevant to domain), "
                    "categories (10+ with name, count, icon, color), activity (30+ timeline/history records "
                    "with date, title, body, status, user), dashboardMetrics (8+ KPI objects with label, "
                    "value, trend, detail, icon), userProfile (demo user with name, email, role, avatar, "
                    "preferences, stats), messages (10+ with sender, preview, timestamp, unread), "
                    "testimonials (8+ with quote, name, role, company, avatar, rating), "
                    "pricingTiers (3 tiers: free/pro/enterprise with features list), "
                    "faqItems (10+ Q&A pairs), processSteps (5+ numbered steps with icon+title+desc), "
                    "featuredItems (6+ highlighted records), savedItems (8+ user-bookmarked records). "
                    "Use https://images.unsplash.com/photo-<real-id>?w=800 for images. "
                    "Export helper functions: getById(id), getByCategory(cat), filterByStatus(status), "
                    "getRelated(id). No fetch, axios, or network calls. Min 600 lines."
                ),
                "exact_imports": [],
                "max_lines": 700,
            })

        for entry in kept:
            if entry.get("layer") == "frontend-api" or "/src/api/" in str(entry.get("path", "")):
                entry["description"] = (
                    f"{entry.get('description', '')} IMPORTANT: API functions must catch all errors "
                    f"and return matching mock data from {mock_path} when backend is unavailable. "
                    "Pages must stay populated before backend is ready."
                ).strip()

        if spec is not None:
            ext = conventions.get("file_extensions", {}).get("components", ".jsx")
            page_ext = conventions.get("file_extensions", {}).get("pages", ".jsx")
            rich_pages = self._rich_frontend_pages(spec)

            # Shared components — always generated (not frozen templates)
            shared_components = {
                f"{src_prefix}components/AppShell{ext}": (
                    "Full app shell: sticky top nav with logo, all page links (Home, Explore, Dashboard, About, "
                    "Login/Register or user avatar+dropdown when logged in), mobile hamburger menu that opens "
                    "a full slide-out. Footer with brand, 4 link columns (Product, Company, Legal, Social), "
                    "newsletter input, copyright. Use lucide-react icons. Import NavLink from react-router-dom. "
                    "Active link gets highlighted style. Min 200 lines."
                ),
                f"{src_prefix}components/StatCard{ext}": (
                    "KPI card: icon (lucide), label, large value, trend arrow+%, detail line, colored background "
                    "based on tone (success/warning/info/neutral). Import Card from components/ui/card. "
                    "Props: label, value, detail, icon, tone, trend, trendValue."
                ),
                f"{src_prefix}components/ItemCard{ext}": (
                    "Domain item card: aspect-ratio image with lazy load, category Badge top-left overlay, "
                    "title (2-line clamp), short description, metadata row (rating stars, price or date, "
                    "status Badge), action buttons (View Details + secondary action). Hover: lift + shadow. "
                    "Import Card, Badge, Button from components/ui/. Min 150 lines."
                ),
                f"{src_prefix}components/TabbedPanel{ext}": (
                    "Tabs with local active-tab state, animated underline indicator, tab count badges, "
                    "and rendered children panels. Import Tabs/TabsList/TabsTrigger/TabsContent from "
                    "components/ui/tabs. Props: tabs=[{id,label,count?,icon?}], children mapped by tab id."
                ),
                f"{src_prefix}components/TimelineList{ext}": (
                    "Vertical timeline: connector line, colored dot by status, item with icon, title, "
                    "body text (2-3 lines), timestamp, Badge status chip, expandable detail on click. "
                    "Import Badge from components/ui/badge. Min 120 lines."
                ),
                f"{src_prefix}components/SearchFilterBar{ext}": (
                    "Full search+filter bar: text search input with icon, 4-6 category pill buttons "
                    "(All + specific), sort dropdown Select, results count text. All controlled via "
                    "props: searchTerm, onSearchChange, activeFilter, onFilterChange, sortBy, onSortChange, "
                    "resultCount, filters=[]. Import Input, Select, Button from components/ui/."
                ),
                f"{src_prefix}components/PageHero{ext}": (
                    "Reusable page hero for inner pages: background gradient/image, breadcrumb nav, "
                    "large heading, sub text, optional CTA buttons, optional tag/badge. "
                    "Props: title, sub, cta, breadcrumbs, image, badge. Min 80 lines."
                ),
            }

            for jsx_path, description in shared_components.items():
                path = jsx_path[:-4] + ext if ext != ".jsx" else jsx_path
                if not any(entry.get("path") == path for entry in kept):
                    kept.append({
                        "path": path,
                        "layer": "component",
                        "depends_on": [mock_path] if "ItemCard" in path or "SearchFilter" in path else [],
                        "description": description,
                        "exact_imports": ["import React from 'react'"],
                        "max_lines": 220,
                    })

            shared_deps = [
                mock_path,
                f"{src_prefix}components/AppShell{ext}",
                f"{src_prefix}components/StatCard{ext}",
                f"{src_prefix}components/ItemCard{ext}",
                f"{src_prefix}components/TabbedPanel{ext}",
                f"{src_prefix}components/TimelineList{ext}",
                f"{src_prefix}components/SearchFilterBar{ext}",
                f"{src_prefix}components/PageHero{ext}",
            ]
            existing_page_paths = {entry.get("path") for entry in kept if str(entry.get("path", "")).startswith(f"{src_prefix}pages/")}
            for entry in kept:
                if not str(entry.get("path", "")).startswith(f"{src_prefix}pages/"):
                    continue
                entry["depends_on"] = sorted(set(entry.get("depends_on", []) + shared_deps))
                entry["max_lines"] = max(entry.get("max_lines", 0), 500)
                entry["description"] = (
                    f"{entry.get('description', '')} "
                    "CRITICAL — SELF-CONTAINED PAGE: ALL section content must be inline in this file. "
                    "Do NOT create sub-components or split into separate files. "
                    "Write every section as a <section> block directly in this component's return(). "
                    f"Import data from {mock_path}. Import shared components and UI primitives. "
                    "Minimum 8 distinct visual sections. Min 400 lines. "
                    "Never show an empty shell or placeholder."
                ).strip()

            for page in rich_pages:
                path = f"{src_prefix}pages/{page['name']}{page_ext}"
                if path in existing_page_paths:
                    continue
                kept.append({
                    "path": path,
                    "layer": "page",
                    "depends_on": shared_deps,
                    "description": (
                        f"Route {page['route']}: {page['purpose']}. "
                        "SELF-CONTAINED PAGE — write ALL sections inline, no sub-components. "
                        "Sections must be coded directly in this file's return(). "
                        "Include: navbar (AppShell), hero/header section, at least 6 content sections "
                        "with real data from mockData, and footer where appropriate. "
                        "Use local useState for interactions (search/filter/tabs/forms/modals). "
                        "Import Button, Card, Badge, Tabs, Input, Avatar, etc. from components/ui/. "
                        "Min 400 lines. Every section populated with real data, no empty states."
                    ),
                    "exact_imports": ["import React, { useMemo, useState } from 'react'"],
                    "max_lines": 550,
                })
                existing_page_paths.add(path)

            app_path = f"{src_prefix}App{ext}"
            route_summary = ", ".join(f"{page['route']}={page['name']}" for page in rich_pages)
            app_deps = [f"{src_prefix}pages/{page['name']}{page_ext}" for page in rich_pages]
            app_entry = next((entry for entry in kept if entry.get("path") == app_path), None)
            if app_entry:
                app_entry["depends_on"] = sorted(set(app_entry.get("depends_on", []) + app_deps))
                app_entry["description"] = (
                    f"React Router v6 app with these routes: {route_summary}. "
                    "Include app shell/navigation, a not-found route, and a frontend-first demo."
                )
            else:
                kept.append({
                    "path": app_path,
                    "layer": "entry",
                    "depends_on": app_deps,
                    "description": f"React Router v6 app with routes: {route_summary}. Wrap in AppShell. Include 404 redirect.",
                    "exact_imports": ["import { BrowserRouter, Routes, Route } from 'react-router-dom'"],
                    "max_lines": 80,
                })

        available = {entry["path"] for entry in kept}
        for entry in kept:
            deps = [str(dep).replace("\\", "/").lstrip("./") for dep in entry.get("depends_on", [])]
            deps = [
                f"{prefix}{dep}" if prefix and dep.startswith("src/") else
                f"{prefix}{dep}" if prefix and dep in {"package.json", "vite.config.js", "tailwind.config.js", "postcss.config.js", "index.html"} else
                dep
                for dep in deps
            ]
            deps = [dep for dep in deps if dep in available]
            if entry["path"].startswith(src_prefix) and entry["path"] != mock_path:
                if mock_path in available and mock_path not in deps and entry.get("layer") in {"component", "page", "entry", "frontend-api"}:
                    deps.insert(0, mock_path)
            entry["depends_on"] = deps

        return kept

    def _safe_component_name(self, value: str, fallback: str) -> str:
        parts = re.findall(r"[A-Za-z0-9]+", str(value or ""))
        name = "".join(part[:1].upper() + part[1:] for part in parts) or fallback
        if name[0].isdigit():
            name = f"{fallback}{name}"
        return name

    def _rich_frontend_pages(self, spec: dict) -> list[dict]:
        pages: list[dict] = []
        seen_routes: set[str] = set()
        seen_names: set[str] = set()

        for page in spec.get("pages", []):
            if not isinstance(page, dict):
                continue
            route = str(page.get("route") or "").strip() or "/"
            name = self._safe_component_name(page.get("name") or route, "Page")
            if route in seen_routes or name in seen_names:
                continue
            pages.append({
                "route": route, "name": name,
                "purpose": page.get("purpose") or "Domain-specific page backed by mock data",
                "components": page.get("components", []),
                "api_calls": [],
            })
            seen_routes.add(route)
            seen_names.add(name)

        # Core app pages
        core_defaults = [
            ("/", "Home",
             "LANDING PAGE — full marketing page: sticky navbar, hero with headline+sub+2 CTAs+hero image, "
             "logo cloud (6 partner/trust logos), feature grid (6 cards with icon+title+body), stats band "
             "(4 impressive numbers), testimonials carousel (6 quotes), pricing tiers (3 plans with feature "
             "lists), FAQ accordion (8 Q&As), final CTA band, footer with 4 link columns. Min 600 lines."),
            ("/explore", "Explore",
             "BROWSE/CATALOG PAGE — SearchFilterBar at top, active filter chips, sort controls, "
             "results count, 12-item grid of ItemCards with pagination, sidebar with facets/filters, "
             "featured/promoted items section at top, empty-state with suggestions. Min 400 lines."),
            ("/detail/:id", "Detail",
             "DETAIL PAGE — large hero image with overlay, entity title+badges, tabbed content "
             "(Overview, Details, Reviews/Activity, Related), sticky right-side summary card with CTA, "
             "metadata grid, activity timeline, related items carousel, breadcrumb. Min 450 lines."),
            ("/workflow/:id", "Workflow",
             "WORKFLOW/ACTION PAGE — multi-step wizard: step indicator bar at top, step 1 (selection "
             "grid from mockData), step 2 (config form with real fields), step 3 (review summary card), "
             "step 4 (confirmation + success animation). Local state for all steps. Min 400 lines."),
            ("/dashboard", "Dashboard",
             "DASHBOARD PAGE — header with user greeting+avatar, 4 KPI StatCards row, tabbed workspace "
             "(Upcoming: timeline list, Activity: feed, Saved: item grid, Insights: charts placeholder), "
             "quick-action buttons, recent notifications panel, progress indicators. Min 450 lines."),
            ("/history", "History",
             "HISTORY/RECORDS PAGE — filter bar with date range + status filter, sortable table with "
             "10+ columns, row actions (view/download/delete), pagination, export button, summary stats "
             "above table, expandable row detail, status badges. Min 400 lines."),
        ]
        for route, name, purpose in core_defaults:
            if route not in seen_routes and name not in seen_names:
                pages.append({"route": route, "name": name, "purpose": purpose,
                               "components": ["AppShell", "StatCard", "ItemCard"], "api_calls": []})
                seen_routes.add(route)
                seen_names.add(name)

        # Auth + utility pages — always added regardless of spec
        auth_defaults = [
            ("/login", "Login",
             "LOGIN PAGE — centered card layout, product logo+tagline at top, email+password inputs "
             "with validation states, 'Remember me' checkbox, 'Forgot password?' link, Login button, "
             "social login buttons (Google, GitHub), divider, link to Register, trust badges at bottom. "
             "Local state for form. Min 250 lines."),
            ("/register", "Register",
             "REGISTER PAGE — centered card, logo at top, full-name+email+password+confirm fields with "
             "live validation (password strength meter, match indicator), terms checkbox with link, "
             "Register button, social signup options, link to Login. Local state for all fields. Min 280 lines."),
            ("/about", "About",
             "ABOUT PAGE — hero with mission statement, team grid (8 members with photo+name+role+bio), "
             "company timeline (6 milestone events), values/principles section (4 cards), press/media logos, "
             "join-us CTA, contact info. Min 400 lines."),
            ("/settings", "Settings",
             "SETTINGS PAGE — left sidebar with setting categories (Profile, Account, Notifications, "
             "Privacy, Billing, Integrations), main panel with forms per category, profile photo upload, "
             "form inputs for all settings, save/cancel buttons, danger zone section. Min 400 lines."),
        ]
        for route, name, purpose in auth_defaults:
            if route not in seen_routes and name not in seen_names:
                pages.append({"route": route, "name": name, "purpose": purpose,
                               "components": ["AppShell"], "api_calls": []})
                seen_routes.add(route)
                seen_names.add(name)

        return pages

    def _fallback_plan(self, spec: dict, tech_stack: str) -> list[dict]:
        conventions = resolve_conventions(tech_stack, ai_config=self.ai_config)
        backend = conventions.get("backend_dir", "backend")
        frontend = conventions.get("frontend_dir", "frontend")
        ext = conventions.get("file_extensions", {}).get("components", ".jsx")
        page_ext = conventions.get("file_extensions", {}).get("pages", ".jsx")
        is_fastapi = "fastapi" in (conventions.get("backend_framework") or "").lower()
        is_django = "django" in (conventions.get("backend_framework") or "").lower()
        db_import = "from database import engine, SessionLocal, Base, get_db"

        plan = []

        if is_fastapi:
            plan += [
                {"path": f"{backend}/requirements.txt", "layer": "config", "depends_on": [], "description": "fastapi, uvicorn[standard], sqlalchemy, pydantic, python-jose[cryptography], passlib[bcrypt], python-multipart", "exact_imports": [], "max_lines": 20},
                {"path": f"{backend}/database.py", "layer": "config", "depends_on": [], "description": "SQLAlchemy engine (SQLite ./app.db), SessionLocal, Base, get_db generator", "exact_imports": [], "max_lines": 30},
                {"path": f"{backend}/models.py", "layer": "model", "depends_on": [f"{backend}/database.py"], "description": f"SQLAlchemy models: {', '.join(m['name'] for m in spec.get('data_models', []) if isinstance(m, dict))}", "exact_imports": [db_import], "max_lines": 200},
                {"path": f"{backend}/schemas.py", "layer": "schema", "depends_on": [f"{backend}/models.py"], "description": "Pydantic v2 schemas. Include Create, Response, and Update variants.", "exact_imports": ["from pydantic import BaseModel"], "max_lines": 200},
                {"path": f"{backend}/main.py", "layer": "entry", "depends_on": [f"{backend}/database.py", f"{backend}/models.py"], "description": "FastAPI app, CORS allow_all, create_all tables, include all routers", "exact_imports": ["from fastapi import FastAPI", "from fastapi.middleware.cors import CORSMiddleware"], "max_lines": 60},
                {"path": f"{backend}/seed.py", "layer": "seed", "depends_on": [f"{backend}/models.py", f"{backend}/database.py"], "description": f"Seed script: {spec.get('seed_data_description', '15+ realistic records per model')}", "exact_imports": [db_import, "from models import *"], "max_lines": 350},
            ]
        elif is_django:
            plan += [
                {"path": f"{backend}/requirements.txt", "layer": "config", "depends_on": [], "description": "django, djangorestframework, django-cors-headers", "exact_imports": [], "max_lines": 10},
                {"path": f"{backend}/manage.py", "layer": "config", "depends_on": [], "description": "Standard Django manage.py", "exact_imports": [], "max_lines": 20},
                {"path": f"{backend}/project/settings.py", "layer": "config", "depends_on": [], "description": "Django settings, INSTALLED_APPS includes rest_framework, corsheaders. CORS allow all. SQLite.", "exact_imports": [], "max_lines": 60},
                {"path": f"{backend}/project/urls.py", "layer": "url", "depends_on": [], "description": "Include api/ urls", "exact_imports": [], "max_lines": 15},
                {"path": f"{backend}/api/models.py", "layer": "model", "depends_on": [], "description": f"Django models: {', '.join(m['name'] for m in spec.get('data_models', []) if isinstance(m, dict))}", "exact_imports": ["from django.db import models"], "max_lines": 150},
                {"path": f"{backend}/api/serializers.py", "layer": "serializer", "depends_on": [f"{backend}/api/models.py"], "description": "DRF ModelSerializers for all models", "exact_imports": ["from rest_framework import serializers", "from .models import *"], "max_lines": 100},
                {"path": f"{backend}/api/views.py", "layer": "view", "depends_on": [f"{backend}/api/serializers.py"], "description": f"DRF ViewSets for: {', '.join(e['method']+' '+e['path'] for e in spec.get('api_endpoints', [])[:8] if isinstance(e, dict))}", "exact_imports": ["from rest_framework import viewsets", "from .models import *", "from .serializers import *"], "max_lines": 150},
                {"path": f"{backend}/api/urls.py", "layer": "url", "depends_on": [f"{backend}/api/views.py"], "description": "DRF DefaultRouter registering all viewsets", "exact_imports": ["from rest_framework.routers import DefaultRouter"], "max_lines": 25},
                {"path": f"{backend}/seed.py", "layer": "seed", "depends_on": [f"{backend}/api/models.py"], "description": f"Django seed: {spec.get('seed_data_description', '')}", "exact_imports": [], "max_lines": 300},
            ]

        if conventions.get("vite_proxy") or "react" in tech_stack.lower():
            frontend_only = conventions.get("import_style") == "frontend_mock"
            frontend_pages = self._rich_frontend_pages(spec)
            prefix = "" if frontend == "." else f"{frontend}/"
            mock_dep = f"{prefix}src/mockData.js"
            api_dep = f"{prefix}src/api/client.js"
            shared_component_paths = [
                f"{prefix}src/components/AppShell{ext}",
                f"{prefix}src/components/StatCard{ext}",
                f"{prefix}src/components/ItemCard{ext}",
                f"{prefix}src/components/TabbedPanel{ext}",
                f"{prefix}src/components/TimelineList{ext}",
            ]
            page_deps = [mock_dep] + ([] if frontend_only else [api_dep]) + shared_component_paths
            plan += [
                {"path": f"{prefix}package.json", "layer": "frontend-config", "depends_on": [], "description": f"React 18, vite {conventions.get('vite_version','^4.5.2')}, @vitejs/plugin-react, react-router-dom@6, tailwindcss, lucide-react. Scripts: dev=vite, build=vite build", "exact_imports": [], "max_lines": 35},
                {"path": f"{prefix}vite.config.js", "layer": "frontend-config", "depends_on": [], "description": "Vite config. Include server.port and proxy if backend exists.", "exact_imports": [], "max_lines": 15},
                {"path": f"{prefix}tailwind.config.js", "layer": "frontend-config", "depends_on": [], "description": "Tailwind content glob", "exact_imports": [], "max_lines": 10},
                {"path": f"{prefix}index.html", "layer": "entry", "depends_on": [], "description": "HTML shell with div#root and script type=module src=/src/main.jsx", "exact_imports": [], "max_lines": 15},
                {"path": mock_dep, "layer": "frontend-config", "depends_on": [], "description": f"Rich mock data for entire app: {spec.get('seed_data_description', '30+ primary records, 30+ activity, 8+ categories, KPIs, testimonials, pricing, FAQ, team, steps')}. Export primaryItems(30+), categories(10+), activity(30+), dashboardMetrics(8+), userProfile, messages(10+), testimonials(8+), pricingTiers(3), faqItems(10+), processSteps(5+), featuredItems(6+), savedItems(8+). Helper fns: getById, getByCategory, filterByStatus, getRelated. Min 600 lines.", "exact_imports": [], "max_lines": 700},
            ]
            if not frontend_only:
                plan.append({"path": api_dep, "layer": "frontend-api", "depends_on": [mock_dep], "description": f"Axios API client with fallback to mock data on every error. Endpoints: {', '.join(e['method']+' '+e['path'] for e in spec.get('api_endpoints', [])[:10] if isinstance(e, dict))}", "exact_imports": ["import axios from 'axios'"], "max_lines": 200})
            plan += [
                *[{"path": f"{prefix}src/pages/{p['name']}{page_ext}", "layer": "page", "depends_on": page_deps, "description": f"Route {p['route']}: {p['purpose']} SELF-CONTAINED — all sections inline, no sub-components. Min 400 lines.", "exact_imports": ["import React, { useMemo, useState } from 'react'"], "max_lines": 550} for p in frontend_pages],
                {"path": f"{prefix}src/App{ext}", "layer": "entry", "depends_on": [f"{prefix}src/pages/{p['name']}{page_ext}" for p in frontend_pages], "description": f"React Router v6 routes: {', '.join(p['route']+'='+p['name'] for p in frontend_pages)}. Wrap in AppShell.", "exact_imports": ["import { BrowserRouter, Routes, Route } from 'react-router-dom'"], "max_lines": 80},
                {"path": f"{prefix}src/main{ext}", "layer": "entry", "depends_on": [f"{prefix}src/App{ext}"], "description": "ReactDOM.createRoot('#root').render(<App/>)", "exact_imports": ["import React from 'react'", "import ReactDOM from 'react-dom/client'"], "max_lines": 12},
                {"path": f"{prefix}src/index.css", "layer": "frontend-config", "depends_on": [], "description": "@tailwind base/components/utilities + CSS custom properties for design tokens.", "exact_imports": [], "max_lines": 80},
                {"path": f"{prefix}postcss.config.js", "layer": "frontend-config", "depends_on": [], "description": "PostCSS with tailwindcss and autoprefixer", "exact_imports": [], "max_lines": 8},
            ]

        return plan


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _strip_fences(content: str, path: str = "") -> str:
    content = content.strip()
    m = re.match(r'^```[a-zA-Z0-9]*\n([\s\S]*?)```\s*$', content)
    if m:
        return m.group(1)
    if content.startswith("```"):
        lines = content.split("\n")
        lines = lines[1:] if lines[0].startswith("```") else lines
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines)
    return content
