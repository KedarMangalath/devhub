import subprocess
import os
import psutil
import threading
import queue
import time
from typing import Dict, Optional, List, Callable

class ProcessHandle:
    def __init__(self, process: subprocess.Popen, cmd: str, work_dir: str):
        self.process = process
        self.cmd = cmd
        self.work_dir = work_dir
        self.output_queue = queue.Queue()
        self.running = True
        self.start_time = time.time()
        
        # Start reading stdout/stderr
        self.stdout_thread = threading.Thread(target=self._read_stream, args=(process.stdout, 'stdout'))
        self.stderr_thread = threading.Thread(target=self._read_stream, args=(process.stderr, 'stderr'))
        self.stdout_thread.daemon = True
        self.stderr_thread.daemon = True
        self.stdout_thread.start()
        self.stderr_thread.start()

    def _read_stream(self, stream, stream_type):
        if not stream:
            return
        
        try:
            for line in iter(stream.readline, b''):
                if line:
                    self.output_queue.put((stream_type, line.decode('utf-8', errors='replace')))
        except Exception:
            pass
        finally:
            stream.close()

    def get_new_output(self, timeout=0.1) -> List[str]:
        output = []
        try:
            while True:
                _, line = self.output_queue.get(block=False)
                output.append(line)
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
            self.running = False

class SandboxManager:
    """Manages execution of background processes for the DevHub IDE terminal and agents."""
    def __init__(self):
        self.processes: Dict[str, ProcessHandle] = {}

    def run_command(self, process_id: str, cmd: str, work_dir: str, env: dict = None) -> ProcessHandle:
        """Starts a new background process. Returns existing handle if already running."""
        if process_id in self.processes and self.processes[process_id].is_running():
            return self.processes[process_id]

        # Prepare environment
        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        # Create process
        try:
            # CREATE_NEW_PROCESS_GROUP flag is important on Windows to let us kill the tree easily without killing ourselves
            process = subprocess.Popen(
                cmd,
                cwd=work_dir,
                env=run_env,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            
            handle = ProcessHandle(process, cmd, work_dir)
            self.processes[process_id] = handle
            return handle

        except Exception as e:
            raise RuntimeError(f"Failed to start process: {str(e)}")

    def get_output(self, process_id: str) -> List[str]:
        if process_id not in self.processes:
            return []
        
        handle = self.processes[process_id]
        return handle.get_new_output()

    def get_status(self, process_id: str) -> dict:
        handle = self.processes.get(process_id)
        if not handle:
            return {
                "exists": False,
                "running": False,
            }

        running = handle.is_running()
        return {
            "exists": True,
            "running": running,
            "command": handle.cmd,
            "work_dir": handle.work_dir,
            "uptime_seconds": int(time.time() - handle.start_time),
        }

    def send_input(self, process_id: str, input_str: str):
        if process_id in self.processes and self.processes[process_id].is_running():
            proc = self.processes[process_id].process
            proc.stdin.write(input_str.encode('utf-8'))
            proc.stdin.flush()

    def kill_process(self, process_id: str):
        if process_id in self.processes:
            self.processes[process_id].kill()
            del self.processes[process_id]

    def cleanup(self):
        for pid, handle in list(self.processes.items()):
            handle.kill()
        self.processes.clear()

# Global singleton
sandbox = SandboxManager()
