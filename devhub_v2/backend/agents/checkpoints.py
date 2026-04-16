from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path, PurePosixPath

from django.utils import timezone

BASE_DIR = Path(__file__).resolve().parents[2]
CHECKPOINTS_DIR = BASE_DIR / "data" / "chat-checkpoints"
CHECKPOINT_EXCLUDED_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "target",
    "vendor",
    ".idea",
    ".vscode",
    "out",
}


def project_checkpoint_root(project_id: str) -> Path:
    return CHECKPOINTS_DIR / str(project_id)


def checkpoint_root(project_id: str, checkpoint_id: str) -> Path:
    return project_checkpoint_root(project_id) / str(checkpoint_id)


def checkpoint_snapshot_path(project_id: str, checkpoint_id: str) -> Path:
    return checkpoint_root(project_id, checkpoint_id) / "snapshot"


def checkpoint_meta_path(project_id: str, checkpoint_id: str) -> Path:
    return checkpoint_root(project_id, checkpoint_id) / "meta.json"


def _normalize_rel_path(file_path: str) -> str:
    normalized = str(file_path or "").replace("\\", "/").strip("/")
    if not normalized:
        return ""
    pure_path = PurePosixPath(normalized)
    if any(part == ".." for part in pure_path.parts):
        raise ValueError(f"Unsafe checkpoint path: {file_path}")
    return pure_path.as_posix()


def _iter_workspace_entries(root: Path):
    if not root.exists() or not root.is_dir():
        return
    root = root.resolve()
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in CHECKPOINT_EXCLUDED_DIRS)
        current_path = Path(current_root)
        rel_dir = current_path.relative_to(root)
        yield rel_dir, dirnames, sorted(filenames)


def _build_manifest(root: Path) -> tuple[set[str], dict[str, Path]]:
    directories: set[str] = {""}
    files: dict[str, Path] = {}
    if not root.exists() or not root.is_dir():
        return directories, files

    for rel_dir, _, filenames in _iter_workspace_entries(root):
        rel_dir_str = "" if str(rel_dir) == "." else rel_dir.as_posix()
        directories.add(rel_dir_str)
        for filename in filenames:
            rel_path = filename if not rel_dir_str else f"{rel_dir_str}/{filename}"
            files[rel_path] = root / rel_path
    return directories, files


def _files_differ(left: Path | None, right: Path) -> bool:
    if left is None or not left.exists():
        return True
    try:
        return left.read_bytes() != right.read_bytes()
    except Exception:
        return True


def create_workspace_checkpoint(project_id: str, workspace_path: Path, *, label: str = "", source: str = "chat") -> dict:
    CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint_id = uuid.uuid4().hex
    root = checkpoint_root(project_id, checkpoint_id)
    snapshot_path = checkpoint_snapshot_path(project_id, checkpoint_id)
    root.mkdir(parents=True, exist_ok=False)
    snapshot_path.mkdir(parents=True, exist_ok=False)

    try:
        directories, files = _build_manifest(workspace_path)
        for rel_dir in sorted(item for item in directories if item):
            (snapshot_path / rel_dir).mkdir(parents=True, exist_ok=True)
        for rel_path, source_path in files.items():
            target_path = snapshot_path / rel_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)

        metadata = {
            "id": checkpoint_id,
            "project_id": str(project_id),
            "workspace_path": str(workspace_path),
            "source": str(source or "chat"),
            "label": str(label or "").strip(),
            "created_at": timezone.now().isoformat(),
            "file_count": len(files),
            "excluded_dirs": sorted(CHECKPOINT_EXCLUDED_DIRS),
        }
        checkpoint_meta_path(project_id, checkpoint_id).write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return metadata
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise


def load_workspace_checkpoint(project_id: str, checkpoint_id: str) -> dict:
    if not str(checkpoint_id or '').strip():
        raise FileNotFoundError("Checkpoint id is required.")
    meta_path = checkpoint_meta_path(project_id, checkpoint_id)
    snapshot_path = checkpoint_snapshot_path(project_id, checkpoint_id)
    if not meta_path.exists() or not snapshot_path.exists():
        raise FileNotFoundError(f"Checkpoint {checkpoint_id} does not exist for project {project_id}.")
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata["snapshot_path"] = str(snapshot_path)
    return metadata


def delete_workspace_checkpoint(project_id: str, checkpoint_id: str) -> None:
    if not str(checkpoint_id or '').strip():
        return
    shutil.rmtree(checkpoint_root(project_id, checkpoint_id), ignore_errors=True)


def snapshot_previous_contents(project_id: str, checkpoint_id: str, file_paths: list[str]) -> dict[str, str]:
    if not str(checkpoint_id or '').strip():
        return {}
    snapshot_path = checkpoint_snapshot_path(project_id, checkpoint_id)
    if not snapshot_path.exists():
        return {}

    previous_contents: dict[str, str] = {}
    for raw_path in file_paths or []:
        normalized = _normalize_rel_path(raw_path)
        if not normalized:
            continue
        target_path = snapshot_path / normalized
        try:
            target_path.resolve().relative_to(snapshot_path.resolve())
        except Exception:
            continue
        if target_path.exists() and target_path.is_file():
            previous_contents[normalized] = target_path.read_text(encoding="utf-8", errors="ignore")
    return previous_contents


def restore_workspace_checkpoint(project_id: str, workspace_path: Path, checkpoint_id: str) -> dict:
    if not str(checkpoint_id or '').strip():
        raise FileNotFoundError("Checkpoint id is required.")
    metadata = load_workspace_checkpoint(project_id, checkpoint_id)
    snapshot_path = checkpoint_snapshot_path(project_id, checkpoint_id)

    snapshot_dirs, snapshot_files = _build_manifest(snapshot_path)
    workspace_dirs, workspace_files = _build_manifest(workspace_path)

    files_to_remove = sorted(path for path in workspace_files if path not in snapshot_files)
    files_to_copy = sorted(
        path for path, snapshot_file in snapshot_files.items()
        if _files_differ(workspace_files.get(path), snapshot_file)
    )
    restored_files = sorted(set(files_to_remove + files_to_copy))

    for rel_path in files_to_remove:
        target_path = workspace_path / rel_path
        if target_path.exists():
            target_path.unlink()

    workspace_only_dirs = sorted(
        (path for path in workspace_dirs if path and path not in snapshot_dirs),
        key=lambda item: item.count("/"),
        reverse=True,
    )
    for rel_dir in workspace_only_dirs:
        target_dir = workspace_path / rel_dir
        try:
            target_dir.rmdir()
        except OSError:
            continue

    for rel_dir in sorted(path for path in snapshot_dirs if path):
        (workspace_path / rel_dir).mkdir(parents=True, exist_ok=True)

    for rel_path in files_to_copy:
        source_path = snapshot_files[rel_path]
        target_path = workspace_path / rel_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)

    return {
        "checkpoint": metadata,
        "restored_files": restored_files,
    }
