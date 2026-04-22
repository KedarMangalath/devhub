import hashlib
import os
import queue
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List
from urllib.parse import urlparse

import psutil


CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


class ProcessHandle:
    def __init__(
        self,
        process: subprocess.Popen,
        cmd: str,
        work_dir: str,
        *,
        metadata: dict | None = None,
        cleanup_hook: Callable[[], None] | None = None,
    ):
        self.process = process
        self.cmd = cmd
        self.work_dir = work_dir
        self.metadata = metadata or {}
        self.cleanup_hook = cleanup_hook
        self.output_queue = queue.Queue()
        self.running = True
        self.start_time = time.time()

        self.stdout_thread = threading.Thread(target=self._read_stream, args=(process.stdout,))
        self.stderr_thread = threading.Thread(target=self._read_stream, args=(process.stderr,))
        self.stdout_thread.daemon = True
        self.stderr_thread.daemon = True
        self.stdout_thread.start()
        self.stderr_thread.start()

    def _read_stream(self, stream):
        if not stream:
            return

        try:
            for line in iter(stream.readline, b""):
                if line:
                    self.output_queue.put(line.decode("utf-8", errors="replace"))
        except Exception:
            pass
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def get_new_output(self) -> List[str]:
        output: List[str] = []
        try:
            while True:
                output.append(self.output_queue.get(block=False))
        except queue.Empty:
            pass
        return output

    def is_running(self):
        if self.process.poll() is not None:
            self.running = False
            return False
        return True

    def kill(self):
        if self.is_running():
            try:
                parent = psutil.Process(self.process.pid)
                for child in parent.children(recursive=True):
                    child.kill()
                parent.kill()
            except psutil.NoSuchProcess:
                pass
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
        if self.cleanup_hook:
            try:
                self.cleanup_hook()
            except Exception:
                pass
        self.running = False


class SandboxManager:
    """Manages background process execution for the DevHub IDE terminal and runtime."""

    def __init__(self):
        self.processes: Dict[str, ProcessHandle] = {}
        self.mode = (os.environ.get("DEVHUB_SANDBOX_MODE") or "local").strip().lower()
        if self.mode not in {"local", "docker"}:
            self.mode = "local"

        self.docker_bin = (os.environ.get("DEVHUB_SANDBOX_DOCKER_BIN") or "docker").strip() or "docker"
        self.docker_image = (
            os.environ.get("DEVHUB_SANDBOX_IMAGE")
            or "mcr.microsoft.com/devcontainers/universal:2"
        ).strip()
        self.docker_runtime = (os.environ.get("DEVHUB_SANDBOX_RUNTIME") or "").strip()
        self.docker_network = (os.environ.get("DEVHUB_SANDBOX_NETWORK") or "bridge").strip() or "bridge"
        self.container_workdir = (os.environ.get("DEVHUB_SANDBOX_WORKDIR") or "/workspace").strip() or "/workspace"
        self.container_shell = (os.environ.get("DEVHUB_SANDBOX_SHELL") or "/bin/sh").strip() or "/bin/sh"
        self.memory_limit = (os.environ.get("DEVHUB_SANDBOX_MEMORY") or "4g").strip()
        self.cpu_limit = (os.environ.get("DEVHUB_SANDBOX_CPUS") or "4").strip()
        self.pids_limit = (os.environ.get("DEVHUB_SANDBOX_PIDS_LIMIT") or "256").strip()
        self.python_packages_dir = ".devhub/python-packages"

    def details(self) -> dict:
        payload = {"mode": self.mode}
        if self.mode == "docker":
            payload.update(
                {
                    "image": self.docker_image,
                    "runtime": self.docker_runtime or None,
                    "network": self.docker_network,
                    "shell": self.container_shell,
                }
            )
        return payload

    def run_command(
        self,
        process_id: str,
        cmd: str,
        work_dir: str,
        env: dict | None = None,
        *,
        kind: str = "process",
        preview_url: str | None = None,
    ) -> ProcessHandle:
        if process_id in self.processes and self.processes[process_id].is_running():
            return self.processes[process_id]

        try:
            if self.mode == "docker":
                process, display_cmd, metadata, cleanup_hook = self._spawn_docker_process(
                    process_id,
                    cmd,
                    work_dir,
                    env or {},
                    kind=kind,
                    preview_url=preview_url,
                )
            else:
                process, display_cmd, metadata, cleanup_hook = self._spawn_local_process(
                    cmd,
                    work_dir,
                    env or {},
                )

            metadata = dict(metadata)
            metadata["kind"] = kind
            if preview_url:
                metadata["preview_url"] = preview_url

            handle = ProcessHandle(
                process,
                display_cmd,
                work_dir,
                metadata=metadata,
                cleanup_hook=cleanup_hook,
            )
            self.processes[process_id] = handle
            return handle
        except Exception as exc:
            raise RuntimeError(f"Failed to start process: {exc}") from exc

    def _spawn_local_process(self, cmd: str, work_dir: str, env: dict) -> tuple[subprocess.Popen, str, dict, Callable[[], None] | None]:
        run_env = os.environ.copy()
        run_env.update(env)
        process = subprocess.Popen(
            cmd,
            cwd=work_dir,
            env=run_env,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            creationflags=CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
        return process, cmd, {"backend": "local"}, None

    def _spawn_docker_process(
        self,
        process_id: str,
        cmd: str,
        work_dir: str,
        env: dict,
        *,
        kind: str,
        preview_url: str | None,
    ) -> tuple[subprocess.Popen, str, dict, Callable[[], None]]:
        if not shutil.which(self.docker_bin):
            raise RuntimeError(f"Docker executable not found: {self.docker_bin}")

        workspace_path = str(Path(work_dir).resolve())
        container_name = self._container_name(process_id)
        preview_port = self._preview_port(preview_url) if kind == "runtime" else None
        command_text = self._prepare_container_command(cmd, kind=kind, preview_port=preview_port) if kind != "terminal" else ""

        args: list[str] = [self.docker_bin, "run", "--rm", "-i", "--name", container_name]
        if self.docker_runtime:
            args.extend(["--runtime", self.docker_runtime])
        args.extend(["--cap-drop=ALL", "--security-opt", "no-new-privileges"])
        if self.memory_limit:
            args.extend(["--memory", self.memory_limit])
        if self.cpu_limit:
            args.extend(["--cpus", self.cpu_limit])
        if self.pids_limit:
            args.extend(["--pids-limit", self.pids_limit])
        if self.docker_network:
            args.extend(["--network", self.docker_network])
        if preview_port and self.docker_network != "none":
            args.extend(["-p", f"{preview_port}:{preview_port}"])
        args.extend(["-v", f"{workspace_path}:{self.container_workdir}", "-w", self.container_workdir])

        for key, value in self._docker_env(kind=kind, preview_port=preview_port, extra_env=env).items():
            args.extend(["-e", f"{key}={value}"])

        args.append(self.docker_image)
        if kind == "terminal":
            args.append(self.container_shell)
            display_cmd = f"{self.container_shell} (docker sandbox)"
        else:
            args.extend([self.container_shell, "-lc", command_text])
            display_cmd = command_text

        process = subprocess.Popen(
            args,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            creationflags=CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
        metadata = {
            "backend": "docker",
            "container_name": container_name,
            "image": self.docker_image,
            "runtime": self.docker_runtime or None,
            "network": self.docker_network,
            "preview_port": preview_port,
        }
        return process, display_cmd, metadata, lambda: self._cleanup_container(container_name)

    def _docker_env(self, *, kind: str, preview_port: int | None, extra_env: dict) -> dict:
        python_packages_path = f"{self.container_workdir}/{self.python_packages_dir}"
        env = {
            "TERM": "xterm-256color",
            "FORCE_COLOR": "1",
            "PYTHONPATH": python_packages_path,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        }
        if kind == "runtime" and preview_port:
            env.update(
                {
                    "HOST": "0.0.0.0",
                    "PORT": str(preview_port),
                    "BROWSER": "none",
                    "CHOKIDAR_USEPOLLING": "true",
                    "WATCHPACK_POLLING": "true",
                }
            )
        env.update({str(key): str(value) for key, value in extra_env.items() if value is not None})
        return env

    def _prepare_container_command(self, cmd: str, *, kind: str, preview_port: int | None) -> str:
        prepared = cmd.strip()
        lowered = prepared.lower()

        if kind == "setup" and "pip install -r requirements.txt" in lowered:
            packages_dir = self.python_packages_dir.replace("\\", "/")
            replacement = (
                f"mkdir -p {packages_dir} && "
                f"python -m pip install --target {packages_dir} -r requirements.txt"
            )
            prepared = re.sub(
                r"(?i)(?:python\s+-m\s+)?pip\s+install\s+-r\s+requirements\.txt",
                replacement,
                prepared,
                count=1,
            )

        if not preview_port:
            return prepared

        prepared = re.sub(r"127\.0\.0\.1:(\d{2,5})", f"0.0.0.0:{preview_port}", prepared)
        prepared = re.sub(r"localhost:(\d{2,5})", f"0.0.0.0:{preview_port}", prepared)
        prepared = prepared.replace("--bind 127.0.0.1", "--bind 0.0.0.0")
        prepared = prepared.replace("--host 127.0.0.1", "--host 0.0.0.0")

        lowered = prepared.lower()
        if any(token in lowered for token in ("npm run dev", "pnpm dev", "pnpm run dev", "yarn dev", "vite", "next dev")):
            if "--host" not in lowered and "host=" not in lowered:
                prepared = f"HOST=0.0.0.0 PORT={preview_port} {prepared}"

        return prepared

    def _preview_port(self, preview_url: str | None) -> int | None:
        if not preview_url:
            return None
        try:
            parsed = urlparse(preview_url)
            return int(parsed.port) if parsed.port else None
        except Exception:
            return None

    def _container_name(self, process_id: str) -> str:
        suffix = hashlib.md5(process_id.encode("utf-8")).hexdigest()[:10]
        return f"devhub-{suffix}"

    def _cleanup_container(self, container_name: str):
        try:
            subprocess.run(
                [self.docker_bin, "rm", "-f", container_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except Exception:
            pass

    def get_output(self, process_id: str) -> List[str]:
        if process_id not in self.processes:
            return []
        return self.processes[process_id].get_new_output()

    def get_status(self, process_id: str) -> dict:
        handle = self.processes.get(process_id)
        if not handle:
            return {"exists": False, "running": False, "backend": self.mode}

        running = handle.is_running()
        status = {
            "exists": True,
            "running": running,
            "command": handle.cmd,
            "work_dir": handle.work_dir,
            "uptime_seconds": int(time.time() - handle.start_time),
            "backend": handle.metadata.get("backend", self.mode),
            "returncode": handle.process.poll() if not running else None,
        }
        if handle.metadata.get("container_name"):
            status["container_name"] = handle.metadata["container_name"]
        if handle.metadata.get("kind"):
            status["kind"] = handle.metadata["kind"]
        if handle.metadata.get("preview_url"):
            status["preview_url"] = handle.metadata["preview_url"]
        return status

    def send_input(self, process_id: str, input_str: str):
        if process_id in self.processes and self.processes[process_id].is_running():
            proc = self.processes[process_id].process
            if proc.stdin:
                proc.stdin.write(input_str.encode("utf-8"))
                proc.stdin.flush()

    def kill_process(self, process_id: str):
        if process_id in self.processes:
            self.processes[process_id].kill()
            del self.processes[process_id]

    def cleanup(self):
        for pid, handle in list(self.processes.items()):
            handle.kill()
        self.processes.clear()


sandbox = SandboxManager()
