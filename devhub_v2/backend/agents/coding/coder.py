import json
import logging
from typing import Callable, List

from agents.core.base import BaseAgent, describe_image_attachments
from agents.core.workspace import workspace_manager

logger = logging.getLogger(__name__)


class CoderAgent(BaseAgent):
    BASE_SYSTEM_INSTRUCTION = (
        "You are an expert autonomous coder. Given a feature specification, an implementation plan, project memory, "
        "and current project context, you write the precise code changes required to implement it.\n"
        "You must return ONLY a JSON array, where each element represents a file to be written or modified.\n\n"
        "JSON format:\n"
        "[\n"
        "  {\n"
        "    \"path\": \"relative/path/to/file.py\",\n"
        "    \"content\": \"<exact raw file content to write (replacing file entirely)>\"\n"
        "  }\n"
        "]\n\n"
        "Rules:\n"
        "1. DO NOT return markdown blocks (```json ... ```).\n"
        "2. DO NOT include explanations, only the valid JSON array.\n"
        "3. Ensure the 'content' string handles quotes and newlines safely according to JSON specs.\n"
        "4. Rewrite the entire file content for each changed file; do not omit unchanged sections.\n"
        "5. Respect the implementation plan and keep related UI, logic, styles, wiring, and docs aligned.\n"
        "6. Prefer extending existing project structure over creating duplicate parallel implementations.\n"
        "7. Preserve the existing runnable scaffold and runtime conventions unless the request explicitly asks for a migration.\n"
        "8. If the project already uses React/Vite, Django, FastAPI, or another framework structure, do not fall back to ad-hoc top-level HTML/CSS/JS files.\n"
        "9. Use the smallest file set that fully satisfies the request while preserving existing behavior outside the requested change.\n"
        "10. Treat project-specific overrides or active skill instructions appended later in the system prompt as required constraints."
    )

    def __init__(self, ai_config: dict | None = None, customization_instruction: str = ""):
        system_instruction = self.BASE_SYSTEM_INSTRUCTION
        if customization_instruction.strip():
            system_instruction = f"{system_instruction}\n\n{customization_instruction.strip()}"
        super().__init__(
            role="Senior Software Engineer",
            system_instruction=system_instruction,
            ai_config=ai_config,
        )

    def implement_feature(
        self,
        workspace_id: str,
        feature_title: str,
        feature_desc: str,
        spec: dict,
        files_context: List[dict],
        implementation_plan: dict | None = None,
        project_memory: str = "",
        supporting_context: str = "",
        customization_context: str = "",
        request_attachments: list[dict] | None = None,
    ) -> dict:
        """
        Takes spec and context, generates code, and writes it directly to the workspace.
        files_context should be a list of dicts: [{'path': '...', 'content': '...'}, ...]
        """
        context_str = "\n\n".join([f"--- FILE: {f['path']} ---\n{f['content']}" for f in files_context])
        attachment_context = describe_image_attachments(request_attachments) or "No image attachments were supplied."

        prompt = f"""
## Feature Required
Title: {feature_title}
Description: {feature_desc}

## Attached Images
{attachment_context}

## AI Specification
{json.dumps(spec, indent=2) if spec else 'No spec available.'}

## Implementation Plan
{json.dumps(implementation_plan, indent=2) if implementation_plan else 'No formal plan available.'}

## Project Memory
{project_memory or 'No project memory available yet.'}

## Supporting Context
{supporting_context or 'No additional supporting context.'}

## Project Customization
{customization_context or 'No project-specific implementation overrides were supplied for this change.'}

## Current File Context
(These are the relevant files before your changes. If you need to modify them, rewrite the entire file content incorporating your changes.)
{context_str}

Please generate the required file modifications and additions to implement this feature.
Keep the project consistent across related files when the request affects multiple surfaces.
Return ONLY the JSON array as instructed.
"""

        print("CoderAgent: Generating implementation...")
        response_text = self.generate_with_attachments(prompt, request_attachments) if request_attachments else self.generate(prompt)

        if response_text.startswith("```json"):
            response_text = response_text.split("```json", 1)[1]
        if response_text.endswith("```"):
            response_text = response_text.rsplit("```", 1)[0]

        response_text = response_text.strip()

        try:
            changes = json.loads(response_text)
            if not isinstance(changes, list):
                raise ValueError("Response is not a JSON array")
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse LLM output as JSON: %s\nOutput was: %s...", exc, response_text[:500])
            return {"error": "Failed to parse code output from LLM.", "raw_response": response_text}

        applied_changes = []

        print(f"CoderAgent: Writing {len(changes)} files to workspace {workspace_id}...")
        for change in changes:
            filepath = change.get("path")
            content = change.get("content")

            if filepath and content is not None:
                try:
                    workspace_manager.write_file(workspace_id, filepath, content)
                    applied_changes.append(filepath)
                    print(f"  -> Wrote {filepath}")
                except Exception as exc:
                    logger.error("Failed to write file %s: %s", filepath, exc)

        return {
            "status": "success",
            "files_modified": applied_changes,
        }

    def fix_runtime_error(
        self,
        workspace_id: str,
        error_text: str,
        files_context: List[dict],
        runtime_type: str = "unknown",
        on_event: Callable[[dict], None] | None = None,
    ) -> dict:
        """Fix a runtime startup error by analyzing the traceback and patching the relevant files."""
        events: list[dict] = []
        tool_events: list[dict] = []
        files_accessed: list[str] = []
        workspace_actions: list[dict] = []

        def _emit(event: dict) -> None:
            payload = dict(event or {})
            events.append(payload)
            if on_event:
                try:
                    on_event(payload)
                except Exception:
                    logger.debug("Runtime autofix event callback failed", exc_info=True)

        def _tool_start(tool: str, summary: dict) -> None:
            event = {"type": "tool_start", "tool": tool, "summary": summary}
            tool_events.append({
                "type": "tool_start",
                "tool": tool,
                "args_preview": {k: str(v)[:100] for k, v in summary.items()},
            })
            _emit(event)

        def _tool_end(tool: str, success: bool, preview: str) -> None:
            event = {"type": "tool_end", "tool": tool, "success": success, "preview": preview[:200]}
            tool_events.append({
                "type": "tool_end",
                "tool": tool,
                "success": success,
                "preview": preview[:200],
            })
            _emit(event)

        context_str = "\n\n".join([f"--- FILE: {f['path']} ---\n{f['content']}" for f in files_context])
        _emit({"type": "thought", "text": "Inspecting the startup traceback and the files it points to."})

        for file_entry in files_context:
            path = str(file_entry.get("path") or "").strip()
            if not path:
                continue
            files_accessed.append(path)
            _tool_start("file_read", {"path": path, "label": path})
            _tool_end("file_read", True, "Loaded traceback context")

        _emit({"type": "thought", "text": "Generating the smallest code change that should unblock startup."})

        prompt = f"""
## Runtime Startup Error

The {runtime_type} project failed to start with the following error:

```
{error_text}
```

## Affected Files
{context_str}

## Task
Analyze the error and produce the minimal code changes to fix it.

Common causes and fixes:
- `ModuleNotFoundError: No module named 'X.Y'` — the sub-module moved to a different package in a newer version; update the import to the new location
- `ImportError: cannot import name 'X' from 'Y'` — the class/function was renamed, moved, or deprecated; update the import path or usage
- `AttributeError: module 'X' has no attribute 'Y'` — API change; find the new API and update usage

Return ONLY the JSON array of file changes as instructed. Do not guess — only fix what the traceback directly points to.
        """
        print(f"CoderAgent: Fixing runtime error in workspace {workspace_id}...")
        response_text = self.generate(prompt)

        for fence in ("```json", "```"):
            if response_text.startswith(fence):
                response_text = response_text[len(fence):]
        if response_text.endswith("```"):
            response_text = response_text.rsplit("```", 1)[0]
        response_text = response_text.strip()

        try:
            changes = json.loads(response_text)
            if not isinstance(changes, list):
                raise ValueError("Not a JSON array")
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("fix_runtime_error: failed to parse LLM output: %s", exc)
            _emit({"type": "thought", "text": "The runtime fix response could not be parsed into file changes."})
            return {
                "status": "failed",
                "error": "Failed to parse fix from LLM.",
                "raw_response": response_text[:500],
                "events": events,
                "tool_events": tool_events,
                "files_accessed": files_accessed,
                "workspace_actions": workspace_actions,
            }

        applied_changes = []
        _emit({"type": "thought", "text": "Applying the generated patch to the workspace."})
        for change in changes:
            filepath = change.get("path")
            content = change.get("content")
            if filepath and content is not None:
                summary = {"path": filepath, "label": filepath}
                _tool_start("file_edit", summary)
                try:
                    workspace_manager.write_file(workspace_id, filepath, content)
                    applied_changes.append(filepath)
                    workspace_actions.append({
                        "type": "file_edit",
                        "status": "completed",
                        "detail": f"Updated {filepath}",
                    })
                    _tool_end("file_edit", True, f"Updated {filepath}")
                    print(f"  [autofix] Wrote {filepath}")
                except Exception as exc:
                    logger.error("fix_runtime_error: failed to write %s: %s", filepath, exc)
                    workspace_actions.append({
                        "type": "file_edit",
                        "status": "failed",
                        "detail": f"Failed to update {filepath}: {exc}",
                    })
                    _tool_end("file_edit", False, f"Failed to update {filepath}: {exc}")

        if applied_changes:
            _emit({"type": "thought", "text": "Patch applied. Restarting the runtime to verify the fix."})
        else:
            _emit({"type": "thought", "text": "No workspace files were changed by the runtime fixer."})

        return {
            "status": "success",
            "files_modified": applied_changes,
            "events": events,
            "tool_events": tool_events,
            "files_accessed": files_accessed,
            "workspace_actions": workspace_actions,
        }
