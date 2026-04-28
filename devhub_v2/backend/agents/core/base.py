import copy
import json
import os
import random
import shlex
import shutil
import socket
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from openai import OpenAI


SUPPORTED_PROVIDERS = {"openai", "claude", "gemini", "openrouter"}
SUPPORTED_GEMINI_MODES = {"api_key", "gemini_cli", "vertexai"}
DEFAULT_GEMINI_MODEL = "gemini-3.1-pro-preview"
DEFAULT_VERTEX_PROJECT = "noted-computing-459609-n2"
DEFAULT_VERTEX_LOCATION = "global"
DEFAULT_HTTP_TIMEOUT_SECONDS = 240
DEFAULT_HTTP_MAX_RETRIES = 3
MAX_HTTP_BACKOFF_SECONDS = 12.0
RETRYABLE_HTTP_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


def default_model_for_provider(provider: str, gemini_mode: str = "api_key") -> str:
    provider = (provider or "openai").strip().lower()
    gemini_mode = (gemini_mode or "api_key").strip().lower()

    if provider == "claude":
        return os.environ.get("DEVHUB_CLAUDE_MODEL", "claude-3-5-sonnet-latest")
    if provider == "gemini":
        if gemini_mode == "vertexai":
            return os.environ.get("DEVHUB_VERTEX_MODEL", DEFAULT_GEMINI_MODEL)
        return os.environ.get("DEVHUB_GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    if provider == "openrouter":
        return os.environ.get("DEVHUB_OPENROUTER_MODEL", "openai/gpt-4o-mini")
    return os.environ.get("DEVHUB_OPENAI_MODEL", os.environ.get("DEVHUB_MODEL", "gpt-4o-mini"))


def default_ai_config() -> dict:
    default_provider = _string_value(os.environ.get("DEVHUB_DEFAULT_PROVIDER") or "gemini").lower() or "gemini"
    if default_provider not in SUPPORTED_PROVIDERS:
        default_provider = "gemini"
    default_gemini_mode = _string_value(os.environ.get("DEVHUB_GEMINI_MODE") or "vertexai").lower() or "vertexai"
    if default_gemini_mode not in SUPPORTED_GEMINI_MODES:
        default_gemini_mode = "vertexai"
    return {
        "provider": default_provider,
        "model": default_model_for_provider(default_provider, default_gemini_mode),
        "api_key": "",
        "base_url": "",
        "gemini_mode": default_gemini_mode,
        "gemini_cli_command": os.environ.get("DEVHUB_GEMINI_CLI_COMMAND", "gemini"),
        "vertex_project": os.environ.get("VERTEX_PROJECT_ID", os.environ.get("GOOGLE_CLOUD_PROJECT", DEFAULT_VERTEX_PROJECT)),
        "vertex_location": os.environ.get("DEVHUB_VERTEX_LOCATION", os.environ.get("GOOGLE_CLOUD_LOCATION", DEFAULT_VERTEX_LOCATION)),
        "vertex_access_token": "",
        "fallback_model": os.environ.get("DEVHUB_GEMINI_FALLBACK_MODEL", ""),
        "request_timeout_seconds": DEFAULT_HTTP_TIMEOUT_SECONDS,
        "max_retries": DEFAULT_HTTP_MAX_RETRIES,
    }


def _string_value(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _int_value(value, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return default


class AIRequestError(ValueError):
    """Provider request failure with retryability metadata."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        retriable: bool = False,
        status_code: int | None = None,
        body: str = "",
        reason: str = "",
        url: str = "",
    ):
        super().__init__(message)
        self.provider = provider
        self.retriable = retriable
        self.status_code = status_code
        self.body = body
        self.reason = reason
        self.url = url


def _parse_data_url_image(data_url: str) -> tuple[str, str]:
    value = _string_value(data_url)
    if not value.startswith("data:") or ";base64," not in value:
        return "", ""
    header, encoded = value.split(",", 1)
    mime_type = _string_value(header[5:].replace(";base64", "")).lower()
    encoded = "".join(encoded.split())
    if not mime_type or not encoded:
        return "", ""
    return mime_type, encoded


def _normalize_image_attachment(attachment: dict | None) -> dict | None:
    if not isinstance(attachment, dict):
        return None

    mime_type = _string_value(attachment.get("mime_type") or attachment.get("mimeType")).lower()
    data_url = _string_value(attachment.get("data_url") or attachment.get("dataUrl"))
    base64_data = _string_value(attachment.get("base64_data") or attachment.get("base64Data"))

    if data_url:
        parsed_mime, parsed_data = _parse_data_url_image(data_url)
        if parsed_mime:
            mime_type = parsed_mime
        if parsed_data:
            base64_data = parsed_data

    if not mime_type and base64_data:
        mime_type = _string_value(attachment.get("media_type") or attachment.get("mediaType")).lower()

    if not mime_type or not base64_data:
        return None

    return {
        "type": "image",
        "name": _string_value(attachment.get("name")) or "image",
        "mime_type": mime_type,
        "base64_data": base64_data,
        "data_url": data_url or f"data:{mime_type};base64,{base64_data}",
        "size_bytes": attachment.get("size_bytes") or attachment.get("sizeBytes"),
    }


def _message_content_blocks(content) -> list[dict]:
    if isinstance(content, list):
        blocks: list[dict] = []
        for part in content:
            if not isinstance(part, dict):
                text = _string_value(part)
                if text:
                    blocks.append({"type": "text", "text": text})
                continue

            part_type = _string_value(part.get("type")).lower()
            if part_type == "text":
                text = _string_value(part.get("text"))
                if text:
                    blocks.append({"type": "text", "text": text})
                continue

            image_block = _normalize_image_attachment(part)
            if image_block:
                blocks.append(image_block)
        return blocks

    text = _string_value(content)
    return [{"type": "text", "text": text}] if text else []


def _content_text(content, *, include_image_placeholders: bool = False) -> str:
    lines: list[str] = []
    for block in _message_content_blocks(content):
        if block.get("type") == "text":
            text = _string_value(block.get("text"))
            if text:
                lines.append(text)
            continue

        if include_image_placeholders and block.get("type") == "image":
            name = _string_value(block.get("name")) or "image"
            mime_type = _string_value(block.get("mime_type"))
            detail = f" ({mime_type})" if mime_type else ""
            lines.append(f"[Attached image: {name}{detail}]")
    return "\n".join(line for line in lines if line).strip()


def _gemini_tools_to_openai(tools_payload: list[dict]) -> list[dict]:
    """Convert Gemini [{"functionDeclarations": [...]}] to OpenAI [{"type": "function", "function": {...}}]."""
    result = []
    for group in tools_payload:
        for decl in group.get("functionDeclarations", []):
            result.append({"type": "function", "function": {
                "name": decl["name"],
                "description": decl.get("description", ""),
                "parameters": decl.get("parameters", {"type": "object", "properties": {}}),
            }})
    return result


def _serialize_messages_openai_tools(messages: list[dict]) -> list[dict]:
    """Convert internal message format to OpenAI format, handling tool calls/results."""
    result = []
    # First pass: collect tool call IDs indexed by (message_index, call_index)
    call_id_map: dict[tuple[int, int], str] = {}
    for i, msg in enumerate(messages):
        for j, tc in enumerate(msg.get("tool_calls", [])):
            call_id_map[(i, j)] = tc.get("_openai_id") or f"call_{i}_{j}"

    # Second pass: serialize with tool call/result awareness
    # We need to find which model message precedes each tool_results message
    model_msg_indices = []
    for i, msg in enumerate(messages):
        role = msg.get("role", "user")
        if role == "model" and msg.get("tool_calls"):
            model_msg_indices.append(i)

    for i, msg in enumerate(messages):
        role = msg.get("role", "user")
        if role == "model":
            role = "assistant"

        tool_calls = msg.get("tool_calls")
        tool_results = msg.get("tool_results")

        if tool_calls:
            openai_tcs = []
            for j, tc in enumerate(tool_calls):
                cid = call_id_map.get((i, j), f"call_{i}_{j}")
                openai_tcs.append({"id": cid, "type": "function", "function": {
                    "name": tc["name"],
                    "arguments": json.dumps(tc.get("args", {})),
                }})
            result.append({"role": role, "content": msg.get("content") or None, "tool_calls": openai_tcs})
        elif tool_results:
            # Find the preceding model message to get its call IDs
            preceding_model_idx = next((m for m in reversed(model_msg_indices) if m < i), None)
            for j, tr in enumerate(tool_results):
                cid = call_id_map.get((preceding_model_idx, j), f"call_{preceding_model_idx}_{j}") if preceding_model_idx is not None else f"call_unknown_{j}"
                result.append({"role": "tool", "tool_call_id": cid, "content": tr.get("output", "")})
        elif role == "system":
            result.append({"role": "system", "content": _content_text(msg.get("content"))})
        else:
            blocks = _message_content_blocks(msg.get("content"))
            if not blocks:
                result.append({"role": role, "content": ""})
            elif len(blocks) == 1 and blocks[0].get("type") == "text":
                result.append({"role": role, "content": blocks[0].get("text") or ""})
            else:
                content = []
                for block in blocks:
                    if block.get("type") == "text":
                        content.append({"type": "text", "text": block.get("text") or ""})
                    elif block.get("type") == "image":
                        content.append({"type": "image_url", "image_url": {"url": block.get("data_url") or ""}})
                result.append({"role": role, "content": content})
    return result


def _serialize_messages_claude_tools(messages: list[dict]) -> list[dict]:
    """Convert internal message format to Anthropic format, handling tool calls/results."""
    result = []
    model_msg_indices = []
    call_id_map: dict[tuple[int, int], str] = {}
    for i, msg in enumerate(messages):
        if msg.get("role") == "model" and msg.get("tool_calls"):
            model_msg_indices.append(i)
            for j, tc in enumerate(msg["tool_calls"]):
                call_id_map[(i, j)] = tc.get("_claude_id") or f"toolu_{i}_{j}"

    for i, msg in enumerate(messages):
        role = msg.get("role", "user")
        if role == "system":
            continue
        anthropic_role = "assistant" if role in {"assistant", "model"} else "user"
        tool_calls = msg.get("tool_calls")
        tool_results = msg.get("tool_results")

        if tool_calls:
            content = []
            if msg.get("content"):
                content.append({"type": "text", "text": _content_text(msg.get("content"))})
            for j, tc in enumerate(tool_calls):
                cid = call_id_map.get((i, j), f"toolu_{i}_{j}")
                content.append({"type": "tool_use", "id": cid, "name": tc["name"], "input": tc.get("args", {})})
            result.append({"role": "assistant", "content": content})
        elif tool_results:
            preceding_model_idx = next((m for m in reversed(model_msg_indices) if m < i), None)
            content = []
            for j, tr in enumerate(tool_results):
                cid = call_id_map.get((preceding_model_idx, j), f"toolu_{preceding_model_idx}_{j}") if preceding_model_idx is not None else f"toolu_unknown_{j}"
                content.append({"type": "tool_result", "tool_use_id": cid, "content": tr.get("output", "")})
            result.append({"role": "user", "content": content})
        else:
            result.append({"role": anthropic_role, "content": _content_text(msg.get("content")) or "No prompt provided."})
    return result or [{"role": "user", "content": "No prompt provided."}]


def describe_image_attachments(attachments: list[dict] | None) -> str:
    normalized = [_normalize_image_attachment(item) for item in list(attachments or [])]
    images = [item for item in normalized if item]
    if not images:
        return ""

    lines = ["Attached image context:"]
    for image in images:
        detail_parts = []
        mime_type = _string_value(image.get("mime_type"))
        if mime_type:
            detail_parts.append(mime_type)
        size_bytes = image.get("size_bytes")
        if isinstance(size_bytes, int) and size_bytes > 0:
            detail_parts.append(f"{size_bytes} bytes")
        detail = f" ({', '.join(detail_parts)})" if detail_parts else ""
        lines.append(f"- {_string_value(image.get('name')) or 'image'}{detail}")
    return "\n".join(lines)


def build_multimodal_message_content(text: str, attachments: list[dict] | None = None):
    attachment_blocks = []
    for attachment in list(attachments or []):
        image_block = _normalize_image_attachment(attachment)
        if image_block:
            attachment_blocks.append(image_block)

    prompt_text = _string_value(text)
    if not attachment_blocks:
        return prompt_text

    blocks: list[dict] = []
    if prompt_text:
        blocks.append({"type": "text", "text": prompt_text})
    blocks.extend(attachment_blocks)
    return blocks


def _gemini_cli_command_available(command_text: str) -> bool:
    command_text = _string_value(command_text)
    if not command_text:
        return False
    try:
        parts = shlex.split(command_text, posix=False)
    except ValueError:
        return False
    if not parts:
        return False
    return shutil.which(parts[0]) is not None


def _resolve_gcloud_executable() -> str:
    candidates = ["gcloud", "gcloud.cmd", "gcloud.exe"] if os.name == "nt" else ["gcloud"]
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise ValueError("Vertex AI auth is not configured. Provide an access token or install gcloud.")


def _vertexai_base_url_for_location(location: str, api_version: str = "v1") -> str:
    normalized_location = _string_value(location).lower()
    if normalized_location == "global":
        return f"https://aiplatform.googleapis.com/{api_version}"
    host_prefix = normalized_location or DEFAULT_VERTEX_LOCATION
    return f"https://{host_prefix}-aiplatform.googleapis.com/{api_version}"


def normalize_ai_config(config: dict | None) -> dict:
    normalized = default_ai_config()
    raw = config if isinstance(config, dict) else {}

    normalized["provider"] = _string_value(raw.get("provider") or normalized["provider"]).lower() or "openai"
    if normalized["provider"] not in SUPPORTED_PROVIDERS:
        normalized["provider"] = "openai"

    normalized["gemini_mode"] = _string_value(raw.get("gemini_mode") or normalized["gemini_mode"]).lower() or "api_key"
    if normalized["gemini_mode"] not in SUPPORTED_GEMINI_MODES:
        normalized["gemini_mode"] = "api_key"

    for key in (
        "model",
        "api_key",
        "base_url",
        "gemini_cli_command",
        "vertex_project",
        "vertex_location",
        "vertex_access_token",
        "fallback_model",
    ):
        normalized[key] = _string_value(raw.get(key) or normalized.get(key))
    normalized["request_timeout_seconds"] = max(
        30,
        _int_value(raw.get("request_timeout_seconds"), _int_value(normalized.get("request_timeout_seconds"), DEFAULT_HTTP_TIMEOUT_SECONDS)),
    )
    normalized["max_retries"] = max(
        0,
        _int_value(raw.get("max_retries"), _int_value(normalized.get("max_retries"), DEFAULT_HTTP_MAX_RETRIES)),
    )

    if normalized["provider"] == "gemini":
        if normalized["model"] in {"", "gemini-2.5-pro"}:
            normalized["model"] = DEFAULT_GEMINI_MODEL

        raw_vertex_project = _string_value(raw.get("vertex_project"))
        if not normalized["vertex_project"]:
            normalized["vertex_project"] = os.environ.get("VERTEX_PROJECT_ID", os.environ.get("GOOGLE_CLOUD_PROJECT", DEFAULT_VERTEX_PROJECT))
        elif normalized["vertex_project"] == DEFAULT_VERTEX_PROJECT and not raw_vertex_project:
            normalized["vertex_project"] = DEFAULT_VERTEX_PROJECT

        raw_vertex_location = _string_value(raw.get("vertex_location")).lower()
        if not normalized["vertex_location"] or raw_vertex_location in {"", "us-central1"}:
            normalized["vertex_location"] = DEFAULT_VERTEX_LOCATION

        if normalized["gemini_mode"] == "gemini_cli" and not _gemini_cli_command_available(normalized.get("gemini_cli_command") or "gemini"):
            normalized["gemini_mode"] = "vertexai"

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


def ai_config_is_usable(config: dict | None = None) -> bool:
    normalized = normalize_ai_config(config)
    provider = normalized.get("provider") or "openai"
    gemini_mode = normalized.get("gemini_mode") or "api_key"

    if provider == "gemini":
        if gemini_mode == "vertexai":
            return bool(
                _string_value(normalized.get("vertex_project"))
                or _string_value(os.environ.get("VERTEX_PROJECT_ID"))
                or _string_value(os.environ.get("GOOGLE_CLOUD_PROJECT"))
            )
        if gemini_mode == "gemini_cli":
            command_text = _string_value(normalized.get("gemini_cli_command")) or os.environ.get("DEVHUB_GEMINI_CLI_COMMAND") or "gemini"
            if _gemini_cli_command_available(command_text):
                return True
            return bool(
                _string_value(normalized.get("vertex_project"))
                or _string_value(os.environ.get("VERTEX_PROJECT_ID"))
                or _string_value(os.environ.get("GOOGLE_CLOUD_PROJECT"))
            )
        return bool(
            _string_value(normalized.get("api_key"))
            or _string_value(os.environ.get("GEMINI_API_KEY"))
            or _string_value(os.environ.get("GOOGLE_API_KEY"))
            or _string_value(os.environ.get("DEVHUB_GEMINI_API_KEY"))
            or _string_value(os.environ.get("DEVHUB_API_KEY"))
        )

    provider_keys = {
        "openai": ("OPENAI_API_KEY", "DEVHUB_API_KEY"),
        "openrouter": ("OPENROUTER_API_KEY", "DEVHUB_OPENROUTER_API_KEY", "DEVHUB_API_KEY"),
        "claude": ("ANTHROPIC_API_KEY", "DEVHUB_ANTHROPIC_API_KEY", "DEVHUB_API_KEY"),
    }
    if _string_value(normalized.get("api_key")):
        return True
    return any(_string_value(os.environ.get(key)) for key in provider_keys.get(provider, ()))


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

    def generate_with_attachments(self, prompt: str, attachments: list[dict] | None = None, tools=None, response_schema=None) -> str:
        messages = [
            {"role": "system", "content": self.system_instruction},
            {"role": "user", "content": build_multimodal_message_content(prompt, attachments)},
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
        serialized_messages = [self._openai_message(message) for message in messages]
        kwargs = {
            "model": self.model,
            "messages": serialized_messages,
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

        system_text = "\n\n".join(_content_text(msg.get("content")) for msg in messages if msg.get("role") == "system").strip()
        anthropic_messages = []
        for msg in messages:
            role = msg.get("role")
            if role == "system":
                continue
            content_blocks = self._claude_content(msg.get("content"))
            anthropic_messages.append(
                {
                    "role": "assistant" if role in {"assistant", "model"} else "user",
                    "content": content_blocks or [{"type": "text", "text": "No prompt provided."}],
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
        try:
            if gemini_mode == "gemini_cli":
                try:
                    return self._gemini_cli_completion(messages, response_schema=response_schema)
                except ValueError as exc:
                    if "not installed" not in str(exc).lower():
                        raise
                    fallback_config = dict(self.ai_config)
                    fallback_config["gemini_mode"] = "vertexai"
                    fallback_agent = BaseAgent(
                        role=self.role,
                        system_instruction=self.system_instruction,
                        model=self.model,
                        ai_config=fallback_config,
                    )
                    return fallback_agent._vertexai_completion(messages, response_schema=response_schema)
            if gemini_mode == "vertexai":
                return self._vertexai_completion(messages, response_schema=response_schema)
            return self._gemini_api_completion(messages, response_schema=response_schema)
        except AIRequestError as exc:
            fallback_model = self._gemini_fallback_model()
            if not self._should_try_gemini_fallback(exc, fallback_model):
                raise
            original_model = self.model
            self.model = fallback_model
            self.ai_config["model"] = fallback_model
            try:
                if gemini_mode == "vertexai":
                    return self._vertexai_completion(messages, response_schema=response_schema)
                if gemini_mode == "api_key":
                    return self._gemini_api_completion(messages, response_schema=response_schema)
                raise
            finally:
                self.model = original_model
                self.ai_config["model"] = original_model

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
        project = self.ai_config.get("vertex_project") or os.environ.get("VERTEX_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT") or DEFAULT_VERTEX_PROJECT
        location = self.ai_config.get("vertex_location") or os.environ.get("DEVHUB_VERTEX_LOCATION") or os.environ.get("GOOGLE_CLOUD_LOCATION") or DEFAULT_VERTEX_LOCATION
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
            base_url = _vertexai_base_url_for_location(location, api_version="v1")

        url = f"{base_url}/projects/{quote(project)}/locations/{quote(location)}/publishers/google/models/{quote(self.model)}:generateContent"
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {access_token}",
        }
        try:
            response = self._http_json(url, headers=headers, payload=payload)
        except AIRequestError as exc:
            if exc.status_code not in {401, 403} or self.ai_config.get("vertex_access_token"):
                raise
            refreshed_headers = dict(headers)
            refreshed_headers["authorization"] = f"Bearer {self._resolve_vertex_access_token(force_refresh=True)}"
            response = self._http_json(url, headers=refreshed_headers, payload=payload)
        return self._gemini_text_from_response(response)

    def _resolve_vertex_access_token(self, force_refresh: bool = False) -> str:
        explicit = _string_value(self.ai_config.get("vertex_access_token"))
        if explicit and not force_refresh:
            return explicit

        for key in ("VERTEX_AI_ACCESS_TOKEN", "GOOGLE_CLOUD_ACCESS_TOKEN"):
            value = _string_value(os.environ.get(key))
            if value and not force_refresh:
                return value

        try:
            gcloud_executable = _resolve_gcloud_executable()
            result = subprocess.run(
                [gcloud_executable, "auth", "print-access-token"],
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
        env.pop("DJANGO_SETTINGS_MODULE", None)

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
        system_text = "\n\n".join(_content_text(msg.get("content")) for msg in messages if msg.get("role") == "system").strip()
        contents = []
        for msg in messages:
            role = msg.get("role")
            if role == "system":
                continue
            parts = self._gemini_parts(msg.get("content"))
            if not parts:
                continue
            contents.append(
                {
                    "role": "model" if role in {"assistant", "model"} else "user",
                    "parts": parts,
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

    # ------------------------------------------------------------------
    # Tool-calling support (Gemini function-calling)
    # ------------------------------------------------------------------

    def complete_with_tools(self, messages: list[dict], tools_payload: list[dict]) -> dict:
        """
        Send messages with function declarations.

        Args:
            messages: Conversation in the internal format (role: system/user/model,
                      content: str, tool_calls: [...], tool_results: [...]).
            tools_payload: Gemini tools list, e.g. [{"functionDeclarations": [...]}].

        Returns:
            dict with:
                "text": str — text response (may be empty if tool calls are returned)
                "tool_calls": list[dict] — each has "name" and "args"
                "raw": dict — the raw API response
        """
        provider = self.ai_config.get("provider", "gemini")
        if provider in {"openai", "openrouter"}:
            return self._openai_tool_completion(messages, tools_payload)
        if provider == "claude":
            return self._claude_tool_completion(messages, tools_payload)
        gemini_mode = self.ai_config.get("gemini_mode", "api_key")
        if gemini_mode == "vertexai":
            return self._vertexai_tool_completion(messages, tools_payload)
        return self._gemini_api_tool_completion(messages, tools_payload)

    def _openai_tool_completion(self, messages: list[dict], tools_payload: list[dict]) -> dict:
        openai_tools = _gemini_tools_to_openai(tools_payload)
        serialized = _serialize_messages_openai_tools(messages)
        response = self._openai_client().chat.completions.create(
            model=self.model,
            messages=serialized,
            tools=openai_tools,
            tool_choice="auto",
            temperature=0.2,
        )
        msg = response.choices[0].message
        text = msg.content or ""
        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    args = {}
                tool_calls.append({"name": tc.function.name, "args": args, "_openai_id": tc.id})
        return {"text": text, "tool_calls": tool_calls, "raw": response}

    def _claude_tool_completion(self, messages: list[dict], tools_payload: list[dict]) -> dict:
        api_key = self._resolve_api_key()
        if not api_key:
            raise ValueError("No API key configured for Claude.")
        openai_tools = _gemini_tools_to_openai(tools_payload)
        claude_tools = [
            {"name": t["function"]["name"], "description": t["function"].get("description", ""), "input_schema": t["function"].get("parameters", {})}
            for t in openai_tools
        ]
        system_text = "\n\n".join(_content_text(m.get("content")) for m in messages if m.get("role") == "system").strip()
        anthropic_messages = _serialize_messages_claude_tools(messages)
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "temperature": 0.2,
            "messages": anthropic_messages,
            "tools": claude_tools,
        }
        if system_text:
            payload["system"] = system_text
        raw = self._http_json(self._resolve_base_url() or "https://api.anthropic.com/v1/messages", headers={"content-type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"}, payload=payload)
        text = ""
        tool_calls = []
        for block in raw.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append({"name": block["name"], "args": block.get("input", {}), "_claude_id": block["id"]})
        return {"text": text, "tool_calls": tool_calls, "raw": raw}

    def _build_gemini_tool_messages(self, messages: list[dict]) -> tuple[str, list[dict]]:
        """
        Convert internal message format to Gemini ``contents`` format,
        handling tool_call and tool_result parts properly.
        """
        system_parts: list[str] = []
        contents: list[dict] = []

        for msg in messages:
            role = msg.get("role", "user")

            if role == "system":
                system_parts.append(_content_text(msg.get("content")))
                continue

            gemini_role = "model" if role in ("assistant", "model") else "user"
            raw_parts = msg.get("gemini_parts")
            if gemini_role == "model" and isinstance(raw_parts, list) and raw_parts:
                contents.append({"role": gemini_role, "parts": copy.deepcopy(raw_parts)})
                continue

            parts: list[dict] = list(self._gemini_parts(msg.get("content")))

            # Tool calls (model asking to call functions)
            for tc in msg.get("tool_calls", []):
                raw_part = tc.get("raw_part")
                if isinstance(raw_part, dict) and raw_part.get("functionCall"):
                    parts.append(copy.deepcopy(raw_part))
                    continue

                function_part = {
                    "functionCall": {
                        "name": tc.get("name", ""),
                        "args": tc.get("args", {}),
                    }
                }
                thought_signature = tc.get("thought_signature")
                if thought_signature:
                    function_part["thoughtSignature"] = thought_signature
                parts.append(function_part)

            # Tool results (user feeding back function results)
            for tr in msg.get("tool_results", []):
                parts.append({
                    "functionResponse": {
                        "name": tr.get("name", ""),
                        "response": {"result": tr.get("output", "")},
                    }
                })

            if parts:
                contents.append({"role": gemini_role, "parts": parts})

        system_text = "\n\n".join(s for s in system_parts if s).strip()
        return system_text, contents

    def _gemini_api_tool_completion(self, messages: list[dict], tools_payload: list[dict]) -> dict:
        """Gemini API (api_key mode) with function calling."""
        api_key = self._resolve_api_key()
        if not api_key:
            raise ValueError("No API key configured for Gemini.")

        system_text, contents = self._build_gemini_tool_messages(messages)
        payload: dict = {
            "contents": contents or [{"role": "user", "parts": [{"text": "No prompt provided."}]}],
            "generationConfig": {"temperature": 0.2},
        }
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        if tools_payload:
            payload["tools"] = tools_payload

        base_url = self._resolve_base_url().rstrip("/")
        url = f"{base_url}/models/{quote(self.model)}:generateContent?key={quote(api_key)}"
        response = self._http_json(url, payload=payload)
        return self._parse_gemini_tool_response(response)

    def _vertexai_tool_completion(self, messages: list[dict], tools_payload: list[dict]) -> dict:
        """Vertex AI with function calling."""
        project = self.ai_config.get("vertex_project") or os.environ.get("VERTEX_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT") or DEFAULT_VERTEX_PROJECT
        location = self.ai_config.get("vertex_location") or os.environ.get("DEVHUB_VERTEX_LOCATION") or os.environ.get("GOOGLE_CLOUD_LOCATION") or DEFAULT_VERTEX_LOCATION
        if not project:
            raise ValueError("Vertex AI requires a Google Cloud project ID.")

        access_token = self._resolve_vertex_access_token()
        system_text, contents = self._build_gemini_tool_messages(messages)
        payload: dict = {
            "contents": contents or [{"role": "user", "parts": [{"text": "No prompt provided."}]}],
            "generationConfig": {"temperature": 0.2},
        }
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        if tools_payload:
            payload["tools"] = tools_payload

        custom_base = _string_value(self.ai_config.get("base_url"))
        if custom_base:
            base_url = custom_base.rstrip("/")
        else:
            base_url = _vertexai_base_url_for_location(location, api_version="v1")

        url = f"{base_url}/projects/{quote(project)}/locations/{quote(location)}/publishers/google/models/{quote(self.model)}:generateContent"
        response = self._http_json(
            url,
            headers={
                "content-type": "application/json",
                "authorization": f"Bearer {access_token}",
            },
            payload=payload,
        )
        return self._parse_gemini_tool_response(response)

    def _parse_gemini_tool_response(self, response: dict) -> dict:
        """
        Parse a Gemini generateContent response that may contain
        text parts and/or functionCall parts.
        """
        texts: list[str] = []
        tool_calls: list[dict] = []
        model_parts: list[dict] = []

        for candidate in response.get("candidates", []):
            content = candidate.get("content") or {}
            parts = content.get("parts") or []
            if not model_parts and isinstance(parts, list) and parts:
                model_parts = copy.deepcopy(parts)
            for part in parts:
                if "text" in part:
                    texts.append(part["text"])
                if "functionCall" in part:
                    fc = part["functionCall"]
                    tool_call = {
                        "name": fc.get("name", ""),
                        "args": fc.get("args", {}),
                        "raw_part": copy.deepcopy(part),
                    }
                    thought_signature = part.get("thoughtSignature") or part.get("thought_signature")
                    if thought_signature:
                        tool_call["thought_signature"] = thought_signature
                    tool_calls.append(tool_call)

        return {
            "text": "\n".join(texts).strip(),
            "tool_calls": tool_calls,
            "model_parts": model_parts,
            "raw": response,
        }

    def _cli_prompt(self, messages: list[dict], response_schema: bool = False) -> str:
        lines = []
        system_chunks = [_content_text(msg.get("content"), include_image_placeholders=True) for msg in messages if msg.get("role") == "system"]
        if system_chunks:
            lines.append("System instruction:")
            lines.append("\n\n".join(system_chunks).strip())

        for msg in messages:
            role = msg.get("role")
            if role == "system":
                continue
            label = "Assistant" if role in {"assistant", "model"} else "User"
            lines.append(f"{label}:")
            lines.append(_content_text(msg.get("content"), include_image_placeholders=True))

        if response_schema:
            lines.append("Return only valid JSON.")

        return "\n\n".join(line for line in lines if line).strip()

    def _openai_message(self, message: dict) -> dict:
        role = _string_value(message.get("role")) or "user"
        if role == "model":
            role = "assistant"

        if role == "system":
            return {"role": role, "content": _content_text(message.get("content"))}

        blocks = _message_content_blocks(message.get("content"))
        if not blocks:
            return {"role": role, "content": ""}
        if len(blocks) == 1 and blocks[0].get("type") == "text":
            return {"role": role, "content": blocks[0].get("text") or ""}

        content = []
        for block in blocks:
            if block.get("type") == "text":
                content.append({"type": "text", "text": block.get("text") or ""})
            elif block.get("type") == "image":
                content.append({"type": "image_url", "image_url": {"url": block.get("data_url") or ""}})
        return {"role": role, "content": content}

    def _claude_content(self, content) -> list[dict]:
        blocks = []
        for block in _message_content_blocks(content):
            if block.get("type") == "text":
                blocks.append({"type": "text", "text": block.get("text") or ""})
            elif block.get("type") == "image":
                blocks.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": block.get("mime_type") or "image/png",
                            "data": block.get("base64_data") or "",
                        },
                    }
                )
        return blocks

    def _gemini_parts(self, content) -> list[dict]:
        parts = []
        for block in _message_content_blocks(content):
            if block.get("type") == "text":
                parts.append({"text": block.get("text") or ""})
            elif block.get("type") == "image":
                parts.append(
                    {
                        "inlineData": {
                            "mimeType": block.get("mime_type") or "image/png",
                            "data": block.get("base64_data") or "",
                        }
                    }
                )
        return parts

    def _request_timeout_seconds(self) -> int:
        return max(30, _int_value(self.ai_config.get("request_timeout_seconds"), DEFAULT_HTTP_TIMEOUT_SECONDS))

    def _max_request_retries(self) -> int:
        return max(0, _int_value(self.ai_config.get("max_retries"), DEFAULT_HTTP_MAX_RETRIES))

    def _retry_delay_seconds(self, attempt_index: int, retry_after: str = "") -> float:
        retry_after_seconds = _int_value(retry_after, 0)
        if retry_after_seconds > 0:
            return float(min(retry_after_seconds, int(MAX_HTTP_BACKOFF_SECONDS)))
        base_delay = min(MAX_HTTP_BACKOFF_SECONDS, 2 ** attempt_index)
        jitter = random.uniform(0.0, min(1.0, base_delay / 2))
        return min(MAX_HTTP_BACKOFF_SECONDS, base_delay + jitter)

    def _gemini_fallback_model(self) -> str:
        return _string_value(self.ai_config.get("fallback_model") or os.environ.get("DEVHUB_GEMINI_FALLBACK_MODEL"))

    def _should_try_gemini_fallback(self, exc: Exception, fallback_model: str) -> bool:
        return (
            isinstance(exc, AIRequestError)
            and exc.retriable
            and bool(fallback_model)
            and fallback_model != self.model
        )

    def _http_json(self, url: str, headers: dict | None = None, payload: dict | None = None) -> dict:
        data = json.dumps(payload or {}).encode("utf-8")
        request = Request(url, data=data, headers=headers or {}, method="POST")
        timeout_seconds = self._request_timeout_seconds()
        max_retries = self._max_request_retries()
        provider = self.ai_config["provider"]

        for attempt in range(max_retries + 1):
            try:
                with urlopen(request, timeout=timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                retriable = exc.code in RETRYABLE_HTTP_STATUS_CODES
                if retriable and attempt < max_retries:
                    time.sleep(self._retry_delay_seconds(attempt, exc.headers.get("Retry-After", "")))
                    continue
                raise AIRequestError(
                    f"{provider} request failed ({exc.code}): {body}",
                    provider=provider,
                    retriable=retriable,
                    status_code=exc.code,
                    body=body,
                    url=url,
                ) from exc
            except (TimeoutError, socket.timeout) as exc:
                if attempt < max_retries:
                    time.sleep(self._retry_delay_seconds(attempt))
                    continue
                raise AIRequestError(
                    f"{provider} request timed out after {timeout_seconds}s: {exc}",
                    provider=provider,
                    retriable=True,
                    reason=str(exc),
                    url=url,
                ) from exc
            except URLError as exc:
                reason = str(getattr(exc, "reason", exc))
                if attempt < max_retries:
                    time.sleep(self._retry_delay_seconds(attempt))
                    continue
                raise AIRequestError(
                    f"{provider} request failed: {reason}",
                    provider=provider,
                    retriable=True,
                    reason=reason,
                    url=url,
                ) from exc

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
