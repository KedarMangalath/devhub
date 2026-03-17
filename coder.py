"""
CLAUDE CODE - Elite Agent Edition
==================================
Intelligent agent that never gets stuck, creates award-winning UIs
"""

import os
import json
import hashlib
import asyncio
import ast
import re
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

# Rich UI
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.tree import Tree
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from rich.align import Align
from rich.live import Live
from rich.status import Status

# Backend
from google import genai
from google.genai import types

load_dotenv()
console = Console()


# ==========================================
# 🎨 ULTRA-PREMIUM UI
# ==========================================

class ClaudeCodeUI:
    @staticmethod
    def show_header():
        header = Panel(
            Align.center(
                "[bold cyan]⚡ CLAUDE CODE - ELITE EDITION[/bold cyan]\n"
                "[dim]Award-Winning UI Generator • Never Gets Stuck • Professional Grade[/dim]\n\n"
                "[white]🚀 Production Ready • 🎨 Stunning Design • 🧠 Intelligent Execution[/white]"
            ),
            border_style="bright_cyan",
            box=box.DOUBLE
        )
        console.print(header)
    
    @staticmethod
    def show_thinking(message: str):
        console.print(f"\n[bold cyan]💭 {message}...[/bold cyan]")
    
    @staticmethod
    def create_status(message: str) -> Status:
        """Create a status spinner for ongoing operations"""
        return Status(f"[bold cyan]{message}[/bold cyan]", console=console, spinner="dots")
    
    @staticmethod
    def show_status(message: str, status_type: str = "info"):
        """Show a status message with appropriate styling"""
        icons = {
            "thinking": "🧠",
            "writing": "📝",
            "running": "⚙️",
            "success": "✅",
            "error": "❌",
            "info": "💡",
            "waiting": "⏳"
        }
        colors = {
            "thinking": "cyan",
            "writing": "yellow",
            "running": "blue",
            "success": "green",
            "error": "red",
            "info": "white",
            "waiting": "magenta"
        }
        icon = icons.get(status_type, "💡")
        color = colors.get(status_type, "white")
        console.print(f"[bold {color}]{icon} {message}[/bold {color}]")
    
    @staticmethod
    def show_step(step_num: int, total: int, action: str):
        """Show current step with progress"""
        progress = "█" * step_num + "░" * (total - step_num)
        console.print(f"\n[cyan]Step {step_num}/{total}[/cyan] [{progress}] [white]{action}[/white]")
    
    @staticmethod
    def show_file_created(path: str, size: int):
        console.print(f"  [green]✓[/green] Created [cyan]{path}[/cyan] [dim]({size} bytes)[/dim]")
    
    @staticmethod
    def show_file_updated(path: str, size: int):
        console.print(f"  [yellow]✏️[/yellow] Updated [cyan]{path}[/cyan] [dim]({size} bytes)[/dim]")
    
    @staticmethod
    def show_file_read(path: str, size: int):
        console.print(f"  [blue]📖[/blue] Read [cyan]{path}[/cyan] [dim]({size} bytes)[/dim]")
    
    @staticmethod
    def show_command_skip(command: str, reason: str):
        console.print(f"  [yellow]⚠[/yellow] Skipping [dim]{command}[/dim] - {reason}")
    
    @staticmethod
    def show_command_run(command: str, success: bool):
        icon = "[green]✓[/green]" if success else "[red]✗[/red]"
        console.print(f"  {icon} Executed [cyan]{command}[/cyan]")
    
    @staticmethod
    def show_agent_message(text: str, title: str = "Agent"):
        panel = Panel(
            Markdown(text),
            title=f"[bold cyan]{title}[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2)
        )
        console.print()
        console.print(panel)
    
    @staticmethod
    def show_completion(files_count: int = 0, iterations: int = 0):
        """Show project creation completion message"""
        console.print()
        stats = ""
        if files_count > 0 or iterations > 0:
            stats = f"\n[dim]📁 Files created: {files_count} • 🔄 Iterations: {iterations}[/dim]\n"
        
        console.print(Panel(
            Align.center(
                "[bold green]✓ Project Created Successfully![/bold green]\n\n"
                "[white]Your award-winning website is ready.[/white]\n"
                f"{stats}"
                "[dim]Run the provided commands to view it.[/dim]"
            ),
            border_style="green",
            box=box.DOUBLE
        ))
    
    @staticmethod
    def show_execution_complete(action: str = "Task", files_count: int = 0, iterations: int = 0):
        """Show that agent has finished executing with a prominent completion panel"""
        console.print()
        
        # Build stats line
        stats_parts = []
        if files_count > 0:
            stats_parts.append(f"📁 Files modified: {files_count}")
        if iterations > 0:
            stats_parts.append(f"🔄 Iterations: {iterations}")
        stats_line = " • ".join(stats_parts) if stats_parts else ""
        
        console.print(Panel(
            Align.center(
                f"[bold green]✅ {action} Complete![/bold green]\n\n"
                "[white]All requested changes have been applied.[/white]\n"
                f"[dim]{stats_line}[/dim]\n\n"
                "[cyan]Ready for next command...[/cyan]"
            ),
            border_style="green",
            box=box.DOUBLE
        ))
    
    @staticmethod
    def show_instructions(instructions: List[str]):
        """Show user instructions in a beautiful panel"""
        instruction_text = "\n".join([f"[cyan]{i+1}.[/cyan] {cmd}" for i, cmd in enumerate(instructions)])
        console.print()
        console.print(Panel(
            f"[bold white]🚀 Next Steps:[/bold white]\n\n{instruction_text}",
            title="How to Run",
            border_style="yellow",
            box=box.ROUNDED
        ))

    @staticmethod
    def show_project_selection(projects: List[str]) -> str:
        """Show project selection menu"""
        console.clear()
        
        # Header
        header = Panel(
            Align.center(
                "[bold cyan]⚡ CLAUDE CODE - ELITE EDITION[/bold cyan]\n"
                "[dim]Project Manager[/dim]"
            ),
            border_style="bright_cyan",
            box=box.DOUBLE
        )
        console.print(header)
        console.print()
        
        # Options
        options = ["[bold green]+ Create New Project[/bold green]"]
        for p in projects:
            options.append(f"[bold white]📂 {p}[/bold white]")
            
        console.print("[bold yellow]Select a project to work on:[/bold yellow]")
        for idx, opt in enumerate(options):
            console.print(f"  [cyan]{idx + 1}.[/cyan] {opt}")
            
        console.print()
        while True:
            choice = Prompt.ask("[bold cyan]Enter choice[/bold cyan]", default="1")
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    if idx == 0:
                        return "NEW"
                    return projects[idx - 1]
            except ValueError:
                pass
            console.print("[red]Invalid choice. Try again.[/red]")


# ==========================================
# 🧠 INTELLIGENT COMMAND ANALYZER
# ==========================================

class CommandIntelligence:
    """Knows which commands block and handles them intelligently"""
    
    BLOCKING_COMMANDS = [
        'npm start', 'npm run dev', 'npm run serve',
        'python -m http.server', 'python manage.py runserver',
        'flask run', 'uvicorn', 'gunicorn',
        'ng serve', 'yarn dev', 'yarn start',
        'next dev', 'vite', 'gatsby develop'
    ]
    
    SAFE_COMMANDS = [
        'npm install', 'npm ci', 'yarn install',
        'pip install', 'pip install -r requirements.txt',
        'npm run build', 'npm run test',
        'pytest', 'python -m pytest',
        'git init', 'git add', 'git commit'
    ]
    
    @classmethod
    def is_blocking(cls, command: str) -> bool:
        """Check if command will block/run forever"""
        cmd_lower = command.lower().strip()
        return any(blocking in cmd_lower for blocking in cls.BLOCKING_COMMANDS)
    
    @classmethod
    def is_safe_to_run(cls, command: str) -> bool:
        """Check if command is safe to run (non-blocking)"""
        cmd_lower = command.lower().strip()
        return any(safe in cmd_lower for safe in cls.SAFE_COMMANDS)
    
    @classmethod
    def get_user_instruction(cls, command: str) -> str:
        """Get instruction for user to run command manually"""
        if 'npm start' in command or 'npm run dev' in command:
            return f"Run `{command}` and open http://localhost:3000"
        elif 'python -m http.server' in command:
            port = re.search(r'(\d+)', command)
            port_num = port.group(1) if port else '8000'
            return f"Run `{command}` and open http://localhost:{port_num}"
        elif 'flask run' in command:
            return f"Run `{command}` and open http://localhost:5000"
        else:
            return f"Run `{command}` to start your application"


# ==========================================
# 🧠 DATA STRUCTURES
# ==========================================

@dataclass
class FileMetadata:
    path: str
    language: str
    size: int
    lines: int
    imports: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    last_modified: float = 0
    hash: str = ""


# ==========================================
# 📚 CONTEXT MANAGER
# ==========================================

class ContextManager:
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.file_index: Dict[str, FileMetadata] = {}
        self.file_hashes: Dict[str, str] = {}
        
    def discover_files(self, extensions: List[str] = None) -> List[Path]:
        if extensions is None:
            extensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.vue']
        
        files = []
        ignore_dirs = {'node_modules', '.git', '__pycache__', 'venv', 'env', '.venv', 'dist', 'build'}
        
        for ext in extensions:
            for file_path in self.project_path.rglob(f'*{ext}'):
                if any(ignored in file_path.parts for ignored in ignore_dirs):
                    continue
                files.append(file_path)
        
        return files
    
    def compute_hash(self, content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()
    
    def detect_language(self, file_path: Path) -> str:
        ext_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
            '.jsx': 'javascript', '.tsx': 'typescript',
            '.html': 'html', '.css': 'css', '.vue': 'vue'
        }
        return ext_map.get(file_path.suffix, 'unknown')
    
    def index_file(self, file_path: Path) -> Optional[FileMetadata]:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            return None
        
        file_hash = self.compute_hash(content)
        relative_path = str(file_path.relative_to(self.project_path))
        
        language = self.detect_language(file_path)
        
        metadata = FileMetadata(
            path=relative_path,
            language=language,
            size=len(content),
            lines=len(content.splitlines()),
            last_modified=file_path.stat().st_mtime,
            hash=file_hash
        )
        
        self.file_index[relative_path] = metadata
        self.file_hashes[relative_path] = file_hash
        return metadata
    
    def index_project(self) -> int:
        files = self.discover_files()
        for file_path in files:
            self.index_file(file_path)
        return len(self.file_index)

    def get_project_summary(self) -> str:
        """Get a summary of the project structure and key files"""
        summary = ["Project Structure:"]
        
        # Sort files for stable output
        sorted_files = sorted(self.file_index.keys())
        
        # Create a simple tree view
        if not sorted_files:
            return "Empty Project"
            
        # Top level structure
        for f in sorted_files:
            summary.append(f"- {f} ({self.file_index[f].language})")
            
        return "\n".join(summary)


# ==========================================
# 🛠️ INTELLIGENT TOOL ORCHESTRATOR
# ==========================================

class IntelligentToolOrchestrator:
    def __init__(self, project_path: str, context_manager: ContextManager, ui: ClaudeCodeUI):
        self.project_path = Path(project_path)
        self.context_manager = context_manager
        self.ui = ui
        self.cmd_intel = CommandIntelligence()
        self.user_instructions = []  # Commands user needs to run manually
    
    def write_file(self, path: str, content: str) -> str:
        """Write file and show beautiful feedback"""
        full_path = self.project_path / path
        file_existed = full_path.exists()  # Check BEFORE writing
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.context_manager.index_file(full_path)
            
            # Show appropriate message based on whether file existed
            if file_existed:
                self.ui.show_file_updated(path, len(content))
            else:
                self.ui.show_file_created(path, len(content))
            
            action = "updated" if file_existed else "created"
            return json.dumps({"success": True, "path": path, "bytes": len(content), "action": action})
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    def read_file(self, path: str) -> str:
        """Read file contents and show feedback"""
        full_path = self.project_path / path
        
        try:
            if not full_path.exists():
                return json.dumps({"error": f"File not found: {path}"})
            
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            self.ui.show_file_read(path, len(content))
            
            return json.dumps({"success": True, "path": path, "content": content, "bytes": len(content)})
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    def list_directory(self, path: str = ".") -> str:
        """List directory"""
        full_path = self.project_path / path
        
        try:
            entries = []
            if full_path.exists() and full_path.is_dir():
                for item in sorted(full_path.iterdir()):
                    if item.name.startswith('.') or item.name in ['__pycache__', 'node_modules']:
                        continue
                    entries.append({
                        "name": item.name,
                        "type": "directory" if item.is_dir() else "file"
                    })
            return json.dumps({"path": path, "entries": entries})
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    def run_command(self, command: str) -> str:
        """Intelligently handle commands - execute safe ones, save blocking ones for user"""
        
        # Check if command will block
        if self.cmd_intel.is_blocking(command):
            instruction = self.cmd_intel.get_user_instruction(command)
            self.user_instructions.append(instruction)
            self.ui.show_command_skip(command, "Long-running process")
            
            return json.dumps({
                "skipped": True,
                "reason": "This is a long-running/blocking command",
                "instruction": instruction,
                "message": "Command saved for user to run manually"
            })
        
        # Execute safe commands
        if self.cmd_intel.is_safe_to_run(command):
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                    timeout=120  # 2 minutes max
                )
                
                success = result.returncode == 0
                self.ui.show_command_run(command, success)
                
                output = f"Exit: {result.returncode}\n\nSTDOUT:\n{result.stdout[:1000]}\n\nSTDERR:\n{result.stderr[:1000]}"
                
                return json.dumps({
                    "success": success,
                    "exit_code": result.returncode,
                    "output": output
                })
            except subprocess.TimeoutExpired:
                return json.dumps({"error": "Command timed out"})
            except Exception as e:
                return json.dumps({"error": str(e)})
        
        # Unknown command - ask user
        self.user_instructions.append(f"Run: {command}")
        return json.dumps({
            "skipped": True,
            "reason": "Unknown command type",
            "instruction": f"Run: {command}"
        })
    
    def get_tool_declarations(self) -> List[types.Tool]:
        return [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name="write_file",
                        description="Write a file. Use this to create all project files.",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "path": types.Schema(type=types.Type.STRING, description="File path"),
                                "content": types.Schema(type=types.Type.STRING, description="Complete file content")
                            },
                            required=["path", "content"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="read_file",
                        description="Read a file's contents. Use this before modifying existing files to understand current state.",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties={"path": types.Schema(type=types.Type.STRING, description="File path to read")},
                            required=["path"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="list_directory",
                        description="List directory contents",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties={"path": types.Schema(type=types.Type.STRING)}
                        )
                    ),
                    types.FunctionDeclaration(
                        name="run_command",
                        description="Run a command. Safe commands (npm install, pip install) execute immediately. Blocking commands (npm start, npm run dev) are saved for the user to run manually.",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties={"command": types.Schema(type=types.Type.STRING)},
                            required=["command"]
                        )
                    )
                ]
            )
        ]
    
    def execute_tool_call(self, function_call) -> str:
        func_name = function_call.name
        args = {k: v for k, v in function_call.args.items()}
        
        if func_name == "write_file":
            return self.write_file(args.get("path", ""), args.get("content", ""))
        elif func_name == "read_file":
            return self.read_file(args.get("path", ""))
        elif func_name == "list_directory":
            return self.list_directory(args.get("path", "."))
        elif func_name == "run_command":
            return self.run_command(args.get("command", ""))
        else:
            return json.dumps({"error": f"Unknown function: {func_name}"})


# ==========================================
# 🤖 CLAUDE CODE INTELLIGENCE
# ==========================================

class CodingAgent:
    def __init__(self, project_id: str, location: str, context_manager: ContextManager, tool_orchestrator: IntelligentToolOrchestrator, ui: ClaudeCodeUI):
        self.client = genai.Client(vertexai=True, project=project_id, location=location)
        self.context_manager = context_manager
        self.tool_orchestrator = tool_orchestrator
        self.ui = ui
        self.model_name = os.getenv("GEMINI_MODEL")
        
        # ELITE SYSTEM PROMPT - DYNAMIC
        file_count = len(context_manager.file_index)
        
        if file_count > 0:
            # EXISTING PROJECT MODE
            self.system_prompt = f"""You are an elite Senior Full-Stack Developer working on an existing project.
            
CONTEXT:
You are working on: {context_manager.project_path.name}
Project Structure:
{context_manager.get_project_summary()}

MISSION:
- Maintain and improve the existing codebase.
- Respect existing patterns, style, and structure.
- When asked to add features, integrate them seamlessly.
- DO NOT rewrite the entire application unless explicitly asked.
- Only modify files that are necessary for the task.

COMMANDS:
- Use `write_file` to create NEW or OVERWRITE existing files.
- Use `run_command` to execute tests or installs.
- REMINDER: Blocking commands (npm start, python runserver) should be skipped/instructed, not run.
"""
        else:
            # NEW PROJECT MODE
            self.system_prompt = """You are an elite AI that creates  websites and applications.

� YOUR MISSION: Create production-ready, stunning, professional-grade code from scratch.

🎨 UI DESIGN EXCELLENCE (For Web Apps):
- Modern gradients, Smooth Animations, Professional Typography
- Responsive, Interactive, Premium Design
- Tailwind CSS

🚀 EXECUTION INTELLIGENCE:
- Create ALL necessary files.
- Run npm install / pip install.
- DON'T run blocking commands (npm start).
"""
        
        self.history = []
        # Safety limit to prevent runaway API costs (practically never reached)
        self.SAFETY_LIMIT = int(os.getenv("AGENT_SAFETY_LIMIT", "500"))

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=60))
    def _generate_with_retry(self, **kwargs):
        """Wrapper for generate_content with retry logic for 429 errors"""
        return self.client.models.generate_content(**kwargs)
    
    def _generate_streaming(self, **kwargs):
        """Generate content with streaming for live display"""
        return self.client.models.generate_content_stream(**kwargs)
    
    def _show_live_thinking(self, text: str, is_complete: bool = False):
        """Display thinking text in a live panel"""
        title = "[bold cyan]🧠 Agent Thinking...[/bold cyan]" if not is_complete else "[bold green]💭 Agent Response[/bold green]"
        border = "cyan" if not is_complete else "green"
        
        # Truncate if too long for display
        display_text = text[-2000:] if len(text) > 2000 else text
        if len(text) > 2000:
            display_text = "..." + display_text
        
        panel = Panel(
            Markdown(display_text) if display_text.strip() else "[dim]Processing...[/dim]",
            title=title,
            border_style=border,
            box=box.ROUNDED,
            padding=(0, 1)
        )
        return panel
    
    async def run(self, user_message: str):
        """Run the agent until it naturally completes (stops calling tools)."""
        
        # Use a live status display for the entire execution
        with console.status("[bold cyan]🧠 Analyzing your requirements...[/bold cyan]", spinner="dots") as status:
            current_message = user_message
            iteration = 0
            
            status_messages = {
                "thinking": "🧠 Thinking...",
                "calling_api": "🌐 Calling AI model...",
                "processing": "⚙️ Processing response...",
                "executing_tools": "🔧 Executing tools...",
                "writing_file": "📝 Writing files...",
                "running_command": "⚡ Running commands..."
            }
        
            # Simple loop - runs until AI naturally finishes (no more function calls)
            while True:
                iteration += 1
                
                # Safety limit to prevent runaway costs
                if iteration > self.SAFETY_LIMIT:
                    console.print(f"[red]Safety limit reached ({self.SAFETY_LIMIT} iterations). Stopping.[/red]")
                    break
                
                try:
                    status.update(f"[bold cyan]{status_messages['calling_api']} (iteration {iteration})[/bold cyan]")
                    
                    contents = self.history.copy()
                    if current_message:
                        contents.append(types.Content(role="user", parts=[types.Part(text=current_message)]))
                    
                    # Use streaming for live thinking display
                    status.stop()  # Stop status to show live panel
                    
                    streamed_text = ""
                    function_calls = []
                    final_response = None
                    
                    try:
                        # Use transient=True so the panel disappears after streaming completes
                        with Live(
                            self._show_live_thinking(""),
                            refresh_per_second=8,
                            console=console,
                            transient=True
                        ) as live:
                            for chunk in self._generate_streaming(
                                model=self.model_name,
                                contents=contents,
                                config=types.GenerateContentConfig(
                                    system_instruction=self.system_prompt,
                                    tools=self.tool_orchestrator.get_tool_declarations(),
                                    temperature=0.8,
                                    max_output_tokens=8000
                                )
                            ):
                                # Accumulate text and function calls from chunks
                                if chunk.candidates and chunk.candidates[0].content:
                                    for part in chunk.candidates[0].content.parts:
                                        if part.text:
                                            streamed_text += part.text
                                            live.update(self._show_live_thinking(streamed_text))
                                        elif part.function_call:
                                            function_calls.append(part.function_call)
                                            # Show what tool is being prepared
                                            tool_name = part.function_call.name
                                            tool_info = f"🔧 Preparing: {tool_name}"
                                            if tool_name == "write_file" and part.function_call.args:
                                                file_path = part.function_call.args.get("file_path", "")
                                                tool_info = f"📝 Writing: {Path(file_path).name if file_path else 'file'}"
                                            elif tool_name == "run_command":
                                                tool_info = f"⚡ Preparing command..."
                                            
                                            display = streamed_text + f"\n\n[dim]{tool_info}[/dim]" if streamed_text else tool_info
                                            live.update(self._show_live_thinking(display))
                                final_response = chunk
                        
                        # After Live exits, show final message if substantial
                        if streamed_text and len(streamed_text.strip()) > 50:
                            self.ui.show_agent_message(streamed_text)
                            
                    except Exception as stream_error:
                        # Fallback to non-streaming if streaming fails
                        console.print(f"[dim]Streaming unavailable, using standard mode...[/dim]")
                        response = self._generate_with_retry(
                            model=self.model_name,
                            contents=contents,
                            config=types.GenerateContentConfig(
                                system_instruction=self.system_prompt,
                                tools=self.tool_orchestrator.get_tool_declarations(),
                                temperature=0.8,
                                max_output_tokens=8000
                            )
                        )
                        final_response = response
                        if response.candidates and response.candidates[0].content:
                            for part in response.candidates[0].content.parts:
                                if part.text:
                                    streamed_text += part.text
                                elif part.function_call:
                                    function_calls.append(part.function_call)
                        
                        # Show the message if substantial
                        if streamed_text and len(streamed_text.strip()) > 50:
                            self.ui.show_agent_message(streamed_text)
                    
                    status.start()  # Resume status spinner
                    
                    status.update(f"[bold cyan]{status_messages['processing']}[/bold cyan]")
                    
                    if not final_response or not final_response.candidates or not final_response.candidates[0]:
                        break
                
                    candidate = final_response.candidates[0]
                    
                    if not candidate.content or not candidate.content.parts:
                        break
                
                    # No function calls = AI is done
                    if not function_calls:
                        if current_message:
                            self.history.append(types.Content(role="user", parts=[types.Part(text=current_message)]))
                        self.history.append(candidate.content)
                        
                        status.stop()  # Stop spinner before showing completion
                        
                        # Show final instructions
                        if self.tool_orchestrator.user_instructions:
                            self.ui.show_instructions(self.tool_orchestrator.user_instructions)
                        
                        # Show completion with stats
                        files_count = len(self.context_manager.file_index)
                        if files_count == 0:
                            self.ui.show_completion(files_count, iteration)
                        else:
                            action = "Generation" if iteration > 5 or files_count > 5 else "Task"
                            self.ui.show_execution_complete(action, files_count, iteration)
                        
                        break
                
                    # Execute tools with status updates
                    status.update(f"[bold yellow]{status_messages['executing_tools']} ({len(function_calls)} tool(s))[/bold yellow]")
                    
                    function_responses = []
                    for i, fc in enumerate(function_calls):
                        # Show specific tool being executed
                        tool_status = f"📝 Writing file..." if fc.name == "write_file" else \
                                      f"⚡ Running command..." if fc.name == "run_command" else \
                                      f"📂 Listing directory..." if fc.name == "list_directory" else \
                                      f"🔧 Executing {fc.name}..."
                        status.update(f"[bold yellow]{tool_status} ({i+1}/{len(function_calls)})[/bold yellow]")
                        
                        result = self.tool_orchestrator.execute_tool_call(fc)
                        function_responses.append(
                            types.Part(
                                function_response=types.FunctionResponse(
                                    name=fc.name,
                                    response={"result": result}
                                )
                            )
                        )
                
                    if current_message:
                        self.history.append(types.Content(role="user", parts=[types.Part(text=current_message)]))
                    self.history.append(candidate.content)
                    self.history.append(types.Content(role="user", parts=function_responses))
                    
                    current_message = ""
                    status.update(f"[bold cyan]{status_messages['thinking']}[/bold cyan]")
                    
                except Exception as e:
                    status.stop()
                    console.print(f"[red]❌ Error: {e}[/red]")
                    break


# ==========================================
# 🖥️ MAIN APP
# ==========================================

class ClaudeCodeApp:
    def __init__(self, project_path: str, project_id: str, location: str):
        self.project_path = Path(project_path)
        self.project_id = project_id
        self.location = location
        self.ui = ClaudeCodeUI()
        
        self.context_manager = ContextManager(str(self.project_path))
        self.tool_orchestrator = IntelligentToolOrchestrator(str(self.project_path), self.context_manager, self.ui)
        self.agent = None
    
    def initialize(self):
        with Status("[cyan]Initializing...", console=console):
            count = self.context_manager.index_project()
        
        if count > 0:
            console.print(f"[dim]Found {count} existing files[/dim]\n")
        
        self.agent = CodingAgent(
            self.project_id,
            self.location,
            self.context_manager,
            self.tool_orchestrator,
            self.ui
        )
        
    def scan_projects(self) -> List[str]:
        """Scan for existing project directories"""
        projects = []
        ignore = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', 'dist', 'build', '.idea', '.vscode'}
        
        for item in self.project_path.iterdir():
            if item.is_dir() and item.name not in ignore and not item.name.startswith('.'):
                projects.append(item.name)
        return sorted(projects)

    def switch_project(self, project_dir: str):
        """Switch context to specific project directory"""
        new_path = self.project_path / project_dir
        if not new_path.exists():
            new_path.mkdir(parents=True, exist_ok=True)
            
        # Re-init everything with new path
        self.context_manager = ContextManager(str(new_path))
        self.tool_orchestrator = IntelligentToolOrchestrator(str(new_path), self.context_manager, self.ui)
        
        console.print(f"\n[green]✓[/green] Switched to project: [bold cyan]{project_dir}[/bold cyan]")
        
        # Initial indexing
        with Status(f"[cyan]Indexing {project_dir}...[/cyan]", console=console):
            count = self.context_manager.index_project()
        console.print(f"[dim]Indexed {count} files[/dim]\n")

        self.agent = CodingAgent(
            self.project_id, 
            self.location, 
            self.context_manager, 
            self.tool_orchestrator,
            self.ui
        )

    def run_repl(self):
        # 1. Project Selection Loop
        while True:
            projects = self.scan_projects()
            choice = self.ui.show_project_selection(projects)
            
            if choice == "NEW":
                console.print()
                name = Prompt.ask("[bold cyan]Enter new project name[/bold cyan]")
                if name:
                    self.switch_project(name)
                    break
            else:
                self.switch_project(choice)
                break

        # 2. Main REPL
        self.ui.show_header()
        console.print(f"[dim]Ready to create award-winning projects![/dim]\n")
        
        while True:
            try:
                console.print()
                user_input = Prompt.ask("[bold cyan]➜[/bold cyan]")
                
                if user_input.lower() in ['exit', 'quit', 'q']:
                    console.print("\n[cyan]Goodbye! 👋[/cyan]")
                    break
                
                if not user_input.strip():
                    continue
                
                if user_input.lower() == '/clear':
                    console.clear()
                    self.ui.show_header()
                    continue
                
                if user_input.lower() == '/help':
                    console.print(Panel(
                        "[bold]Examples:[/bold]\n\n"
                        "• Create an award-winning website for my space tech startup\n"
                        "• Build a stunning portfolio with dark mode\n"
                        "• Create a modern SaaS landing page with animations",
                        title="Help",
                        border_style="cyan"
                    ))
                    continue
                
                # Reset instructions for new project
                self.tool_orchestrator.user_instructions = []
                
                asyncio.run(self.agent.run(user_input))
                
            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted[/yellow]")
                if Confirm.ask("Exit?", default=False):
                    break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")


# ==========================================
# 🚀 ENTRY POINT
# ==========================================

if __name__ == "__main__":
    import sys
    
    project_id = os.environ.get("GCP_PROJECT_ID")
    location = os.environ.get("GCP_LOCATION", "us-central1")
    
    if not project_id:
        console.print("[bold red]❌ GCP_PROJECT_ID not set[/bold red]")
        sys.exit(1)
    
    try:
        app = ClaudeCodeApp(os.getcwd(), project_id, location)
        # app.initialize() # Initialization now happens after project selection
        app.run_repl()
    except KeyboardInterrupt:
        console.print("\n[cyan]Goodbye![/cyan]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")