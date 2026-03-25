import json
import os
import shlex
import subprocess
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from openai import OpenAI


SUPPORTED_PROVIDERS = {"openai", "claude", "gemini", "openrouter"}
SUPPORTED_GEMINI_MODES = {"api_key", "gemini_cli", "vertexai"}


def default_model_for_provider(provider: str, gemini_mode: str = "api_key") -> str:
    provider = (provider or "openai").strip().lower()
    gemini_mode = (gemini_mode or "api_key").strip().lower()

    if provider == "claude":
        return os.environ.get("DEVHUB_CLAUDE_MODEL", "claude-3-5-sonnet-latest")
    if provider == "gemini":
        if gemini_mode == "vertexai":
            return os.environ.get("DEVHUB_VERTEX_MODEL", "gemini-2.5-pro")
        return os.environ.get("DEVHUB_GEMINI_MODEL", "gemini-2.5-pro")
    if provider == "openrouter":
        return os.environ.get("DEVHUB_OPENROUTER_MODEL", "openai/gpt-4o-mini")
    return os.environ.get("DEVHUB_OPENAI_MODEL", os.environ.get("DEVHUB_MODEL", "gpt-4o-mini"))


def default_ai_config() -> dict:
    default_provider = _string_value(os.environ.get("DEVHUB_DEFAULT_PROVIDER") or "openai").lower() or "openai"
    if default_provider not in SUPPORTED_PROVIDERS:
        default_provider = "openai"
    return {
        "provider": default_provider,
        "model": default_model_for_provider(default_provider),
        "api_key": "",
        "base_url": "",
        "gemini_mode": "api_key",
        "gemini_cli_command": os.environ.get("DEVHUB_GEMINI_CLI_COMMAND", "gemini"),
        "vertex_project": os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
        "vertex_location": os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
        "vertex_access_token": "",
    }


def _string_value(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_ai_config(config: dict | None) -> dict:
    normalized = default_ai_config()
    raw = config if isinstance(config, dict) else {}

    normalized["provider"] = _string_value(raw.get("provider") or normalized["provider"]).lower() or "openai"
    if normalized["provider"] not in SUPPORTED_PROVIDERS:
        normalized["provider"] = "openai"

    normalized["gemini_mode"] = _string_value(raw.get("gemini_mode") or normalized["gemini_mode"]).lower() or "api_key"
    if normalized["gemini_mode"] not in SUPPORTED_GEMINI_MODES:
        normalized["gemini_mode"] = "api_key"

    for key in ("model", "api_key", "base_url", "gemini_cli_command", "vertex_project", "vertex_location", "vertex_access_token"):
        normalized[key] = _string_value(raw.get(key) or normalized.get(key))

    if not normalized["model"]:
        normalized["model"] = default_model_for_provider(normalized["provider"], normalized["gemini_mode"])

    if normalized["provider"] == "openrouter" and not normalized["base_url"]:
        normalized["base_url"] = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    return normalized


def has_any_ai_credentials() -> bool:
    keys = [
        "OPENAI_API_KEY",
        "DEVHUB_API_KEY",
        "OPENROUTER_API_KEY",
        "DEVHUB_OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
        "DEVHUB_ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "DEVHUB_GEMINI_API_KEY",
        "VERTEX_AI_ACCESS_TOKEN",
        "GOOGLE_CLOUD_ACCESS_TOKEN",
    ]
    return any(_string_value(os.environ.get(key)) for key in keys)


class BaseAgent:
    """Base class for DevHub agents with provider-aware model routing."""

    def __init__(self, role: str, system_instruction: str, model: str | None = None, ai_config: dict | None = None):
        self.role = role
        self.system_instruction = system_instruction
        self.ai_config = normalize_ai_config(ai_config)
        if model:
            self.ai_config["model"] = model
        self.model = self.ai_config["model"]
        self.client = None
        self.chat_history = []

    def generate(self, prompt: str, tools=None, response_schema=None) -> str:
        messages = [
            {"role": "system", "content": self.system_instruction},
            {"role": "user", "content": prompt},
        ]
        return self._complete(messages, response_schema=response_schema)

    def start_chat(self, history=None):
        self.chat_history = history if history else []
        return self

    def send_message(self, message: str) -> str:
        messages = [{"role": "system", "content": self.system_instruction}]
        for msg in self.chat_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": message})

        reply = self._complete(messages)
        self.chat_history.append({"role": "user", "content": message})
        self.chat_history.append({"role": "assistant", "content": reply})
        return reply

    def _complete(self, messages: list[dict], response_schema: bool = False) -> str:
        provider = self.ai_config["provider"]
        if provider in {"openai", "openrouter"}:
            return self._openai_compatible_completion(messages, response_schema=response_schema)
        if provider == "claude":
            return self._claude_completion(messages, response_schema=response_schema)
        if provider == "gemini":
            return self._gemini_completion(messages, response_schema=response_schema)
        raise ValueError(f"Unsupported AI provider: {provider}")

    def _resolve_api_key(self) -> str:
        if self.ai_config.get("api_key"):
            return self.ai_config["api_key"]

        provider = self.ai_config["provider"]
        provider_keys = {
            "openai": ["OPENAI_API_KEY", "DEVHUB_API_KEY"],
            "openrouter": ["OPENROUTER_API_KEY", "DEVHUB_OPENROUTER_API_KEY", "DEVHUB_API_KEY"],
            "claude": ["ANTHROPIC_API_KEY", "DEVHUB_ANTHROPIC_API_KEY", "DEVHUB_API_KEY"],
            "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY", "DEVHUB_GEMINI_API_KEY", "DEVHUB_API_KEY"],
        }
        for key in provider_keys.get(provider, []):
            value = _string_value(os.environ.get(key))
            if value:
                return value
        return ""

    def _resolve_base_url(self) -> str:
        if self.ai_config.get("base_url"):
            return self.ai_config["base_url"]

        provider = self.ai_config["provider"]
        if provider == "openrouter":
            return os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        if provider == "openai":
            return _string_value(os.environ.get("OPENAI_BASE_URL") or os.environ.get("DEVHUB_API_BASE_URL"))
        if provider == "claude":
            return _string_value(os.environ.get("ANTHROPIC_BASE_URL")) or "https://api.anthropic.com/v1/messages"
        if provider == "gemini":
            return _string_value(os.environ.get("GEMINI_BASE_URL")) or "https://generativelanguage.googleapis.com/v1beta"
        return ""

    def _openai_client(self) -> OpenAI:
        if self.client is None:
            api_key = self._resolve_api_key()
            if not api_key:
                raise ValueError(f"No API key configured for {self.ai_config['provider']}.")
            kwargs = {"api_key": api_key}
            base_url = self._resolve_base_url()
            if base_url:
                kwargs["base_url"] = base_url
            self.client = OpenAI(**kwargs)
        return self.client

    def _openai_compatible_completion(self, messages: list[dict], response_schema: bool = False) -> str:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
        if response_schema:
            kwargs["response_format"] = {"type": "json_object"}

        response = self._openai_client().chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def _claude_completion(self, messages: list[dict], response_schema: bool = False) -> str:
        api_key = self._resolve_api_key()
        if not api_key:
            raise ValueError("No API key configured for Claude.")

        system_text = "\n\n".join(str(msg.get("content") or "") for msg in messages if msg.get("role") == "system").strip()
        anthropic_messages = []
        for msg in messages:
            role = msg.get("role")
            if role == "system":
                continue
            anthropic_messages.append(
                {
                    "role": "assistant" if role == "assistant" else "user",
                    "content": [{"type": "text", "text": str(msg.get("content") or "")}],
                }
            )

        if not anthropic_messages:
            anthropic_messages.append({"role": "user", "content": [{"type": "text", "text": "No prompt provided."}]})

        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "temperature": 0.2,
            "messages": anthropic_messages,
        }
        if system_text:
            payload["system"] = system_text

        response = self._http_json(
            self._resolve_base_url(),
            headers={
                "content-type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            payload=payload,
        )
        return "\n".join(
            item.get("text", "")
            for item in response.get("content", [])
            if isinstance(item, dict) and item.get("type") == "text"
        ).strip()

    def _gemini_completion(self, messages: list[dict], response_schema: bool = False) -> str:
        gemini_mode = self.ai_config.get("gemini_mode", "api_key")
        if gemini_mode == "gemini_cli":
            return self._gemini_cli_completion(messages, response_schema=response_schema)
        if gemini_mode == "vertexai":
            return self._vertexai_completion(messages, response_schema=response_schema)
        return self._gemini_api_completion(messages, response_schema=response_schema)

    def _gemini_api_completion(self, messages: list[dict], response_schema: bool = False) -> str:
        api_key = self._resolve_api_key()
        if not api_key:
            raise ValueError("No API key configured for Gemini.")

        system_text, contents = self._gemini_payload(messages)
        payload = {
            "contents": contents or [{"role": "user", "parts": [{"text": "No prompt provided."}]}],
            "generationConfig": {
                "temperature": 0.2,
            },
        }
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        if response_schema:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        base_url = self._resolve_base_url().rstrip("/")
        url = f"{base_url}/models/{quote(self.model)}:generateContent?key={quote(api_key)}"
        response = self._http_json(url, payload=payload)
        return self._gemini_text_from_response(response)

    def _vertexai_completion(self, messages: list[dict], response_schema: bool = False) -> str:
        project = self.ai_config.get("vertex_project") or os.environ.get("GOOGLE_CLOUD_PROJECT")
        location = self.ai_config.get("vertex_location") or os.environ.get("GOOGLE_CLOUD_LOCATION") or "us-central1"
        if not project:
            raise ValueError("Vertex AI requires a Google Cloud project ID.")

        access_token = self._resolve_vertex_access_token()
        system_text, contents = self._gemini_payload(messages)
        payload = {
            "contents": contents or [{"role": "user", "parts": [{"text": "No prompt provided."}]}],
            "generationConfig": {
                "temperature": 0.2,
            },
        }
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        if response_schema:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        custom_base = _string_value(self.ai_config.get("base_url"))
        if custom_base:
            base_url = custom_base.rstrip("/")
        else:
            base_url = f"https://{location}-aiplatform.googleapis.com/v1"

        url = f"{base_url}/projects/{quote(project)}/locations/{quote(location)}/publishers/google/models/{quote(self.model)}:generateContent"
        response = self._http_json(
            url,
            headers={
                "content-type": "application/json",
                "authorization": f"Bearer {access_token}",
            },
            payload=payload,
        )
        return self._gemini_text_from_response(response)

    def _resolve_vertex_access_token(self) -> str:
        explicit = _string_value(self.ai_config.get("vertex_access_token"))
        if explicit:
            return explicit

        for key in ("VERTEX_AI_ACCESS_TOKEN", "GOOGLE_CLOUD_ACCESS_TOKEN"):
            value = _string_value(os.environ.get(key))
            if value:
                return value

        try:
            result = subprocess.run(
                ["gcloud", "auth", "print-access-token"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except FileNotFoundError as exc:
            raise ValueError("Vertex AI auth is not configured. Provide an access token or install gcloud.") from exc

        token = result.stdout.strip()
        if result.returncode != 0 or not token:
            detail = result.stderr.strip() or result.stdout.strip() or "unknown gcloud error"
            raise ValueError(f"Unable to fetch a Vertex AI access token via gcloud: {detail}")
        return token

    def _gemini_cli_completion(self, messages: list[dict], response_schema: bool = False) -> str:
        prompt = self._cli_prompt(messages, response_schema=response_schema)
        command_text = _string_value(self.ai_config.get("gemini_cli_command")) or os.environ.get("DEVHUB_GEMINI_CLI_COMMAND", "gemini")
        env = os.environ.copy()

        api_key = self._resolve_api_key()
        if api_key:
            env["GEMINI_API_KEY"] = api_key

        command = []
        temp_prompt_path = None
        try:
            if "{" in command_text and "}" in command_text:
                with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".txt") as handle:
                    handle.write(prompt)
                    temp_prompt_path = handle.name
                formatted = command_text.format(
                    model=self.model,
                    prompt=prompt.replace('"', '\\"'),
                    prompt_file=temp_prompt_path,
                )
                command = shlex.split(formatted, posix=False)
            else:
                command = shlex.split(command_text, posix=False) or ["gemini"]
                if "-m" not in command and "--model" not in command:
                    command.extend(["-m", self.model])
                if "-p" not in command and "--prompt" not in command:
                    command.extend(["-p", prompt])

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=240,
                check=False,
                env=env,
            )
        except FileNotFoundError as exc:
            raise ValueError("Gemini CLI is not installed or not available on PATH.") from exc
        finally:
            if temp_prompt_path and os.path.exists(temp_prompt_path):
                try:
                    os.remove(temp_prompt_path)
                except OSError:
                    pass

        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "unknown Gemini CLI error"
            raise ValueError(f"Gemini CLI request failed: {detail}")

        return result.stdout.strip()

    def _gemini_payload(self, messages: list[dict]) -> tuple[str, list[dict]]:
        system_text = "\n\n".join(str(msg.get("content") or "") for msg in messages if msg.get("role") == "system").strip()
        contents = []
        for msg in messages:
            role = msg.get("role")
            if role == "system":
                continue
            contents.append(
                {
                    "role": "model" if role == "assistant" else "user",
                    "parts": [{"text": str(msg.get("content") or "")}],
                }
            )
        return system_text, contents

    def _gemini_text_from_response(self, response: dict) -> str:
        texts = []
        for candidate in response.get("candidates", []):
            content = candidate.get("content") or {}
            for part in content.get("parts", []):
                text = part.get("text")
                if text:
                    texts.append(text)
        return "\n".join(texts).strip()

    def _cli_prompt(self, messages: list[dict], response_schema: bool = False) -> str:
        lines = []
        system_chunks = [str(msg.get("content") or "") for msg in messages if msg.get("role") == "system"]
        if system_chunks:
            lines.append("System instruction:")
            lines.append("\n\n".join(system_chunks).strip())

        for msg in messages:
            role = msg.get("role")
            if role == "system":
                continue
            label = "Assistant" if role == "assistant" else "User"
            lines.append(f"{label}:")
            lines.append(str(msg.get("content") or ""))

        if response_schema:
            lines.append("Return only valid JSON.")

        return "\n\n".join(line for line in lines if line).strip()

    def _http_json(self, url: str, headers: dict | None = None, payload: dict | None = None) -> dict:
        data = json.dumps(payload or {}).encode("utf-8")
        request = Request(url, data=data, headers=headers or {}, method="POST")

        try:
            with urlopen(request, timeout=240) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ValueError(f"{self.ai_config['provider']} request failed ({exc.code}): {body}") from exc
        except URLError as exc:
            raise ValueError(f"{self.ai_config['provider']} request failed: {exc.reason}") from exc

    def parse_json(self, response_text: str) -> dict:
        if not response_text:
            return {}

        text = response_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            inner = []
            skip_first = True
            for line in lines:
                if skip_first and line.startswith("```"):
                    skip_first = False
                    continue
                if line.strip() == "```":
                    break
                inner.append(line)
            text = "\n".join(inner)

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse JSON response: {exc}\nRaw text: {text}")
