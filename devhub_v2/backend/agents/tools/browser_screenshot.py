"""
BrowserScreenshotTool - capture a page screenshot with a local headless browser.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

from .base_tool import BaseTool, ToolContext, ToolResult

DEFAULT_WAIT_MS = 1500
MAX_WAIT_MS = 15000
DEFAULT_WIDTH = 1440
DEFAULT_HEIGHT = 1024
MAX_DIMENSION = 2400


def _find_browser_executable() -> str | None:
    candidates = [
        shutil.which("msedge"),
        shutil.which("chrome"),
        shutil.which("chromium"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        if Path(candidate).exists():
            return str(candidate)
    return None


class BrowserScreenshotTool(BaseTool):
    name = "browser_screenshot"
    description = (
        "Capture a screenshot of a web page with a local headless browser. "
        "Use this for UI verification, especially with stage='before' before edits "
        "and stage='after' once the redesign is done."
    )
    read_only = False

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Absolute http(s) or file URL to capture.",
                },
                "stage": {
                    "type": "string",
                    "description": "Verification label such as before or after.",
                    "enum": ["before", "after", "check"],
                },
                "output_path": {
                    "type": "string",
                    "description": "Optional relative PNG path inside the workspace.",
                },
                "wait_ms": {
                    "type": "integer",
                    "description": f"Time to wait for page rendering in milliseconds (default {DEFAULT_WAIT_MS}).",
                },
                "width": {
                    "type": "integer",
                    "description": f"Viewport width in pixels (default {DEFAULT_WIDTH}).",
                },
                "height": {
                    "type": "integer",
                    "description": f"Viewport height in pixels (default {DEFAULT_HEIGHT}).",
                },
            },
            "required": ["url"],
        }

    def validate_input(self, input_data: dict) -> dict:
        validated = super().validate_input(input_data)
        url = str(validated.get("url") or "").strip()
        if not url:
            raise ValueError("Parameter 'url' is required.")

        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https", "file"}:
            raise ValueError("Only http, https, and file URLs are supported.")

        stage = str(validated.get("stage") or "check").strip().lower()
        if stage not in {"before", "after", "check"}:
            raise ValueError("Parameter 'stage' must be one of: before, after, check.")
        validated["stage"] = stage
        validated["url"] = url
        return validated

    def call(self, input_data: dict, context: ToolContext) -> ToolResult:
        browser = _find_browser_executable()
        if not browser:
            return ToolResult(error="No supported browser executable was found for headless screenshots.")

        stage = str(input_data.get("stage") or "check")
        wait_ms = min(max(int(input_data.get("wait_ms") or DEFAULT_WAIT_MS), 0), MAX_WAIT_MS)
        width = min(max(int(input_data.get("width") or DEFAULT_WIDTH), 320), MAX_DIMENSION)
        height = min(max(int(input_data.get("height") or DEFAULT_HEIGHT), 320), MAX_DIMENSION)

        output_rel = str(input_data.get("output_path") or "").strip()
        if not output_rel:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            output_rel = f".devhub_artifacts/screenshots/{stage}-{timestamp}.png"

        output_path = (context.workspace_path / output_rel).resolve()
        try:
            output_path.relative_to(context.workspace_path.resolve())
        except ValueError:
            return ToolResult(error="Access denied: output_path must stay inside the workspace.")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        common_args = [
            "--disable-gpu",
            "--hide-scrollbars",
            "--run-all-compositor-stages-before-draw",
            f"--virtual-time-budget={wait_ms}",
            f"--window-size={width},{height}",
            f"--screenshot={output_path}",
            str(input_data["url"]),
        ]
        attempts = [
            [browser, "--headless=new", *common_args],
            [browser, "--headless", *common_args],
        ]

        last_error = ""
        for command in attempts:
            try:
                completed = subprocess.run(
                    command,
                    cwd=str(context.workspace_path),
                    capture_output=True,
                    text=True,
                    timeout=45,
                )
                if completed.returncode == 0 and output_path.exists():
                    rel_output = str(output_path.relative_to(context.workspace_path)).replace("\\", "/")
                    return ToolResult(
                        output=(
                            f"Saved {stage} screenshot for {input_data['url']} to {rel_output} "
                            f"using {Path(browser).name}."
                        ),
                        files_modified=[rel_output],
                        metadata={
                            "url": input_data["url"],
                            "stage": stage,
                            "output_path": rel_output,
                            "browser": browser,
                        },
                    )
                last_error = (completed.stderr or completed.stdout or f"Exit code: {completed.returncode}").strip()
            except subprocess.TimeoutExpired:
                last_error = "Headless browser timed out while capturing the page."
            except Exception as exc:
                last_error = str(exc)

        return ToolResult(
            error=f"Failed to capture screenshot for {input_data['url']}: {last_error or 'Unknown browser error.'}"
        )
