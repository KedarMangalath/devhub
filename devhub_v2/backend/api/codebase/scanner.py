import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

from agents.core.workspace import SKIP_DIRS

from api.project_utils import (
    _global_ai_config,
    _normalize_path,
    _normalize_tech_stack,
    _suggested_stack_from_text,
)
from api.workspace.runtime import detect_runtime

logger = logging.getLogger(__name__)


def scan_local_folder(folder_path: str) -> str:
    base = Path(folder_path)
    if not base.exists() or not base.is_dir():
        return f"Path not found: {folder_path}"

    config_files = [
        "README.md", "readme.md", "package.json", "requirements.txt", "setup.py",
        "pyproject.toml", "Dockerfile", "docker-compose.yml", ".env.example",
        "pom.xml", "go.mod", "Cargo.toml", "angular.json", "next.config.js",
        "vite.config.js", "vite.config.ts", "webpack.config.js",
    ]

    result = ["=== FILE STRUCTURE ==="]
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in sorted(dirs) if d not in SKIP_DIRS]
        depth = len(Path(root).relative_to(base).parts)
        if depth > 3:
            dirs[:] = []
            continue
        indent = "  " * depth
        folder_name = Path(root).name if depth > 0 else base.name
        result.append(f"{indent}{folder_name}/")
        for filename in sorted(files)[:30]:
            result.append(f"{indent}  {filename}")

    result.append("\n=== KEY FILES ===")
    for filename in config_files:
        file_path = base / filename
        if not file_path.exists():
            continue
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")[:2000]
        except Exception:
            continue
        result.append(f"\n--- {filename} ---\n{content}")

    result.append("\n=== SAMPLE SOURCE FILES ===")
    source_exts = {".py", ".js", ".ts", ".tsx", ".go", ".java", ".rb", ".php", ".rs"}
    found = 0
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for filename in files:
            if found >= 3:
                break
            if Path(filename).suffix not in source_exts:
                continue
            file_path = Path(root) / filename
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")[:1500]
            except Exception:
                continue
            rel_path = file_path.relative_to(base)
            result.append(f"\n--- {rel_path} ---\n{content}")
            found += 1
        if found >= 3:
            break

    return "\n".join(result)[:8000]


def _read_text_if_exists(file_path: Path, limit: int = 5000) -> str:
    try:
        if file_path.exists() and file_path.is_file():
            return file_path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except Exception:
        logger.exception("Failed to read file during import inspection: %s", file_path)
    return ""


def _repo_name_from_github_url(github_url: str) -> str:
    cleaned = str(github_url or "").rstrip("/").split("/")[-1]
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    cleaned = re.sub(r"[-_]+", " ", cleaned).strip()
    return cleaned.title() if cleaned else "Imported Project"


def _detected_stack_for_path(project_root: Path) -> list[str]:
    detected: list[str] = []

    package_json = _read_text_if_exists(project_root / "package.json")
    frontend_package_json = _read_text_if_exists(project_root / "frontend" / "package.json")
    package_blob = "\n".join([package_json, frontend_package_json]).lower()

    requirements_blob = "\n".join([
        _read_text_if_exists(project_root / "requirements.txt"),
        _read_text_if_exists(project_root / "pyproject.toml"),
        _read_text_if_exists(project_root / "backend" / "requirements.txt"),
        _read_text_if_exists(project_root / "backend" / "pyproject.toml"),
    ]).lower()

    config_names = {path.name.lower() for path in project_root.glob("*")}
    config_names.update(path.name.lower() for path in (project_root / "frontend").glob("*") if (project_root / "frontend").exists())
    runtime = detect_runtime(project_root)
    runtime_type = str(runtime.get("runtime_type") or "").lower()

    if "next.config.js" in config_names or "next.config.mjs" in config_names or "next" in package_blob:
        detected.extend(["Next.js", "React", "Node.js"])
    elif "react" in package_blob:
        detected.extend(["React", "Node.js"])
    elif "vue" in package_blob:
        detected.extend(["Vue", "Node.js"])
    elif package_blob:
        detected.append("Node.js")

    if "express" in package_blob:
        detected.append("Express")
    if "tailwind" in package_blob or "tailwind.config.js" in config_names or "tailwind.config.ts" in config_names:
        detected.append("Tailwind")
    if "typescript" in package_blob or (project_root / "tsconfig.json").exists() or (project_root / "frontend" / "tsconfig.json").exists():
        detected.append("TypeScript")

    if (project_root / "manage.py").exists() or "django" in requirements_blob:
        detected.append("Django")
    elif "fastapi" in requirements_blob:
        detected.append("FastAPI")
    elif requirements_blob or runtime_type == "python":
        detected.append("Python")

    postgres_markers = ["postgres", "psycopg", "postgresql"]
    combined_blob = "\n".join([
        package_blob,
        requirements_blob,
        _read_text_if_exists(project_root / ".env.example"),
        _read_text_if_exists(project_root / ".env"),
        _read_text_if_exists(project_root / "docker-compose.yml"),
    ]).lower()
    if any(marker in combined_blob for marker in postgres_markers):
        detected.append("PostgreSQL")

    if runtime_type == "node" and "Node.js" not in detected:
        detected.append("Node.js")
    if runtime_type == "static" and not detected:
        detected.append("HTML/CSS/JS")

    return _normalize_tech_stack(detected)


def _slug_to_title(text: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9]+', ' ', text or '').strip()
    return cleaned.title() or 'New Project'


def _fallback_project_suggestion(idea: str, source_type: str, tech_stack: list[str]) -> dict:
    source_label = {
        'starter': 'AI-generated starter',
        'github': 'GitHub import',
        'folder': 'existing local folder',
    }.get(source_type, 'project')
    suggested_stack = _suggested_stack_from_text(idea, tech_stack)
    name = _slug_to_title(idea[:60] or 'new project')
    description = (
        f"{name} is a {source_label} built around {', '.join(suggested_stack)}. "
        "It starts from a working foundation, supports iterative feature delivery, "
        "and stays easy to evolve through the workspace, feature pipeline, and AI chat."
    )
    return {
        'name': name,
        'description': description,
        'tech_stack': suggested_stack,
    }


def _suggest_project_details(idea: str, source_type: str, tech_stack: list[str]) -> dict:
    fallback = _fallback_project_suggestion(idea, source_type, tech_stack)

    try:
        from agents.core.base import BaseAgent

        agent = BaseAgent(
            role="Project Setup Assistant",
            system_instruction=(
                "You generate concise but polished DevHub project metadata. "
                "Return valid JSON with keys name, description, and tech_stack. "
                "Descriptions should be clear, practical, and editable."
            ),
            ai_config=_global_ai_config(),
        )
        response = agent.generate(
            json.dumps({"idea": idea, "source_type": source_type, "tech_stack": tech_stack}),
            response_schema=True,
        )
        parsed = agent.parse_json(response)
        if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict):
            parsed = parsed[0]
        if not isinstance(parsed, dict):
            parsed = {}
        return {
            'name': str(parsed.get('name') or fallback['name']).strip() or fallback['name'],
            'description': str(parsed.get('description') or fallback['description']).strip() or fallback['description'],
            'tech_stack': _normalize_tech_stack(parsed.get('tech_stack') or fallback['tech_stack']),
        }
    except Exception:
        logger.exception("Project detail suggestion failed; using fallback")
        return fallback


def _build_import_inspection(project_root: Path, source_type: str, idea: str = "", source_label: str = "") -> dict:
    project_root = _normalize_path(str(project_root))
    scan_summary = scan_local_folder(str(project_root))
    detected_stack = _detected_stack_for_path(project_root)
    suggestion_seed_parts = [
        idea.strip(),
        source_label.strip(),
        f"Project root: {project_root.name}",
        scan_summary[:2400],
    ]
    suggestion_seed = "\n\n".join(part for part in suggestion_seed_parts if part)
    suggestion = _suggest_project_details(suggestion_seed, source_type, detected_stack)
    runtime = detect_runtime(project_root)

    suggested_name = suggestion.get("name") or project_root.name.replace("-", " ").replace("_", " ").title()
    if source_type == "github" and source_label:
        repo_name = _repo_name_from_github_url(source_label)
        if repo_name:
            suggested_name = repo_name

    lines = [line for line in scan_summary.splitlines() if line.strip()]
    structure_preview = "\n".join(lines[:24])

    return {
        "name": suggested_name,
        "description": suggestion.get("description") or f"Imported from {source_type} source.",
        "tech_stack": suggestion.get("tech_stack") or detected_stack,
        "detected_stack": detected_stack,
        "resolved_path": str(project_root),
        "root_name": project_root.name,
        "runtime": runtime,
        "structure_preview": structure_preview,
        "source_summary": scan_summary[:3200],
    }


def _pick_local_folder() -> str | None:
    if sys.platform.startswith("win"):
        powershell_script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
            "$dialog.Description = 'Select a project folder for DevHub'; "
            "$dialog.ShowNewFolderButton = $false; "
            "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { "
            "Write-Output $dialog.SelectedPath }"
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-STA", "-Command", powershell_script],
                capture_output=True,
                text=True,
                timeout=120,
            )
            selected = result.stdout.strip()
            if result.returncode == 0 and selected:
                return selected
        except Exception:
            logger.exception("PowerShell folder picker failed")

    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(title="Select a project folder for DevHub")
        root.destroy()
        return selected or None
    except Exception:
        logger.exception("Tk folder picker failed")
        return None
