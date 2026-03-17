import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
WORKSPACE_DIR = DATA_DIR / "workspaces"

class WorkspaceManager:
    """Manages isolated file workspaces for agents to perform operations safely without affecting source projects until approved."""
    
    def __init__(self):
        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

    def create_workspace(self, source_path: str) -> str:
        """Copies a project to a new isolated workspace and returns the workspace ID."""
        workspace_id = str(uuid.uuid4())
        dest_path = WORKSPACE_DIR / workspace_id
        
        try:
            # We don't copy standard node_modules, .git, venv etc. to save space and time in sandboxes
            shutil.copytree(
                source_path, 
                dest_path, 
                ignore=shutil.ignore_patterns('node_modules', '.git', '__pycache__', '.venv', 'venv')
            )
            return workspace_id
        except Exception as e:
            raise RuntimeError(f"Failed to create workspace: {str(e)}")

    def get_workspace_path(self, workspace_id: str) -> Path:
        """Returns the absolute path to a workspace."""
        path = WORKSPACE_DIR / workspace_id
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
        path = WORKSPACE_DIR / workspace_id
        if path.exists():
            shutil.rmtree(path)

workspace_manager = WorkspaceManager()
