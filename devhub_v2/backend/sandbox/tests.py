import io
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from sandbox.executor import SandboxManager


def _mock_process():
    process = Mock()
    process.stdout = io.BytesIO(b"")
    process.stderr = io.BytesIO(b"")
    process.stdin = Mock()
    process.poll.return_value = None
    process.pid = 4242
    return process


class SandboxManagerTests(SimpleTestCase):
    @patch.dict("os.environ", {"DEVHUB_SANDBOX_MODE": "local"}, clear=False)
    @patch("sandbox.executor.subprocess.Popen")
    def test_local_mode_uses_host_process_execution(self, mock_popen):
        mock_popen.return_value = _mock_process()

        manager = SandboxManager()
        handle = manager.run_command("proc_local", "npm run dev", "C:\\repo")

        self.assertEqual(handle.cmd, "npm run dev")
        self.assertEqual(manager.get_status("proc_local")["backend"], "local")
        self.assertTrue(mock_popen.called)
        self.assertEqual(mock_popen.call_args.kwargs["cwd"], "C:\\repo")
        self.assertTrue(mock_popen.call_args.kwargs["shell"])

    @patch.dict(
        "os.environ",
        {
            "DEVHUB_SANDBOX_MODE": "docker",
            "DEVHUB_SANDBOX_IMAGE": "devhub/universal:latest",
            "DEVHUB_SANDBOX_RUNTIME": "runsc",
            "DEVHUB_SANDBOX_NETWORK": "bridge",
        },
        clear=False,
    )
    @patch("sandbox.executor.shutil.which", return_value="docker")
    @patch("sandbox.executor.subprocess.Popen")
    def test_docker_mode_wraps_runtime_command_with_container_launch(self, mock_popen, _mock_which):
        mock_popen.return_value = _mock_process()

        manager = SandboxManager()
        manager.run_command(
            "proc_docker",
            "python manage.py runserver 127.0.0.1:8100",
            "C:\\repo",
            kind="runtime",
            preview_url="http://127.0.0.1:8100",
        )

        args = mock_popen.call_args.args[0]
        self.assertEqual(args[0], "docker")
        self.assertIn("--runtime", args)
        self.assertIn("runsc", args)
        self.assertIn("-p", args)
        self.assertIn("8100:8100", args)
        self.assertIn("C:\\repo:/workspace", args)
        self.assertIn("devhub/universal:latest", args)
        self.assertIn("/bin/sh", args)
        self.assertIn("-lc", args)
        self.assertIn("0.0.0.0:8100", args[-1])

    @patch.dict(
        "os.environ",
        {
            "DEVHUB_SANDBOX_MODE": "docker",
            "DEVHUB_SANDBOX_IMAGE": "devhub/universal:latest",
        },
        clear=False,
    )
    @patch("sandbox.executor.shutil.which", return_value="docker")
    @patch("sandbox.executor.subprocess.Popen")
    def test_docker_terminal_uses_container_shell(self, mock_popen, _mock_which):
        mock_popen.return_value = _mock_process()

        manager = SandboxManager()
        handle = manager.run_command("proc_term", "cmd.exe", "C:\\repo", kind="terminal")

        args = mock_popen.call_args.args[0]
        self.assertEqual(args[0], "docker")
        self.assertEqual(args[-1], "/bin/sh")
        self.assertEqual(handle.cmd, "/bin/sh (docker sandbox)")

    @patch.dict(
        "os.environ",
        {
            "DEVHUB_SANDBOX_MODE": "docker",
            "DEVHUB_SANDBOX_IMAGE": "devhub/universal:latest",
        },
        clear=False,
    )
    @patch("sandbox.executor.shutil.which", return_value="docker")
    @patch("sandbox.executor.subprocess.Popen")
    def test_docker_python_setup_installs_packages_into_workspace(self, mock_popen, _mock_which):
        mock_popen.return_value = _mock_process()

        manager = SandboxManager()
        manager.run_command(
            "proc_setup",
            "python -m pip install -r requirements.txt",
            "C:\\repo",
            kind="setup",
        )

        args = mock_popen.call_args.args[0]
        command = args[-1]

        self.assertIn("mkdir -p .devhub/python-packages", command)
        self.assertIn("python -m pip install --target .devhub/python-packages -r requirements.txt", command)
        self.assertIn("PYTHONPATH=/workspace/.devhub/python-packages", args)

    @patch.dict(
        "os.environ",
        {
            "DEVHUB_SANDBOX_MODE": "docker",
            "DEVHUB_SANDBOX_IMAGE": "devhub/universal:latest",
        },
        clear=False,
    )
    @patch("sandbox.executor.shutil.which", return_value="docker")
    @patch("sandbox.executor.subprocess.Popen")
    def test_docker_setup_preserves_node_install_when_python_requirements_are_also_present(self, mock_popen, _mock_which):
        mock_popen.return_value = _mock_process()

        manager = SandboxManager()
        manager.run_command(
            "proc_setup_combo",
            "npm install && python -m pip install -r requirements.txt",
            "C:\\repo",
            kind="setup",
        )

        args = mock_popen.call_args.args[0]
        command = args[-1]

        self.assertIn("npm install", command)
        self.assertIn("mkdir -p .devhub/python-packages", command)
        self.assertIn("python -m pip install --target .devhub/python-packages -r requirements.txt", command)
