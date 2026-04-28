"""
Multi-stage scaffold pipeline.

Stage 1 — SpecAgent:       user line + hard stack constraint → product spec JSON
Stage 2 — FilePlanAgent:   spec → ordered file plan with per-file contracts
Stage 3 — FileCodeAgent:   each file gets its own LLM call (parallel within layer)
Stage 4 — ExecValidator:   syntax check → import check → jsx-in-ts extension fix
Stage 5 — RepairAgent:     real errors → LLM fixes broken files → repeat up to MAX_REPAIR_ROUNDS
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
from agents.coding.stack_conventions import (
    get_conventions,
    build_constraint_block,
    get_vite_config,
    get_react_tailwind_config,
    get_react_index_css,
)

logger = logging.getLogger(__name__)

MAX_PARALLEL_FILES = 6
MAX_REPAIR_ROUNDS = 3


# ---------------------------------------------------------------------------
# FileCodeAgent
# ---------------------------------------------------------------------------

class FileCodeAgent(BaseAgent):
    """Generates a single file given spec, conventions, and dependency content."""

    def __init__(self, ai_config: dict | None = None):
        super().__init__(
            role="Senior Software Engineer",
            system_instruction=(
                "You are a senior engineer writing one specific file for a project. "
                "You receive exact architectural constraints, a precise file contract, "
                "and the content of every file this file depends on. "
                "Write COMPLETE, WORKING code. No TODO placeholders, no 'coming soon', "
                "no lorem ipsum. For any React frontend, rich realistic local demo "
                "data in `src/mockData.js` (or `frontend/src/mockData.js`) is required "
                "and should not be treated as a stub. Pages must look complete on first "
                "load even when backend APIs are unavailable. "
                "Every import must reference a real package or a file listed in the plan. "
                "Follow the import rules EXACTLY — flat imports if specified, no package prefix. "
                "Return ONLY the raw file content — no JSON wrapper, no markdown fences."
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
    ) -> str:
        ext = Path(file_path).suffix
        lang_map = {
            ".py": "Python", ".jsx": "React JSX", ".tsx": "React TSX",
            ".js": "JavaScript", ".ts": "TypeScript", ".json": "JSON",
            ".css": "CSS", ".html": "HTML", ".txt": "plain text", ".md": "Markdown",
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

        all_paths_str = "\n".join(f"  {p}" for p in full_plan_paths)

        prompt = f"""Write the file `{file_path}`.

{constraint_block}

## File contract
{description}

## Exact imports to use (copy verbatim — no alternatives)
{chr(10).join(f'  {imp}' for imp in exact_imports) if exact_imports else '  (derive from dependency files and constraint block)'}

## All project file paths (for accurate relative imports)
{all_paths_str}
{deps_section}

## Product context
Product: {spec.get('product_name', '')} — {spec.get('tagline', '')}
Auth: {spec.get('auth_model', 'none')}
Models: {', '.join(m['name'] for m in spec.get('data_models', []))}
API: {', '.join(e['method']+' '+e['path'] for e in spec.get('api_endpoints', []))}

## Frontend design system
{json.dumps(spec.get('design_system', {}), indent=2)[:3000]}

## Frontend content/data direction
frontend_data_collections: {json.dumps(spec.get('frontend_data_collections', []), indent=2)[:3000]}
content_bank: {json.dumps(spec.get('content_bank', {}), indent=2)[:3000]}

## Instructions
- Write complete {lang} code for `{file_path}`
- Target ~{max_lines} lines. For seed files, write ALL records even if longer.
- Follow the constraint block EXACTLY for imports and API paths
- For React/UI files: avoid generic blue-gray dashboards; use the design system, varied sections,
  local mock data, polished empty-free states, responsive spacing, and real-feeling interactions
- Return ONLY the raw file content. No JSON. No markdown fences. No preamble.
"""
        content = self.generate(prompt=prompt)
        return _strip_fences(content, file_path)


# ---------------------------------------------------------------------------
# ExecValidator
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
                self._emit(f"Syntax error: {rel}:{exc.lineno}")
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
        """Detect JSX in .ts files — must be .tsx."""
        errors = []
        frontend_dir = self.root / self.conv.get("frontend_dir", "frontend")
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
                            f"Must be renamed to .tsx. The file contains JSX (`<Component>` or "
                            f"`return (<div>`) which requires .tsx extension."
                        ),
                        "stdout": content[:300],
                        "file_to_rename": {"from": rel, "to": rel[:-3] + ".tsx"},
                    })
                    self._emit(f"JSX in .ts: {rel}")
            except Exception:
                pass
        return errors

    def _phase_frontend_imports(self) -> list[dict]:
        """Check relative imports resolve to real files."""
        errors = []
        frontend_dir = self.root / self.conv.get("frontend_dir", "frontend")
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
                            f"Available files: {[k for k in known if resolved.split('/')[-1] in k][:5]}"
                        ),
                        "stdout": "",
                    })

        if not errors:
            self._emit("Frontend imports OK")
        return errors

    def _phase_api_routes(self) -> list[dict]:
        """Cross-check frontend API calls vs backend route definitions."""
        errors = []
        frontend_dir = self.root / self.conv.get("frontend_dir", "frontend")
        backend_dir = self.root / self.conv.get("backend_dir", "backend")
        if not frontend_dir.exists() or not backend_dir.exists():
            return errors

        # Collect backend routes
        backend_routes: set[str] = set()
        for py_file in backend_dir.rglob("*.py"):
            if any(skip in str(py_file) for skip in (".venv", "__pycache__")):
                continue
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
                # FastAPI @router.get("/path")
                for m in re.finditer(r'@\w+\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']', content):
                    backend_routes.add(m.group(2).strip("/").split("{")[0].rstrip("/"))
                # Django path("resource/", ...)
                for m in re.finditer(r"""path\(['"]([^'"]+)['"]""", content):
                    backend_routes.add(m.group(1).strip("/").split("<")[0].rstrip("/"))
                # DRF router.register(r"resource", ...)
                for m in re.finditer(r"""router\.register\(r?['"]([^'"]+)['"]""", content):
                    backend_routes.add(m.group(1).strip("/"))
            except Exception:
                pass

        if not backend_routes:
            return errors  # can't validate without routes

        # Collect frontend calls
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
                    if url and backend_routes and not any(
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
                                f"Backend routes found: {sorted(backend_routes)[:10]}"
                            ),
                            "stdout": "",
                        })
            except Exception:
                pass

        return errors


# ---------------------------------------------------------------------------
# ScaffoldPipeline
# ---------------------------------------------------------------------------

class ScaffoldPipeline:
    """
    Orchestrates multi-stage project scaffolding with execution-driven repair.

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
        conventions = get_conventions(tech_stack)

        # Stage 1
        self._emit("stage", "Stage 1/5: Expanding description into product spec", {"stage": 1})
        spec = self._run_spec(description, tech_stack)
        self._emit("spec_ready", (
            f"Spec: {spec.get('product_name')} — "
            f"{len(spec.get('pages', []))} pages, "
            f"{len(spec.get('data_models', []))} models, "
            f"{len(spec.get('api_endpoints', []))} endpoints"
        ))

        # Stage 2
        self._emit("stage", "Stage 2/5: Planning file structure with contracts", {"stage": 2})
        file_plan = self._run_plan(spec, tech_stack)
        file_plan = self._adapt_file_plan_for_stack(file_plan, conventions, spec)
        self._emit("plan_ready", f"File plan: {len(file_plan)} files")

        if conventions.get("vite_proxy"):
            file_plan = self._ensure_vite_config(file_plan, conventions)

        # Stage 3
        self._emit("stage", "Stage 3/5: Generating files", {"stage": 3})
        files = self._run_codegen(spec, file_plan, tech_stack, conventions)
        self._emit("codegen_done", f"Generated {len(files)} files")

        # Override vite.config with guaranteed-correct version
        if conventions.get("vite_proxy") or conventions.get("import_style") == "frontend_mock":
            vite_path = self._find_vite_config_path(file_plan, conventions)
            files[vite_path] = get_vite_config(
                backend_port=conventions.get("backend_port"),
                frontend_port=conventions.get("frontend_port", 5173),
            )

        if "react" in str(conventions.get("frontend_framework", "")).lower():
            tailwind_path = self._find_file_path(file_plan, "tailwind.config.js", conventions)
            index_css_path = self._find_file_path(file_plan, "src/index.css", conventions)
            files[tailwind_path] = get_react_tailwind_config()
            files[index_css_path] = get_react_index_css()

        # Write to disk
        if project_root:
            self._write_files(files, project_root)

        # Stage 4+5
        if project_root:
            self._emit("stage", "Stage 4/5: Validating and repairing", {"stage": 4})
            files = self._repair_loop(files, spec, tech_stack, file_plan, conventions, project_root)

        return {"files": files, "spec": spec, "file_plan": file_plan}

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

    def _run_plan(self, spec: dict, tech_stack: str) -> list[dict]:
        try:
            agent = FilePlanAgent(ai_config=self.ai_config)
            plan = agent.plan(spec=spec, tech_stack=tech_stack)
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
    ) -> dict[str, str]:
        constraint_block = build_constraint_block(tech_stack)
        full_plan_paths = [e["path"] for e in file_plan]
        generated: dict[str, str] = {}

        layer_order = [
            "config", "model", "schema", "serializer", "view", "url",
            "frontend-config", "frontend-api", "component", "page", "entry", "seed", "other",
        ]
        layer_groups: dict[str, list[dict]] = {l: [] for l in layer_order}
        for entry in file_plan:
            layer = entry.get("layer", "other")
            layer_groups.setdefault(layer, []).append(entry)

        parallelisable = {"component", "page", "schema", "serializer"}

        for layer in layer_order:
            entries = layer_groups.get(layer, [])
            if not entries:
                continue
            if layer in parallelisable and len(entries) > 1:
                self._emit("codegen_layer", f"Generating {len(entries)} {layer} files (parallel)")
                self._codegen_parallel(entries, spec, generated, constraint_block, full_plan_paths)
            else:
                for entry in entries:
                    self._codegen_one(entry, spec, generated, constraint_block, full_plan_paths)

        return generated

    def _codegen_one(self, entry, spec, generated, constraint_block, full_plan_paths):
        path = entry["path"]
        dep_contents = {dep: generated[dep] for dep in entry.get("depends_on", []) if dep in generated}
        self._emit("file_start", f"Generating {path}")
        try:
            agent = FileCodeAgent(ai_config=self.ai_config)
            content = agent.generate_file(
                file_path=path, file_desc=entry, spec=spec,
                dep_contents=dep_contents, constraint_block=constraint_block,
                full_plan_paths=full_plan_paths,
            )
            generated[path] = content
            self._emit("file_done", f"Done: {path}")
        except Exception as exc:
            logger.error("FileCodeAgent failed %s: %s", path, exc)
            self._emit("file_error", f"Failed: {path} — {exc}")

    def _codegen_parallel(self, entries, spec, generated, constraint_block, full_plan_paths):
        def _task(entry):
            path = entry["path"]
            dep_contents = {dep: generated[dep] for dep in entry.get("depends_on", []) if dep in generated}
            agent = FileCodeAgent(ai_config=self.ai_config)
            return path, agent.generate_file(
                file_path=path, file_desc=entry, spec=spec,
                dep_contents=dep_contents, constraint_block=constraint_block,
                full_plan_paths=full_plan_paths,
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

    def _repair_loop(self, files, spec, tech_stack, file_plan, conventions, project_root):
        validator = ExecValidator(project_root, conventions, on_event=self.on_event)

        for round_num in range(1, MAX_REPAIR_ROUNDS + 1):
            self._emit("validate_start", f"Validation round {round_num}/{MAX_REPAIR_ROUNDS}")
            errors = validator.run_all()

            if not errors:
                self._emit("validate_ok", f"Round {round_num}: Clean — no errors")
                break

            # Handle simple renames first (no LLM needed)
            renames = [e for e in errors if e.get("file_to_rename")]
            other_errors = [e for e in errors if not e.get("file_to_rename")]

            if renames:
                for rename_info in renames:
                    files = self._apply_rename(rename_info["file_to_rename"], files, project_root)
                # Re-run to get fresh errors after renames
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
                self._emit("repair_exhausted", "Max repair rounds reached", {
                    "remaining": [e.get("stderr", "")[:150] for e in other_errors[:3]]
                })

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
            "backend/",
            "/backend/",
            "src/api/",
            "api/client",
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
                    "Rich frontend demo data module for the entire app. Export at least 15 primary "
                    "domain records, 20 secondary/activity/history records, 8 category/status/metric "
                    "records, a user/account profile, dashboard summaries, route-friendly IDs/slugs, "
                    "realistic names, statuses, dates, ratings, prices, notes/messages, and "
                    "https://images.unsplash.com or https://picsum.photos/seed imagery. Also export "
                    "helper lookup/filter functions used by pages. No fetch, axios, or network calls."
                ),
                "exact_imports": [],
                "max_lines": 420,
            })

        for entry in kept:
            if entry.get("layer") == "frontend-api" or "/src/api/" in str(entry.get("path", "")):
                entry["description"] = (
                    f"{entry.get('description', '')} IMPORTANT: API functions are optional backend "
                    f"enhancements. Import fallback records/helpers from {mock_path} and return mock "
                    "data when the backend is unavailable, empty, or returns an error. Pages must remain "
                    "fully populated on first load."
                ).strip()

        if spec is not None:
            ext = conventions.get("file_extensions", {}).get("components", ".jsx")
            page_ext = conventions.get("file_extensions", {}).get("pages", ".jsx")
            rich_pages = self._rich_frontend_pages(spec)
            shared_components = {
                f"{src_prefix}components/AppShell.jsx": "Responsive app shell with brand header, route navigation, primary CTA, mobile-friendly layout, active route styling, and polished mobile behavior. Use lucide-react icons only.",
                f"{src_prefix}components/StatCard.jsx": "Reusable metric card for dashboard summaries, trust indicators, counts, ratings, progress, or product metrics.",
                f"{src_prefix}components/ItemCard.jsx": "Reusable domain item card for primary records from mockData. Render image, title, category/status, metadata, rating/price/date when present, and view/action buttons.",
                f"{src_prefix}components/TabbedPanel.jsx": "Reusable tabs component for dashboard/workspace sections with local active tab state.",
                f"{src_prefix}components/TimelineList.jsx": "Reusable activity/history list for orders, bookings, tasks, messages, reports, events, audit entries, or updates from mockData.",
            }

            for jsx_path, description in shared_components.items():
                path = jsx_path[:-4] + ext if ext != ".jsx" else jsx_path
                if not any(entry.get("path") == path for entry in kept):
                    kept.append({
                        "path": path,
                        "layer": "component",
                        "depends_on": [mock_path] if path.endswith(f"ItemCard{ext}") else [],
                        "description": description,
                        "exact_imports": ["import React from 'react'"],
                        "max_lines": 130,
                    })

            shared_deps = [
                mock_path,
                f"{src_prefix}components/AppShell{ext}",
                f"{src_prefix}components/StatCard{ext}",
                f"{src_prefix}components/ItemCard{ext}",
                f"{src_prefix}components/TabbedPanel{ext}",
                f"{src_prefix}components/TimelineList{ext}",
            ]
            existing_page_paths = {entry.get("path") for entry in kept if str(entry.get("path", "")).startswith(f"{src_prefix}pages/")}
            for entry in kept:
                if not str(entry.get("path", "")).startswith(f"{src_prefix}pages/"):
                    continue
                entry["depends_on"] = sorted(set(entry.get("depends_on", []) + shared_deps))
                entry["description"] = (
                    f"{entry.get('description', '')} Build a populated, domain-specific screen using "
                    f"{mock_path} and shared components. Use local state for search, filters, tabs, "
                    "forms, selections, confirmations, and visible mock results. API calls are optional "
                    "enhancement only; never show an empty shell while waiting for backend data."
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
                        f"Route {page['route']}: {page['purpose']}. Build a populated, domain-specific "
                        f"screen using {mock_path} and shared components. Use local state for search, "
                        "filters, tabs, forms, selections, and confirmations. API calls are optional "
                        "enhancement only; no empty shell."
                    ),
                    "exact_imports": ["import React, { useMemo, useState } from 'react'"],
                    "max_lines": 220,
                })
                existing_page_paths.add(path)

            app_path = f"{src_prefix}App{ext}"
            route_summary = ", ".join(f"{page['route']}={page['name']}" for page in rich_pages)
            app_deps = [f"{src_prefix}pages/{page['name']}{page_ext}" for page in rich_pages]
            app_entry = next((entry for entry in kept if entry.get("path") == app_path), None)
            if app_entry:
                app_entry["depends_on"] = sorted(set(app_entry.get("depends_on", []) + app_deps))
                app_entry["description"] = (
                    f"React Router v6 app with these routes: {route_summary}. Include app shell/navigation, "
                    "a not-found route, and a frontend-first demo experience that is not blocked by backend/API wiring."
                )
            else:
                kept.append({
                    "path": app_path,
                    "layer": "entry",
                    "depends_on": app_deps,
                    "description": f"React Router v6 app with these routes: {route_summary}. Include app shell/navigation, a not-found route, and a frontend-first demo experience that is not blocked by backend/API wiring.",
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
        """Ensure frontend-only fallback plans produce full starter apps."""
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
                "route": route,
                "name": name,
                "purpose": page.get("purpose") or "Domain-specific page backed by mock data",
                "components": page.get("components", []),
                "api_calls": [],
            })
            seen_routes.add(route)
            seen_names.add(name)

        defaults = [
            ("/", "Home", "Polished product overview with hero, trust indicators, featured records, categories, and clear paths into the app."),
            ("/explore", "Explore", "Primary directory/list workspace with search, filters, category/status pills, populated cards or rows, and saved selections."),
            ("/detail/:id", "Detail", "Primary entity detail page with image/media, metadata, related records, reviews/activity, and a sticky action summary."),
            ("/workflow/:id", "Workflow", "Main product action flow with local state, multi-step selections, form inputs, confirmation, and result summary."),
            ("/dashboard", "Dashboard", "User dashboard/workspace with 3-4 populated tabs or panels for upcoming items, activity/messages, insights, and saved records."),
            ("/history", "History", "History, records, orders, reports, saved items, or settings page appropriate to the product domain."),
        ]
        for route, name, purpose in defaults:
            if len(pages) >= 6:
                break
            if route in seen_routes or name in seen_names:
                continue
            pages.append({
                "route": route,
                "name": name,
                "purpose": purpose,
                "components": ["AppShell", "StatCard", "ItemCard"],
                "api_calls": [],
            })
            seen_routes.add(route)
            seen_names.add(name)

        return pages

    def _fallback_plan(self, spec: dict, tech_stack: str) -> list[dict]:
        """Minimal fallback when FilePlanAgent fails."""
        conventions = get_conventions(tech_stack)
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
                {"path": f"{backend}/models.py", "layer": "model", "depends_on": [f"{backend}/database.py"], "description": f"SQLAlchemy models: {', '.join(m['name']+' ('+', '.join(f['name'] for f in m.get('fields',[])[:6])+')' for m in spec.get('data_models',[]))}", "exact_imports": [db_import], "max_lines": 200},
                {"path": f"{backend}/schemas.py", "layer": "schema", "depends_on": [f"{backend}/models.py"], "description": "Pydantic v2 schemas matching all models. Include Create, Response, and Update variants.", "exact_imports": ["from pydantic import BaseModel", "from typing import Optional, List", "from datetime import datetime"], "max_lines": 200},
                {"path": f"{backend}/routers/__init__.py", "layer": "view", "depends_on": [], "description": "Empty init", "exact_imports": [], "max_lines": 1},
                *[{"path": f"{backend}/routers/{p.strip('/').split('/')[1] if '/' in p else 'items'}.py", "layer": "view", "depends_on": [f"{backend}/models.py", f"{backend}/schemas.py", f"{backend}/database.py"], "description": f"FastAPI router for {p}: {purp}", "exact_imports": ["from fastapi import APIRouter, Depends, HTTPException, status", db_import, "from models import *", "from schemas import *"], "max_lines": 120}
                 for p, purp in {e["path"].strip("/").split("/")[1]: e.get("purpose", "") for e in spec.get("api_endpoints", []) if len(e["path"].strip("/").split("/")) > 1}.items()],
                {"path": f"{backend}/main.py", "layer": "entry", "depends_on": [f"{backend}/database.py", f"{backend}/models.py"], "description": "FastAPI app, CORS allow_all, create_all tables, include all routers with /api prefix", "exact_imports": ["from fastapi import FastAPI", "from fastapi.middleware.cors import CORSMiddleware", "from database import engine, Base"], "max_lines": 60},
                {"path": f"{backend}/seed.py", "layer": "seed", "depends_on": [f"{backend}/models.py", f"{backend}/database.py"], "description": f"Seed script: {spec.get('seed_data_description', '15+ realistic records per model')}. Run from backend/ directory.", "exact_imports": [db_import, "from models import *"], "max_lines": 350},
            ]
        elif is_django:
            plan += [
                {"path": f"{backend}/requirements.txt", "layer": "config", "depends_on": [], "description": "django, djangorestframework, django-cors-headers", "exact_imports": [], "max_lines": 10},
                {"path": f"{backend}/manage.py", "layer": "config", "depends_on": [], "description": "Standard Django manage.py", "exact_imports": [], "max_lines": 20},
                {"path": f"{backend}/project/settings.py", "layer": "config", "depends_on": [], "description": "Django settings, INSTALLED_APPS includes rest_framework, corsheaders, api. CORS allow all. SQLite.", "exact_imports": [], "max_lines": 60},
                {"path": f"{backend}/project/urls.py", "layer": "url", "depends_on": [], "description": "Include api/ urls", "exact_imports": [], "max_lines": 15},
                {"path": f"{backend}/api/models.py", "layer": "model", "depends_on": [], "description": f"Django models: {', '.join(m['name'] for m in spec.get('data_models', []))}", "exact_imports": ["from django.db import models"], "max_lines": 150},
                {"path": f"{backend}/api/serializers.py", "layer": "serializer", "depends_on": [f"{backend}/api/models.py"], "description": "DRF ModelSerializers for all models", "exact_imports": ["from rest_framework import serializers", "from .models import *"], "max_lines": 100},
                {"path": f"{backend}/api/views.py", "layer": "view", "depends_on": [f"{backend}/api/serializers.py"], "description": f"DRF ViewSets. Endpoints: {', '.join(e['method']+' '+e['path'] for e in spec.get('api_endpoints', [])[:8])}", "exact_imports": ["from rest_framework import viewsets", "from .models import *", "from .serializers import *"], "max_lines": 150},
                {"path": f"{backend}/api/urls.py", "layer": "url", "depends_on": [f"{backend}/api/views.py"], "description": "DRF DefaultRouter registering all viewsets", "exact_imports": ["from rest_framework.routers import DefaultRouter", "from . import views"], "max_lines": 25},
                {"path": f"{backend}/seed.py", "layer": "seed", "depends_on": [f"{backend}/api/models.py"], "description": f"Django seed: {spec.get('seed_data_description','')}", "exact_imports": [], "max_lines": 300},
            ]

        # Frontend (Vite+React)
        if conventions.get("vite_proxy") or "react" in tech_stack.lower():
            frontend_only = conventions.get("import_style") == "frontend_mock"
            frontend_pages = self._rich_frontend_pages(spec)
            prefix = "" if frontend == "." else f"{frontend}/"
            mock_dep = f"{prefix}src/mockData.js"
            api_dep = f"{prefix}src/api/client.js"
            shared_components = [
                {
                    "name": "AppShell",
                    "description": "Responsive app shell with brand header, route navigation, primary CTA, mobile-friendly layout, and active route styling. Use lucide-react icons only.",
                    "max_lines": 130,
                },
                {
                    "name": "StatCard",
                    "description": "Reusable metric card for dashboard summaries, trust indicators, counts, ratings, progress, or financial/product metrics. Props include label, value, detail, icon, and tone.",
                    "max_lines": 90,
                },
                {
                    "name": "ItemCard",
                    "description": "Reusable domain item card for the primary records in mockData. Render image, title, category/status, metadata, rating/price/date when present, and view/action buttons.",
                    "max_lines": 130,
                },
                {
                    "name": "TabbedPanel",
                    "description": "Reusable tabs component for dashboard/workspace sections. Manages local active tab state and renders populated panel content passed by pages.",
                    "max_lines": 110,
                },
                {
                    "name": "TimelineList",
                    "description": "Reusable activity/history list for appointments, orders, tasks, messages, reports, events, or audit entries from mockData.",
                    "max_lines": 110,
                },
            ]
            shared_component_paths = [f"{prefix}src/components/{c['name']}{ext}" for c in shared_components]
            page_deps = [mock_dep] + ([] if frontend_only else [api_dep]) + shared_component_paths
            package_desc = (
                f"React 18, vite {conventions.get('vite_version','^4.5.2')}, @vitejs/plugin-react, react-router-dom@6, tailwindcss, lucide-react. "
                "Do not include axios, @heroicons/react, or @mui/icons-material. Scripts: dev=vite, build=vite build, preview=vite preview"
                if frontend_only
                else f"React 18, vite {conventions.get('vite_version','^4.5.2')}, @vitejs/plugin-react, react-router-dom@6, axios, tailwindcss, lucide-react. Scripts: dev=vite, build=vite build"
            )
            plan += [
                {"path": f"{prefix}package.json", "layer": "frontend-config", "depends_on": [], "description": package_desc, "exact_imports": [], "max_lines": 35},
                {"path": f"{prefix}vite.config.js", "layer": "frontend-config", "depends_on": [], "description": "Vite config. Frontend-only stacks must set only server.port with no proxy.", "exact_imports": [], "max_lines": 15},
                {"path": f"{prefix}tailwind.config.js", "layer": "frontend-config", "depends_on": [], "description": "Tailwind content: ['./src/**/*.{js,jsx}']", "exact_imports": [], "max_lines": 10},
                {"path": f"{prefix}index.html", "layer": "entry", "depends_on": [], "description": "HTML shell with div#root and <script type=module src=/src/main.jsx>", "exact_imports": [], "max_lines": 15},
            ]
            plan.append({"path": mock_dep, "layer": "frontend-config", "depends_on": [], "description": f"Rich mock data for the whole app: {spec.get('seed_data_description', '15+ realistic primary records and 20+ related activity records')}. Export named arrays and helper functions for primaryItems, categories, activities/history, dashboardMetrics, userProfile, messages/notes, route-friendly IDs/slugs, workflow options, testimonials/notes, and media/images adapted to the product domain. Prefer Unsplash URLs for hero/detail imagery, with picsum.photos/seed fallback. No fetch, axios, or network calls.", "exact_imports": [], "max_lines": 420})
            plan += [
                {
                    "path": f"{prefix}src/components/{component['name']}{ext}",
                    "layer": "component",
                    "depends_on": [mock_dep] if component["name"] in {"ItemCard", "TimelineList"} else [],
                    "description": component["description"],
                    "exact_imports": ["import React from 'react'", "import { NavLink, Link } from 'react-router-dom'"] if component["name"] == "AppShell" else ["import React from 'react'"],
                    "max_lines": component["max_lines"],
                }
                for component in shared_components
            ]
            if not frontend_only:
                plan.append({"path": api_dep, "layer": "frontend-api", "depends_on": [mock_dep], "description": f"Axios instance with baseURL=''. Named exports for every API endpoint: {'. '.join(e['method']+' '+e['path']+' ('+e.get('handler','')+'): '+e.get('purpose','') for e in spec.get('api_endpoints',[])[:12])}. Every exported function must catch network/backend errors and return the matching mock data from {mock_dep}, so UI stays populated before backend is ready.", "exact_imports": ["import axios from 'axios'"], "max_lines": 160})

            plan += [
                *[{"path": f"{prefix}src/pages/{p['name']}{page_ext}", "layer": "page", "depends_on": page_deps, "description": f"Route {p['route']}: {p['purpose']}. Components: {', '.join(p.get('components',[]))}. Build a populated domain-specific screen using {mock_dep}, AppShell, shared cards/tabs/lists, and local state. Include 4-7 rich sections/panels, search/filter/tabs/selections/forms as relevant, and no blank API-dependent shell. Intended API integrations: {', '.join(p.get('api_calls', [])) if p.get('api_calls') else 'none for first render'}", "exact_imports": ["import React, { useMemo, useState } from 'react'"], "max_lines": 260} for p in frontend_pages],
                {"path": f"{prefix}src/App{ext}", "layer": "entry", "depends_on": [f"{prefix}src/pages/{p['name']}{page_ext}" for p in frontend_pages] + shared_component_paths, "description": f"React Router v6 with routes: {', '.join(p['route']+'='+p['name'] for p in frontend_pages)}. Wrap pages in a domain-appropriate app shell/navigation and include fallback redirect or not-found page.", "exact_imports": ["import { BrowserRouter, Routes, Route } from 'react-router-dom'"], "max_lines": 80},
                {"path": f"{prefix}src/main{ext}", "layer": "entry", "depends_on": [f"{prefix}src/App{ext}"], "description": "ReactDOM.createRoot('#root').render(<App/>)", "exact_imports": ["import React from 'react'", "import ReactDOM from 'react-dom/client'"], "max_lines": 12},
                {"path": f"{prefix}src/index.css", "layer": "frontend-config", "depends_on": [], "description": "@tailwind base; @tailwind components; @tailwind utilities; plus polished responsive app styling if needed.", "exact_imports": [], "max_lines": 80},
                {"path": f"{prefix}postcss.config.js", "layer": "frontend-config", "depends_on": [], "description": "PostCSS with tailwindcss and autoprefixer plugins", "exact_imports": [], "max_lines": 8},
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
