import hashlib
import json
import os
import re
import socket
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen


# ---------------------------------------------------------------------------
# Port allocation — always bind-test so we never collide with a live process
# ---------------------------------------------------------------------------

def _port_is_free(port: int) -> bool:
    for host in ("127.0.0.1", "localhost", "::1"):
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return False
        except OSError:
            pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", port))
    except OSError:
        return False
    if socket.has_ipv6:
        try:
            with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("::1", port))
        except OSError:
            return False
    return True


def find_free_port(preferred: int | None = None, range_start: int = 5000, range_end: int = 9900) -> int:
    """Return a port that is actually available right now.

    Tries `preferred` first (keeps ports stable across restarts).
    Falls back to scanning `range_start..range_end` if preferred is taken.
    """
    if preferred and range_start <= preferred <= range_end and _port_is_free(preferred):
        return preferred
    for port in range(range_start, range_end + 1):
        if port != preferred and _port_is_free(port):
            return port
    raise RuntimeError(f"No free port found in range {range_start}-{range_end}")


def _stable_preferred_port(project_root: Path, *, start: int, size: int = 700) -> int:
    """Deterministic port derived from project path — used as *preferred* input to find_free_port."""
    digest = hashlib.md5(str(project_root.resolve()).encode("utf-8")).hexdigest()
    return start + (int(digest[:8], 16) % size)


def _stable_runtime_port(project_root: Path, *, start: int, size: int = 700) -> int:
    return _stable_preferred_port(project_root, start=start, size=size)


def _alloc_port(project_root: Path, *, start: int, end: int) -> int:
    """Allocate the next actually-free port, biased toward a stable preferred value."""
    preferred = _stable_preferred_port(project_root, start=start, size=max(1, end - start + 1))
    return find_free_port(preferred=preferred, range_start=start, range_end=end)


def _substitute_port(cmd: str, port: int) -> str:
    """Replace $PORT / ${PORT} placeholders with the real port number."""
    if not cmd:
        return cmd
    return cmd.replace("${PORT}", str(port)).replace("$PORT", str(port))


def _inject_port_into_node_command(cmd: str, port: int) -> str:
    """Append the correct port flag to a Node dev-server command."""
    if not cmd:
        return cmd
    lower = cmd.lower()
    if re.search(r"\b(ng)\b.*serve", lower):
        return f"{cmd} --host 127.0.0.1 --port {port}"
    if re.search(r"\bnext\b.*(dev|start)", lower):
        return f"{cmd} -H 127.0.0.1 -p {port}"
    if re.search(r"\b(npm|pnpm|yarn|bun)\b.*(dev|preview)", lower):
        return f"{cmd} -- --port {port}"
    # generic npm start / react-scripts — rely on PORT env var, no extra flag
    return cmd


def _is_vite_project(project_root: Path, scripts: dict) -> bool:
    script_blob = " ".join(str(value or "").lower() for value in scripts.values())
    return _has_vite_config(project_root) or "vite" in script_blob


def _inject_vite_host_port_command(cmd: str, port: int) -> str:
    """Force Vite to bind the same loopback host DevHub previews and probes."""
    if not cmd:
        return cmd
    lower = cmd.lower()
    vite_args = f"--host 127.0.0.1 --port {port}"
    if re.search(r"\b(npm|pnpm|yarn|bun)\b.*\b(dev|preview)\b", lower):
        return f"{cmd} -- {vite_args}"
    if re.search(r"\bvite\b", lower):
        return f"{cmd} {vite_args}"
    return _inject_port_into_node_command(cmd, port)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _python_executable_command() -> str:
    sandbox_mode = str(os.environ.get("DEVHUB_SANDBOX_MODE") or "").strip().lower()
    if sandbox_mode == "docker":
        return "python"
    return f'"{sys.executable}"'


def _is_windows_local_sandbox() -> bool:
    sandbox_mode = str(os.environ.get("DEVHUB_SANDBOX_MODE") or "").strip().lower()
    return sandbox_mode != "docker" and os.name == "nt"


def _prefix_command_for_runtime_dir(rel_runtime_root: Path, command: str) -> str:
    normalized_command = str(command or "").strip()
    if not normalized_command:
        return ""
    if rel_runtime_root == Path("."):
        return normalized_command
    rel_dir = rel_runtime_root.as_posix()
    if _is_windows_local_sandbox():
        return f'pushd "{rel_dir}" && {normalized_command} && popd'
    return f"cd {rel_dir} && {normalized_command}"


def _read_runtime_text_if_exists(path: Path) -> str:
    try:
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        pass
    return ""


RUNTIME_SKIP_DIRS = {
    ".git", ".hg", ".svn", ".devhub", ".claude", ".code-review-graph",
    "__pycache__", ".venv", "venv", "env", "node_modules",
    "dist", "build", ".next", ".nuxt", "coverage", "target",
}


def _runtime_root_candidates(project_root: Path, marker: str, *, max_depth: int = 2) -> list[Path]:
    candidates: list[Path] = []

    def visit(root: Path, depth: int) -> None:
        if (root / marker).is_file():
            candidates.append(root)
        if depth >= max_depth:
            return
        try:
            children = list(root.iterdir())
        except Exception:
            return
        for child in children:
            if not child.is_dir() or child.name in RUNTIME_SKIP_DIRS or child.name.startswith("."):
                continue
            visit(child, depth + 1)

    visit(project_root, 0)
    return candidates


def _runtime_root_score(
    project_root: Path, runtime_root: Path, preferred_names: tuple[str, ...]
) -> tuple[int, int, str]:
    try:
        rel = runtime_root.relative_to(project_root)
        parts = rel.parts
    except ValueError:
        parts = runtime_root.parts
    preferred_rank = 0 if any(part.lower() in preferred_names for part in parts[-2:]) else 1
    return (preferred_rank, len(parts), rel.as_posix() if "rel" in dir() else runtime_root.as_posix())


def _python_install_required(project_root: Path) -> bool:
    if not (project_root / "requirements.txt").exists():
        return False
    sandbox_mode = str(os.environ.get("DEVHUB_SANDBOX_MODE") or "").strip().lower()
    if sandbox_mode == "docker":
        return not (project_root / ".devhub" / "python-packages").exists()
    return False


def _node_setup_command(project_root: Path) -> str | None:
    commands: list[str] = []
    if (project_root / "package.json").exists():
        package_manager = _node_package_manager(project_root)
        commands.append(f"{package_manager} install")
    if (project_root / "requirements.txt").exists():
        python_cmd = _python_executable_command()
        commands.append(f"{python_cmd} -m pip install -r requirements.txt")
    return " && ".join(commands) if commands else None


def _node_package_manager(project_root: Path) -> str:
    package_json_path = project_root / "package.json"
    try:
        package_json = (
            json.loads(package_json_path.read_text(encoding="utf-8"))
            if package_json_path.exists()
            else {}
        )
    except Exception:
        package_json = {}
    declared = str(package_json.get("packageManager") or "").strip().lower()
    if declared:
        return declared.split("@", 1)[0]
    if (project_root / "pnpm-lock.yaml").exists() or (project_root / "pnpm-workspace.yaml").exists():
        return "pnpm"
    if (project_root / "yarn.lock").exists():
        return "yarn"
    if (project_root / "bun.lock").exists() or (project_root / "bun.lockb").exists():
        return "bun"
    return "npm"


def _node_script_command(package_manager: str, script_name: str) -> str:
    if package_manager == "npm":
        return f"npm run {script_name}"
    if package_manager == "bun":
        return f"bun run {script_name}"
    if package_manager in {"pnpm", "yarn"}:
        return f"{package_manager} {script_name}"
    return f"{package_manager} run {script_name}"


def _node_install_required(project_root: Path) -> bool:
    needs_root_packages = (project_root / "package.json").exists() and not (
        project_root / "node_modules"
    ).exists()
    needs_python_packages = (project_root / "requirements.txt").exists() and _python_install_required(
        project_root
    )
    return needs_root_packages or needs_python_packages


def _vite_config_preview_url(project_root: Path) -> str | None:
    for rel_path in ("vite.config.js", "vite.config.ts", "vite.config.mjs", "vite.config.cjs"):
        config_path = project_root / rel_path
        if not config_path.exists():
            continue
        try:
            content = config_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        port_match = re.search(r"port\s*:\s*(\d{4,5})", content)
        host_match = re.search(r"host\s*:\s*['\"]([^'\"]+)['\"]", content)
        port = port_match.group(1) if port_match else None
        host = host_match.group(1) if host_match else "127.0.0.1"
        if host in {"0.0.0.0", "::"}:
            host = "127.0.0.1"
        if port:
            return f"http://{host}:{port}"
    return None


def _has_vite_config(project_root: Path) -> bool:
    return any((project_root / rel_path).exists() for rel_path in (
        "vite.config.js", "vite.config.ts", "vite.config.mjs", "vite.config.cjs"
    ))


def _node_script_port(script: str) -> int | None:
    if not script:
        return None
    patterns = (
        r"(?:--port|-p)\s+(\d{4,5})\b",
        r"\bPORT\s*=\s*(\d{4,5})\b",
        r":(\d{4,5})\b",
        r"\b(\d{4,5})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, script)
        if match:
            return int(match.group(1))
    return None


def _node_port_range(project_root: Path, scripts: dict) -> tuple[int, int]:
    candidates = [scripts.get("dev"), scripts.get("start"), scripts.get("preview")]
    lower = " ".join(str(c or "").lower() for c in candidates)
    frontend_markers = ("vite", "react-scripts", "next", "nuxt", "svelte", "angular", "ng ")
    if _has_vite_config(project_root) or any(fw in lower for fw in frontend_markers):
        return 5200, 5899
    return 3000, 3699


def _get_node_port(project_root: Path, scripts: dict) -> tuple[int, bool]:
    """Return (port, needs_injection).

    `needs_injection=True` means the run command must have the port flag appended.
    """
    candidates = [scripts.get("dev"), scripts.get("start"), scripts.get("preview")]
    range_start, range_end = _node_port_range(project_root, scripts)

    # Port already explicit inside an npm script
    for c in candidates:
        explicit_port = _node_script_port(str(c or ""))
        if explicit_port:
            if _port_is_free(explicit_port):
                return explicit_port, False
            return _alloc_port(project_root, start=range_start, end=range_end), True

    # Explicit port in vite config
    vite_url = _vite_config_preview_url(project_root)
    if vite_url:
        m = re.search(r":(\d{4,5})$", vite_url)
        if m:
            explicit_port = int(m.group(1))
            if _port_is_free(explicit_port):
                return explicit_port, False
            return _alloc_port(project_root, start=range_start, end=range_end), True

    # Determine port range by framework type then allocate a truly-free port
    return _alloc_port(project_root, start=range_start, end=range_end), True


# ---------------------------------------------------------------------------
# Per-framework detectors
# ---------------------------------------------------------------------------

def _detect_node_runtime_at_path(project_root: Path, runtime_root: Path) -> dict | None:
    package_json_path = runtime_root / "package.json"
    if not package_json_path.exists():
        return None
    try:
        package_json = json.loads(package_json_path.read_text(encoding="utf-8"))
    except Exception:
        package_json = {}

    scripts = package_json.get("scripts", {})
    package_manager = _node_package_manager(runtime_root)
    run_command: str | None = None
    if scripts.get("dev"):
        run_command = _node_script_command(package_manager, "dev")
    elif scripts.get("start"):
        run_command = "npm start" if package_manager == "npm" else _node_script_command(package_manager, "start")
    elif scripts.get("preview"):
        run_command = _node_script_command(package_manager, "preview")

    port, needs_injection = _get_node_port(runtime_root, scripts)
    if run_command and _is_vite_project(runtime_root, scripts):
        run_command = _inject_vite_host_port_command(run_command, port)
    elif needs_injection and run_command:
        run_command = _inject_port_into_node_command(run_command, port)

    rel_runtime_root = runtime_root.relative_to(project_root) if runtime_root != project_root else Path(".")
    entrypoint = "package.json" if rel_runtime_root == Path(".") else f"{rel_runtime_root.as_posix()}/package.json"
    return {
        "label": package_json.get("name") or runtime_root.name or project_root.name,
        "runtime_type": "node",
        "package_manager": package_manager,
        "entrypoint": entrypoint,
        "run_command": _prefix_command_for_runtime_dir(rel_runtime_root, run_command) if run_command else None,
        "setup_command": _prefix_command_for_runtime_dir(rel_runtime_root, _node_setup_command(runtime_root) or "") or None,
        "install_required": _node_install_required(runtime_root),
        "preview_url": f"http://127.0.0.1:{port}",
        "runtime_root": runtime_root.as_posix(),
    }


def _detect_django_runtime_at_path(project_root: Path, runtime_root: Path) -> dict | None:
    if not (runtime_root / "manage.py").exists():
        return None
    python_cmd = _python_executable_command()
    port = _alloc_port(runtime_root, start=8100, end=8799)
    rel_runtime_root = runtime_root.relative_to(project_root) if runtime_root != project_root else Path(".")
    entrypoint = "manage.py" if rel_runtime_root == Path(".") else f"{rel_runtime_root.as_posix()}/manage.py"
    return {
        "label": runtime_root.name or project_root.name,
        "runtime_type": "django",
        "entrypoint": entrypoint,
        "run_command": _prefix_command_for_runtime_dir(
            rel_runtime_root, f"{python_cmd} manage.py runserver 127.0.0.1:{port}"
        ),
        "setup_command": _prefix_command_for_runtime_dir(
            rel_runtime_root, f"{python_cmd} -m pip install -r requirements.txt"
        ) if (runtime_root / "requirements.txt").exists() else None,
        "install_required": _python_install_required(runtime_root),
        "preview_url": f"http://127.0.0.1:{port}",
        "runtime_root": runtime_root.as_posix(),
    }


def _detect_python_runtime_at_path(project_root: Path, runtime_root: Path) -> dict | None:
    entrypoint = (
        "main.py" if (runtime_root / "main.py").exists()
        else "app.py" if (runtime_root / "app.py").exists()
        else ""
    )
    if not entrypoint:
        return None

    python_cmd = _python_executable_command()
    port = _alloc_port(runtime_root, start=8100, end=8799)
    module_name = Path(entrypoint).stem

    entrypoint_text = _read_runtime_text_if_exists(runtime_root / entrypoint).lower()
    requirements_blob = _read_runtime_text_if_exists(runtime_root / "requirements.txt").lower()

    if "fastapi" in requirements_blob or "uvicorn" in requirements_blob or "fastapi(" in entrypoint_text:
        run_command = f"{python_cmd} -m uvicorn {module_name}:app --host 127.0.0.1 --port {port} --reload"
    elif "flask" in requirements_blob or "flask(" in entrypoint_text:
        run_command = f"{python_cmd} -m flask --app {module_name}:app run --host 127.0.0.1 --port {port}"
    else:
        run_command = f"{python_cmd} {entrypoint}"

    rel_runtime_root = runtime_root.relative_to(project_root) if runtime_root != project_root else Path(".")
    return {
        "label": runtime_root.name,
        "runtime_type": "python",
        "entrypoint": entrypoint if rel_runtime_root == Path(".") else f"{rel_runtime_root.as_posix()}/{entrypoint}",
        "run_command": _prefix_command_for_runtime_dir(rel_runtime_root, run_command),
        "setup_command": _prefix_command_for_runtime_dir(
            rel_runtime_root, f"{python_cmd} -m pip install -r requirements.txt"
        ) if (runtime_root / "requirements.txt").exists() else None,
        "install_required": _python_install_required(runtime_root),
        "preview_url": f"http://127.0.0.1:{port}",
        "runtime_root": runtime_root.as_posix(),
    }


def _detect_rust_runtime_at_path(project_root: Path, runtime_root: Path) -> dict | None:
    if not (runtime_root / "Cargo.toml").exists():
        return None

    # Check if it's a web server by scanning dependencies
    cargo_text = _read_runtime_text_if_exists(runtime_root / "Cargo.toml").lower()
    web_crates = {"axum", "actix-web", "rocket", "warp", "tide", "salvo", "poem", "ntex"}
    is_web = any(crate in cargo_text for crate in web_crates)

    preview_url: str | None = None
    if is_web:
        # Scan source for explicit bind address first
        for rel_path in ("src/main.rs", "src/lib.rs", "main.rs"):
            text = _read_runtime_text_if_exists(runtime_root / rel_path)
            explicit = re.search(r"(?:127\.0\.0\.1|localhost|0\.0\.0\.0):(\d{4,5})", text)
            if explicit:
                preview_url = f"http://127.0.0.1:{explicit.group(1)}"
                break
        if not preview_url:
            port = _alloc_port(runtime_root, start=8100, end=8799)
            preview_url = f"http://127.0.0.1:{port}"

    rel_runtime_root = runtime_root.relative_to(project_root) if runtime_root != project_root else Path(".")
    return {
        "label": runtime_root.name,
        "runtime_type": "rust",
        "entrypoint": "Cargo.toml" if rel_runtime_root == Path(".") else f"{rel_runtime_root.as_posix()}/Cargo.toml",
        "run_command": _prefix_command_for_runtime_dir(rel_runtime_root, "cargo run"),
        "setup_command": _prefix_command_for_runtime_dir(rel_runtime_root, "cargo fetch"),
        "install_required": False,
        "preview_url": preview_url,
        "runtime_root": runtime_root.as_posix(),
    }


# ---------------------------------------------------------------------------
# LLM-based runtime inference (fallback for unknown project types)
# ---------------------------------------------------------------------------

_LLM_CACHE: dict[str, tuple[float, dict]] = {}
_LLM_CACHE_TTL = 300.0  # 5 minutes
_RUNTIME_INFERENCE_CACHE_VERSION = 2


def _llm_infer_runtime(project_root: Path, blueprint: dict | None = None) -> dict | None:
    """Ask Claude to figure out how to start projects we can't detect via file patterns.

    Result is cached in memory (5 min TTL) and on disk (.devhub/runtime_inference.json).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    cache_key = str(project_root.resolve())
    now = time.time()

    # Memory cache
    if cache_key in _LLM_CACHE:
        ts, cached = _LLM_CACHE[cache_key]
        if now - ts < _LLM_CACHE_TTL:
            return cached

    # Disk cache
    disk_cache_path = project_root / ".devhub" / "runtime_inference.json"
    try:
        if disk_cache_path.exists():
            cached_data = json.loads(disk_cache_path.read_text(encoding="utf-8"))
            if (
                cached_data.get("_version") == _RUNTIME_INFERENCE_CACHE_VERSION
                and now - cached_data.get("_ts", 0) < _LLM_CACHE_TTL * 6
            ):  # 30 min on disk
                result = {k: v for k, v in cached_data.items() if not k.startswith("_")}
                # Re-check port availability
                if result.get("preview_url"):
                    m = re.search(r":(\d{4,5})$", result["preview_url"])
                    if m:
                        old_port = int(m.group(1))
                        new_port = find_free_port(preferred=old_port, range_start=5000, range_end=9900)
                        if new_port != old_port:
                            result["preview_url"] = f"http://127.0.0.1:{new_port}"
                            result["run_command"] = re.sub(r"\b" + str(old_port) + r"\b", str(new_port), result.get("run_command") or "")
                _LLM_CACHE[cache_key] = (now, result)
                return result
    except Exception:
        pass

    # Collect project context
    key_files = [
        "package.json", "requirements.txt", "pyproject.toml", "Cargo.toml",
        "go.mod", "Gemfile", "composer.json", "pom.xml", "build.gradle",
        "Makefile", "Dockerfile", "go.sum", ".env.example",
        "main.py", "app.py", "server.py", "index.js", "main.go", "main.rs",
        "Program.cs", "mix.exs", "pubspec.yaml",
    ]
    file_contexts: list[str] = []
    for fname in key_files:
        fp = project_root / fname
        if fp.exists():
            try:
                content = fp.read_text(encoding="utf-8", errors="ignore")[:1500]
                file_contexts.append(f"=== {fname} ===\n{content}")
            except Exception:
                pass

    try:
        entries = sorted(
            p.name for p in project_root.iterdir()
            if p.name not in RUNTIME_SKIP_DIRS and not p.name.startswith(".")
        )
        dir_listing = "  ".join(entries[:50])
    except Exception:
        dir_listing = ""

    blueprint_text = ""
    if blueprint and isinstance(blueprint, dict):
        tech = blueprint.get("tech_stack") or []
        desc = str(blueprint.get("description") or "")[:200]
        if tech or desc:
            blueprint_text = f"Blueprint — {desc} | Stack: {', '.join(str(t) for t in tech[:8])}"

    context = "\n\n".join(filter(None, [
        f"Project files: {dir_listing}",
        "\n\n".join(file_contexts[:7]),
        blueprint_text,
    ]))

    python_cmd = _python_executable_command()
    prompt = f"""You are a DevOps expert. Given this project, output exactly how to run its dev server.

{context}

Respond ONLY with a valid JSON object — no markdown fences, no explanation:
{{
  "runtime_type": "node|python|django|rust|go|ruby|php|java|dotnet|elixir|static|unknown",
  "run_command": "shell command using $PORT where the port belongs",
  "setup_command": "install deps command or null",
  "install_required": true,
  "preview_port_range_start": 8000
}}

Port injection rules (use $PORT literally in run_command):
  Vite/React:    npm run dev -- --host 127.0.0.1 --port $PORT
  Django:        {python_cmd} manage.py runserver 127.0.0.1:$PORT
  FastAPI:       {python_cmd} -m uvicorn main:app --host 127.0.0.1 --port $PORT --reload
  Flask:         {python_cmd} -m flask --app app:app run --host 127.0.0.1 --port $PORT
  Go:            go run . -addr 127.0.0.1:$PORT  (or PORT=$PORT go run . if it reads env)
  Ruby/Rails:    bundle exec rails server -p $PORT -b 127.0.0.1
  PHP:           php -S 127.0.0.1:$PORT -t public
  Spring Boot:   ./mvnw spring-boot:run -Dspring-boot.run.arguments=--server.port=$PORT
  .NET:          dotnet run --urls http://127.0.0.1:$PORT
  Elixir:        mix phx.server  (with PORT=$PORT set via env)
  Static HTML:   {python_cmd} -m http.server $PORT --bind 127.0.0.1
  Unknown:       set run_command to null

preview_port_range_start: 5200 for frontend, 8000 for backend APIs."""

    try:
        import anthropic  # noqa: PLC0415

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = re.sub(r"```(?:json)?\n?", "", text).strip().rstrip("`").strip()
        data = json.loads(text)

        range_start = max(1024, int(data.get("preview_port_range_start") or 8000))
        port = _alloc_port(project_root, start=range_start, end=min(range_start + 699, 9900))

        raw_cmd = str(data.get("run_command") or "")
        run_command = _substitute_port(raw_cmd, port) if raw_cmd else None

        result: dict = {
            "label": project_root.name,
            "runtime_type": data.get("runtime_type", "unknown"),
            "entrypoint": None,
            "run_command": run_command or None,
            "setup_command": data.get("setup_command") or None,
            "install_required": bool(data.get("install_required", False)),
            "preview_url": f"http://127.0.0.1:{port}" if run_command else None,
        }

        _LLM_CACHE[cache_key] = (now, result)

        # Persist to disk
        try:
            disk_cache_path.parent.mkdir(parents=True, exist_ok=True)
            disk_cache_path.write_text(
                json.dumps(
                    {**result, "_ts": now, "_version": _RUNTIME_INFERENCE_CACHE_VERSION},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

        return result
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Probe / wait utilities
# ---------------------------------------------------------------------------

def _loopback_probe_candidates(preview_url: str) -> list[str]:
    try:
        parsed = urlparse(preview_url)
    except Exception:
        return [preview_url]
    host = (parsed.hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        return [preview_url]

    candidates = [preview_url]
    for alternate_host in ("127.0.0.1", "localhost", "[::1]"):
        if alternate_host.strip("[]") == host:
            continue
        netloc = alternate_host
        if parsed.port:
            netloc = f"{alternate_host}:{parsed.port}"
        if parsed.username:
            userinfo = parsed.username
            if parsed.password:
                userinfo = f"{userinfo}:{parsed.password}"
            netloc = f"{userinfo}@{netloc}"
        candidate = urlunparse(parsed._replace(netloc=netloc))
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _probe_preview_url(preview_url: str, timeout: float = 1.2) -> tuple[bool, str | None]:
    errors: list[str] = []
    for candidate_url in _loopback_probe_candidates(preview_url):
        request = Request(candidate_url, headers={"User-Agent": "DevHub Preview Probe"})
        try:
            with urlopen(request, timeout=timeout) as response:
                response.read(1)
            return True, None
        except HTTPError:
            return True, None
        except URLError as exc:
            errors.append(f"{candidate_url}: {getattr(exc, 'reason', None) or exc}")
        except Exception as exc:
            errors.append(f"{candidate_url}: {exc}")
    return False, "; ".join(errors) if errors else "Preview probe failed."


def _wait_for_preview_ready(
    preview_url: str, sandbox, process_id: str, timeout_seconds: float = 8.0
) -> tuple[bool, str | None]:
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


# ---------------------------------------------------------------------------
# Runtime combiner
# ---------------------------------------------------------------------------

def _combine_detected_runtime(
    project_root: Path, frontend_runtime: dict | None, backend_runtime: dict | None
) -> dict:
    if frontend_runtime and backend_runtime:
        combined = dict(frontend_runtime)
        setup_commands = [
            str(command).strip()
            for command in (backend_runtime.get("setup_command"), frontend_runtime.get("setup_command"))
            if str(command or "").strip()
        ]
        grouped_setup = [f"({command})" for command in dict.fromkeys(setup_commands)]
        combined.update({
            "label": f"{project_root.name} ({backend_runtime.get('runtime_type')} + {frontend_runtime.get('runtime_type')})",
            "runtime_type": "fullstack",
            "entrypoint": frontend_runtime.get("entrypoint") or backend_runtime.get("entrypoint"),
            "run_command": frontend_runtime.get("run_command") or backend_runtime.get("run_command"),
            "setup_command": " && ".join(grouped_setup) or None,
            "install_required": bool(backend_runtime.get("install_required")) or bool(frontend_runtime.get("install_required")),
            "preview_url": frontend_runtime.get("preview_url") or backend_runtime.get("preview_url"),
            "primary_runtime": frontend_runtime,
            "secondary_runtime": backend_runtime,
            "secondary_runtimes": [backend_runtime],
        })
        return combined
    return frontend_runtime or backend_runtime or {}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def detect_runtime(project_root: Path, blueprint: dict | None = None) -> dict:
    """Detect how to run the project at `project_root`.

    1. Tries file-based detection for known frameworks (Node, Django, Python, Rust).
    2. Falls back to LLM inference (Claude) for everything else.
    """
    node_roots = sorted(
        _runtime_root_candidates(project_root, "package.json"),
        key=lambda r: _runtime_root_score(project_root, r, ("frontend", "client", "web", "ui", "app")),
    )
    django_roots = sorted(
        _runtime_root_candidates(project_root, "manage.py"),
        key=lambda r: _runtime_root_score(project_root, r, ("backend", "server", "api", "app")),
    )
    python_roots = sorted(
        set(
            _runtime_root_candidates(project_root, "main.py")
            + _runtime_root_candidates(project_root, "app.py")
        ),
        key=lambda r: _runtime_root_score(project_root, r, ("backend", "server", "api", "app")),
    )
    rust_roots = sorted(
        _runtime_root_candidates(project_root, "Cargo.toml"),
        key=lambda r: _runtime_root_score(project_root, r, ("backend", "server", "api", "service")),
    )

    frontend_runtime = next(
        (r for r in (_detect_node_runtime_at_path(project_root, root) for root in node_roots)
         if r and r.get("run_command")),
        None,
    )
    django_runtime = next(
        (r for r in (_detect_django_runtime_at_path(project_root, root) for root in django_roots) if r),
        None,
    )
    python_runtime = next(
        (r for r in (_detect_python_runtime_at_path(project_root, root) for root in python_roots) if r),
        None,
    )
    rust_runtime = next(
        (r for r in (_detect_rust_runtime_at_path(project_root, root) for root in rust_roots) if r),
        None,
    )
    backend_runtime = django_runtime or python_runtime or rust_runtime

    combined = _combine_detected_runtime(project_root, frontend_runtime, backend_runtime)
    if combined and combined.get("run_command"):
        return combined
    if frontend_runtime and frontend_runtime.get("run_command"):
        return frontend_runtime
    if backend_runtime and backend_runtime.get("run_command"):
        return backend_runtime

    # Static HTML fallback
    static_roots = _runtime_root_candidates(project_root, "index.html", max_depth=1)
    if static_roots:
        runtime_root = sorted(
            static_roots,
            key=lambda r: _runtime_root_score(project_root, r, ("public", "static", "web", "app")),
        )[0]
        rel_runtime_root = runtime_root.relative_to(project_root) if runtime_root != project_root else Path(".")
        python_cmd = _python_executable_command()
        port = _alloc_port(runtime_root, start=4173, end=4872)
        return {
            "label": runtime_root.name,
            "runtime_type": "static",
            "entrypoint": "index.html" if rel_runtime_root == Path(".") else f"{rel_runtime_root.as_posix()}/index.html",
            "run_command": _prefix_command_for_runtime_dir(
                rel_runtime_root, f"{python_cmd} -m http.server {port} --bind 127.0.0.1"
            ),
            "setup_command": None,
            "install_required": False,
            "preview_url": f"http://127.0.0.1:{port}",
        }

    # LLM fallback for Go, Ruby, PHP, Java, .NET, Elixir, etc.
    llm_result = _llm_infer_runtime(project_root, blueprint)
    if llm_result and llm_result.get("run_command"):
        return llm_result

    return {
        "label": project_root.name,
        "runtime_type": "unknown",
        "entrypoint": None,
        "run_command": None,
        "setup_command": None,
        "install_required": False,
        "preview_url": None,
    }


# ---------------------------------------------------------------------------
# Identifiers & response helpers
# ---------------------------------------------------------------------------

def runtime_process_id(workspace_id: str) -> str:
    return f"{workspace_id}_runtime"


def setup_process_id(workspace_id: str) -> str:
    return f"{workspace_id}_setup"


def _runtime_with_process_status(runtime: dict, status: dict) -> dict:
    """Prefer the command/URL that a running process was actually started with."""
    if not status.get("running"):
        return runtime
    updated = dict(runtime)
    if status.get("command"):
        updated["run_command"] = status["command"]
    if status.get("preview_url"):
        updated["preview_url"] = status["preview_url"]
    return updated


def _runtime_response_payload(
    runtime: dict, process_id: str, sandbox, *, wait_for_preview: bool = False
) -> dict:
    status = sandbox.get_status(process_id)
    runtime = _runtime_with_process_status(runtime, status)
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
        # POST: wait actively for the server to respond (called once on start)
        ready, preview_error = _wait_for_preview_ready(preview_url, sandbox, process_id)
        payload["status"] = sandbox.get_status(process_id)
        payload["ready"] = ready
        payload["preview_error"] = preview_error
    else:
        # GET: do NOT probe — the browser can reach localhost directly.
        # Return ready=True so the frontend shows the iframe immediately.
        payload["ready"] = True
        payload["preview_error"] = None

    return payload
