import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _preview_url_for_command(command: str | None) -> str | None:
    if not command:
        return None
    match = re.search(r'(\d{4,5})', command)
    if not match:
        return None
    return f"http://127.0.0.1:{match.group(1)}"


def _vite_config_preview_url(project_root: Path) -> str | None:
    for rel_path in ("vite.config.js", "vite.config.ts", "vite.config.mjs", "vite.config.cjs"):
        config_path = project_root / rel_path
        if not config_path.exists():
            continue
        try:
            content = config_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        port_match = re.search(r'port\s*:\s*(\d{4,5})', content)
        host_match = re.search(r"host\s*:\s*['\"]([^'\"]+)['\"]", content)
        port = port_match.group(1) if port_match else "5173"
        host = host_match.group(1) if host_match else "127.0.0.1"
        if host in {"0.0.0.0", "::"}:
            host = "127.0.0.1"
        return f"http://{host}:{port}"
    return None


def _node_preview_url(project_root: Path, scripts: dict, run_command: str | None) -> str | None:
    candidate_scripts = [
        scripts.get("dev"),
        scripts.get("start"),
        scripts.get("preview"),
        run_command,
    ]
    for candidate in candidate_scripts:
        preview_url = _preview_url_for_command(candidate)
        if preview_url:
            return preview_url

    lower_scripts = " ".join(str(candidate or "").lower() for candidate in candidate_scripts)
    if "vite" in lower_scripts:
        return _vite_config_preview_url(project_root) or "http://127.0.0.1:5173"
    if "react-scripts start" in lower_scripts:
        return "http://127.0.0.1:3000"
    if "next dev" in lower_scripts or "next start" in lower_scripts:
        return "http://127.0.0.1:3000"
    if "nuxt" in lower_scripts:
        return "http://127.0.0.1:3000"
    return None


def _python_executable_command() -> str:
    sandbox_mode = str(os.environ.get("DEVHUB_SANDBOX_MODE") or "").strip().lower()
    if sandbox_mode == "docker":
        return "python"
    return f'"{sys.executable}"'


def _read_runtime_text_if_exists(path: Path) -> str:
    try:
        if path.exists() and path.is_file():
            return path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        pass
    return ""


def _stable_runtime_port(project_root: Path, *, start: int, size: int = 700) -> int:
    digest = hashlib.md5(str(project_root.resolve()).encode('utf-8')).hexdigest()
    return start + (int(digest[:8], 16) % size)


def _python_install_required(project_root: Path) -> bool:
    requirements_file = project_root / "requirements.txt"
    if not requirements_file.exists():
        return False

    sandbox_mode = str(os.environ.get("DEVHUB_SANDBOX_MODE") or "").strip().lower()
    if sandbox_mode == "docker":
        return not (project_root / ".devhub" / "python-packages").exists()

    return False


def _node_setup_command(project_root: Path) -> str | None:
    commands: list[str] = []
    if (project_root / "package.json").exists():
        commands.append("npm install")
    if (project_root / "requirements.txt").exists():
        python_cmd = _python_executable_command()
        commands.append(f"{python_cmd} -m pip install -r requirements.txt")
    return " && ".join(commands) if commands else None


def _node_install_required(project_root: Path) -> bool:
    frontend_package = project_root / "frontend" / "package.json"
    frontend_node_modules = project_root / "frontend" / "node_modules"
    needs_frontend_packages = frontend_package.exists() and not frontend_node_modules.exists()
    needs_root_packages = (project_root / "package.json").exists() and not (project_root / "node_modules").exists()
    needs_python_packages = (project_root / "requirements.txt").exists() and _python_install_required(project_root)
    return needs_root_packages or needs_frontend_packages or needs_python_packages


def _detect_python_app_runtime(project_root: Path, entrypoint: str, python_cmd: str) -> tuple[str, str | None]:
    entrypoint_path = project_root / entrypoint
    entrypoint_text = _read_runtime_text_if_exists(entrypoint_path).lower()
    requirements_blob = _read_runtime_text_if_exists(project_root / "requirements.txt").lower()
    port = _stable_runtime_port(project_root, start=8100)
    module_name = Path(entrypoint).stem

    if "fastapi" in requirements_blob or "uvicorn" in requirements_blob or "fastapi(" in entrypoint_text:
        return (
            f"{python_cmd} -m uvicorn {module_name}:app --host 127.0.0.1 --port {port}",
            f"http://127.0.0.1:{port}",
        )

    if "flask" in requirements_blob or "flask(" in entrypoint_text:
        return (
            f"{python_cmd} -m flask --app {module_name}:app run --host 127.0.0.1 --port {port}",
            f"http://127.0.0.1:{port}",
        )

    return (
        f"{python_cmd} {entrypoint}",
        _preview_url_for_command(f"{python_cmd} {entrypoint}"),
    )


def _probe_preview_url(preview_url: str, timeout: float = 1.2) -> tuple[bool, str | None]:
    request = Request(preview_url, headers={"User-Agent": "DevHub Preview Probe"})
    try:
        with urlopen(request, timeout=timeout) as response:
            response.read(1)
        return True, None
    except HTTPError:
        return True, None
    except URLError as exc:
        reason = getattr(exc, "reason", None)
        return False, str(reason or exc)
    except Exception as exc:
        return False, str(exc)


def _wait_for_preview_ready(preview_url: str, sandbox, process_id: str, timeout_seconds: float = 8.0) -> tuple[bool, str | None]:
    deadline = time.time() + timeout_seconds
    last_error = None

    while time.time() < deadline:
        status = sandbox.get_status(process_id)
        if not status.get("running"):
            startup_output = "".join(sandbox.get_output(process_id)).strip()
            if startup_output:
                return False, startup_output[-2000:]
            return False, last_error or "Runtime process exited before the preview became reachable."

        ready, error = _probe_preview_url(preview_url)
        if ready:
            return True, None

        last_error = error
        time.sleep(0.35)

    return False, last_error or "Preview did not become reachable in time."


def _detect_node_runtime_at_path(project_root: Path, runtime_root: Path) -> dict | None:
    package_json_path = runtime_root / "package.json"
    if not package_json_path.exists():
        return None
    try:
        package_json = json.loads(package_json_path.read_text(encoding='utf-8'))
    except Exception:
        package_json = {}

    scripts = package_json.get("scripts", {})
    run_command = None
    if scripts.get("dev"):
        run_command = "npm run dev"
    elif scripts.get("start"):
        run_command = "npm start"
    elif scripts.get("preview"):
        run_command = "npm run preview"

    rel_runtime_root = runtime_root.relative_to(project_root) if runtime_root != project_root else Path(".")
    entrypoint = "package.json" if rel_runtime_root == Path(".") else f"{rel_runtime_root.as_posix()}/package.json"
    return {
        "label": package_json.get("name") or runtime_root.name or project_root.name,
        "runtime_type": "node",
        "entrypoint": entrypoint,
        "run_command": run_command,
        "setup_command": _node_setup_command(runtime_root),
        "install_required": _node_install_required(runtime_root),
        "preview_url": _node_preview_url(runtime_root, scripts, run_command),
        "runtime_root": runtime_root.as_posix(),
    }


def _detect_django_runtime_at_path(project_root: Path, runtime_root: Path) -> dict | None:
    manage_py = runtime_root / "manage.py"
    if not manage_py.exists():
        return None
    requirements_file = runtime_root / "requirements.txt"
    python_cmd = _python_executable_command()
    port = _stable_runtime_port(runtime_root, start=8100)
    rel_runtime_root = runtime_root.relative_to(project_root) if runtime_root != project_root else Path(".")
    entrypoint = "manage.py" if rel_runtime_root == Path(".") else f"{rel_runtime_root.as_posix()}/manage.py"
    run_prefix = "" if rel_runtime_root == Path(".") else f"cd {rel_runtime_root.as_posix()} && "
    setup_prefix = "" if rel_runtime_root == Path(".") else f"cd {rel_runtime_root.as_posix()} && "
    return {
        "label": runtime_root.name or project_root.name,
        "runtime_type": "django",
        "entrypoint": entrypoint,
        "run_command": f"{run_prefix}{python_cmd} manage.py runserver 127.0.0.1:{port}",
        "setup_command": f"{setup_prefix}{python_cmd} -m pip install -r requirements.txt" if requirements_file.exists() else None,
        "install_required": _python_install_required(runtime_root),
        "preview_url": f"http://127.0.0.1:{port}",
        "runtime_root": runtime_root.as_posix(),
    }


def _combine_detected_runtime(project_root: Path, frontend_runtime: dict | None, backend_runtime: dict | None) -> dict:
    if frontend_runtime and backend_runtime:
        combined = dict(backend_runtime)
        combined.update({
            "label": f"{project_root.name} ({backend_runtime.get('runtime_type')} + {frontend_runtime.get('runtime_type')})",
            "runtime_type": backend_runtime.get("runtime_type") or frontend_runtime.get("runtime_type") or "unknown",
            "entrypoint": backend_runtime.get("entrypoint") or frontend_runtime.get("entrypoint"),
            "run_command": backend_runtime.get("run_command") or frontend_runtime.get("run_command"),
            "setup_command": backend_runtime.get("setup_command") or frontend_runtime.get("setup_command"),
            "install_required": bool(backend_runtime.get("install_required")) or bool(frontend_runtime.get("install_required")),
            "preview_url": frontend_runtime.get("preview_url") or backend_runtime.get("preview_url"),
            "secondary_runtime": frontend_runtime,
        })
        return combined
    return frontend_runtime or backend_runtime or {}


def detect_runtime(project_root: Path) -> dict:
    direct_node_runtime = _detect_node_runtime_at_path(project_root, project_root)
    if direct_node_runtime:
        return direct_node_runtime

    direct_django_runtime = _detect_django_runtime_at_path(project_root, project_root)
    if direct_django_runtime:
        return direct_django_runtime

    if (project_root / "main.py").exists() or (project_root / "app.py").exists():
        entrypoint = "main.py" if (project_root / "main.py").exists() else "app.py"
        requirements_file = project_root / "requirements.txt"
        python_cmd = _python_executable_command()
        run_command, preview_url = _detect_python_app_runtime(project_root, entrypoint, python_cmd)
        return {
            "label": project_root.name,
            "runtime_type": "python",
            "entrypoint": entrypoint,
            "run_command": run_command,
            "setup_command": f"{python_cmd} -m pip install -r requirements.txt" if requirements_file.exists() else None,
            "install_required": _python_install_required(project_root),
            "preview_url": preview_url,
        }

    if (project_root / "index.html").exists():
        python_cmd = _python_executable_command()
        port = _stable_runtime_port(project_root, start=4173)
        return {
            "label": project_root.name,
            "runtime_type": "static",
            "entrypoint": "index.html",
            "run_command": f"{python_cmd} -m http.server {port} --bind 127.0.0.1",
            "setup_command": None,
            "install_required": False,
            "preview_url": f"http://127.0.0.1:{port}",
        }

    frontend_runtime = None
    for subdir in ("frontend", "client", "web", "app", "ui"):
        candidate_root = project_root / subdir
        frontend_runtime = _detect_node_runtime_at_path(project_root, candidate_root)
        if frontend_runtime:
            break

    backend_runtime = None
    for subdir in ("backend", "server", "api", "src"):
        candidate_root = project_root / subdir
        backend_runtime = _detect_django_runtime_at_path(project_root, candidate_root)
        if backend_runtime:
            break

    combined_runtime = _combine_detected_runtime(project_root, frontend_runtime, backend_runtime)
    if combined_runtime:
        return combined_runtime

    return {
        "label": project_root.name,
        "runtime_type": "unknown",
        "entrypoint": None,
        "run_command": None,
        "setup_command": None,
        "install_required": False,
        "preview_url": None,
    }


def runtime_process_id(workspace_id: str) -> str:
    return f"{workspace_id}_runtime"


def setup_process_id(workspace_id: str) -> str:
    return f"{workspace_id}_setup"


def _runtime_response_payload(runtime: dict, process_id: str, sandbox, *, wait_for_preview: bool = False) -> dict:
    status = sandbox.get_status(process_id)
    payload = {
        **runtime,
        "process_id": process_id,
        "status": status,
        "ready": False,
        "preview_error": None,
        "sandbox": sandbox.details(),
    }
    preview_url = runtime.get("preview_url")

    if not preview_url or not status.get("running"):
        return payload

    if wait_for_preview:
        ready, preview_error = _wait_for_preview_ready(preview_url, sandbox, process_id)
        status = sandbox.get_status(process_id)
        payload["status"] = status
    else:
        ready, preview_error = _probe_preview_url(preview_url)

    payload["ready"] = ready
    payload["preview_error"] = preview_error
    return payload
