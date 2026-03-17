import os
import shutil
import uuid
import json
from pathlib import Path
from typing import Optional

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".next", ".nuxt", "target", "vendor", ".idea", ".vscode", ".devhub",
}

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
WORKSPACE_DIR = DATA_DIR / "workspaces"
PROJECTS_DIR = DATA_DIR / "projects"

class WorkspaceManager:
    """Manages isolated file workspaces for agents to perform operations safely without affecting source projects until approved."""
    
    def __init__(self):
        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    def _workspace_meta_path(self, workspace_id: str) -> Path:
        return WORKSPACE_DIR / f"{workspace_id}.json"

    def _read_workspace_metadata(self, workspace_id: str) -> Optional[dict]:
        meta_path = self._workspace_meta_path(workspace_id)
        if not meta_path.exists():
            return None
        return json.loads(meta_path.read_text(encoding='utf-8'))

    def _write_workspace_metadata(self, workspace_id: str, metadata: dict):
        meta_path = self._workspace_meta_path(workspace_id)
        meta_path.write_text(json.dumps(metadata), encoding='utf-8')

    def create_workspace(self, source_path: str, managed: bool = False) -> str:
        """Registers a project path as a workspace and returns the workspace ID."""
        source = Path(source_path).expanduser().resolve()
        if not source.exists() or not source.is_dir():
            raise RuntimeError(f"Source path does not exist: {source_path}")

        workspace_id = str(uuid.uuid4())
        metadata = {
            "source_path": str(source),
            "managed": managed,
        }
        self._write_workspace_metadata(workspace_id, metadata)
        return workspace_id

    def get_workspace_info(self, workspace_id: str) -> dict:
        metadata = self._read_workspace_metadata(workspace_id)
        if metadata:
            return metadata

        legacy_path = WORKSPACE_DIR / workspace_id
        if legacy_path.exists():
            return {
                "source_path": str(legacy_path.resolve()),
                "managed": True,
                "legacy": True,
            }

        raise ValueError(f"Workspace {workspace_id} does not exist.")

    def get_workspace_path(self, workspace_id: str) -> Path:
        """Returns the absolute path to a workspace."""
        info = self.get_workspace_info(workspace_id)
        path = Path(info["source_path"]).expanduser().resolve()
        if not path.exists():
            raise ValueError(f"Workspace {workspace_id} does not exist.")
        return path

    def read_file(self, workspace_id: str, file_rel_path: str) -> str:
        workspace_path = self.get_workspace_path(workspace_id)
        file_path = workspace_path / file_rel_path
        
        # Security check: ensure path is within workspace
        try:
            file_path.resolve().relative_to(workspace_path.resolve())
        except ValueError:
            raise PermissionError("Access denied: File is outside of workspace.")

        if not file_path.exists():
            raise FileNotFoundError(f"File {file_rel_path} not found in workspace.")
            
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def write_file(self, workspace_id: str, file_rel_path: str, content: str):
        workspace_path = self.get_workspace_path(workspace_id)
        file_path = workspace_path / file_rel_path
        
        # Security check
        try:
            file_path.resolve().relative_to(workspace_path.resolve())
        except ValueError:
            raise PermissionError("Access denied: File is outside of workspace.")

        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def delete_workspace(self, workspace_id: str):
        metadata = self._read_workspace_metadata(workspace_id)
        if metadata:
            path = Path(metadata["source_path"]).expanduser().resolve()
            if metadata.get("managed") and path.exists():
                shutil.rmtree(path)
            meta_path = self._workspace_meta_path(workspace_id)
            if meta_path.exists():
                meta_path.unlink()
            return

        path = WORKSPACE_DIR / workspace_id
        if path.exists():
            shutil.rmtree(path)

workspace_manager = WorkspaceManager()
