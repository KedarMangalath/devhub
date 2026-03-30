from __future__ import annotations

import ast
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


HTTP_METHOD_ORDER = ["GET", "POST", "PUT", "PATCH", "DELETE"]
GROUP_ORDER = {
    "Settings": 0,
    "Projects": 1,
    "Imports": 2,
    "Documentation": 3,
    "Work Items": 4,
    "Chat": 5,
    "Agents": 6,
    "Workspace": 7,
    "Other": 99,
}


REFERENCE_OVERRIDES: dict[str, dict[str, Any]] = {}


FIELD_EXAMPLES: dict[str, Any] = {
    "id": "proj_123",
    "project_id": "proj_123",
    "feature_id": "feat_1",
    "workspace_id": "ws_456",
    "process_id": "ws_456_runtime",
    "run_id": "run_789",
    "session_id": "session_abc123",
    "name": "Sample Project",
    "title": "Sample Item",
    "description": "Short description",
    "idea": "Build a sample project",
    "source_type": "starter",
    "status": "ready",
    "local_path": "/path/to/project",
    "github_url": "https://github.com/example/repo",
    "tech_stack": ["React", "Node.js"],
    "command": "npm run dev",
    "content": "Describe the requested change",
    "selected_file": "src/App.tsx",
    "selected_content": "// current file contents",
    "context_mentions": ["@current_file"],
    "apply_changes": False,
    "messages": [{"role": "user", "content": "How do I start?"}],
    "sessions": [{"session_id": "session_abc123", "title": "Getting started"}],
    "active_session_id": "session_abc123",
    "input": "npm run dev\n",
    "path": "src/App.tsx",
    "output": "Server started on port 3000\n",
    "preview_url": "http://127.0.0.1:3000",
    "ready": True,
    "ok": True,
    "success": True,
    "logs": [{"step": "started", "message": "Background work started"}],
    "ai_config": {
        "provider": "provider-name",
        "model": "model-name",
    },
}


def build_api_reference_catalog(workspace_path: Path) -> list[dict[str, Any]]:
    root_urls_path = _find_root_urls_path(workspace_path)
    if not root_urls_path:
        return []

    routes = _collect_django_routes(root_urls_path, workspace_path)
    entries: list[dict[str, Any]] = []
    for route_index, route in enumerate(routes):
        full_path = _normalize_url_path(route.get("path", ""))
        if not full_path.startswith("/api/"):
            continue

        view_file = route.get("view_file_abs")
        view_name = str(route.get("view_name") or "")
        view_info = _load_view_function(view_file, view_name) if view_file and view_name else None
        methods = _extract_allowed_methods(view_info.get("source", "") if view_info else "")
        metadata = REFERENCE_OVERRIDES.get(view_name, {})

        for method in methods:
            entries.append(_build_reference_entry(route, view_info, method, route_index, metadata))

    return sorted(
        entries,
        key=lambda item: (
            GROUP_ORDER.get(str(item.get("group") or "Other"), GROUP_ORDER["Other"]),
            int(item.get("route_order") or 0),
            HTTP_METHOD_ORDER.index(str(item.get("method") or "GET")) if str(item.get("method") or "GET") in HTTP_METHOD_ORDER else len(HTTP_METHOD_ORDER),
            str(item.get("path") or ""),
        ),
    )


def _find_root_urls_path(workspace_path: Path) -> Path | None:
    candidates = [
        workspace_path / "backend" / "devhub_backend" / "urls.py",
        workspace_path / "devhub_backend" / "urls.py",
        workspace_path / "backend" / "urls.py",
        workspace_path / "urls.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    for candidate in workspace_path.rglob("urls.py"):
        try:
            content = candidate.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "include('api.urls')" in content or 'include("api.urls")' in content:
            return candidate
    return None


def _collect_django_routes(file_path: Path, workspace_path: Path, prefix: str = "") -> list[dict[str, Any]]:
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return []

    calls = _extract_urlpattern_calls(tree)
    routes: list[dict[str, Any]] = []
    for index, call in enumerate(calls):
        route_fragment = _literal_str(call.args[0]) if call.args else ""
        handler = call.args[1] if len(call.args) > 1 else None
        route_name = _call_keyword_literal(call, "name")
        combined_path = f"{prefix}{route_fragment}"

        include_module = _extract_include_module(handler)
        if include_module:
            include_file = _resolve_module_to_file(workspace_path, include_module)
            if include_file and include_file != file_path:
                routes.extend(_collect_django_routes(include_file, workspace_path, combined_path))
            continue

        view_name = _extract_view_name(handler)
        if not view_name:
            continue

        view_file = file_path.with_name("views.py")
        if not view_file.exists():
            resolved = _resolve_module_to_file(workspace_path, "views")
            if resolved:
                view_file = resolved

        routes.append(
            {
                "path": combined_path,
                "route_name": route_name or view_name,
                "view_name": view_name,
                "view_file_abs": str(view_file.resolve()) if view_file.exists() else "",
                "view_file": str(view_file.relative_to(workspace_path)).replace("\\", "/") if view_file.exists() else "",
                "url_file": str(file_path.relative_to(workspace_path)).replace("\\", "/"),
                "route_order": index,
            }
        )
    return routes


def _extract_urlpattern_calls(tree: ast.Module) -> list[ast.Call]:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "urlpatterns" and isinstance(node.value, (ast.List, ast.Tuple)):
                    return [item for item in node.value.elts if isinstance(item, ast.Call) and _call_name(item) in {"path", "re_path"}]
    return []


def _call_name(call: ast.Call | None) -> str:
    if not call:
        return ""
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return ""


def _call_keyword_literal(call: ast.Call, name: str) -> str:
    for keyword in call.keywords:
        if keyword.arg == name:
            return _literal_str(keyword.value)
    return ""


def _extract_include_module(node: ast.AST | None) -> str:
    if not isinstance(node, ast.Call) or _call_name(node) != "include" or not node.args:
        return ""
    return _literal_str(node.args[0])


def _extract_view_name(node: ast.AST | None) -> str:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _resolve_module_to_file(workspace_path: Path, module_name: str) -> Path | None:
    module_parts = [part for part in str(module_name or "").split(".") if part]
    if not module_parts:
        return None

    direct_candidates = [
        workspace_path.joinpath(*module_parts).with_suffix(".py"),
        workspace_path / "backend" / Path(*module_parts).with_suffix(".py"),
    ]
    for candidate in direct_candidates:
        if candidate.exists():
            return candidate

    suffix = "/".join(module_parts) + ".py"
    for candidate in workspace_path.rglob(f"{module_parts[-1]}.py"):
        normalized = str(candidate.relative_to(workspace_path)).replace("\\", "/")
        if normalized.endswith(suffix):
            return candidate
    return None


@lru_cache(maxsize=64)
def _load_view_function(view_file_rel: str, function_name: str) -> dict[str, Any]:
    view_file = Path(view_file_rel)
    try:
        source = view_file.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {}

    try:
        tree = ast.parse(source)
    except Exception:
        return {}

    helper_returns = _helper_return_payloads(tree)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            decorators = [_decorator_name(item) for item in node.decorator_list]
            return {
                "source": ast.get_source_segment(source, node) or "",
                "node": node,
                "decorators": decorators,
                "lineno": getattr(node, "lineno", None),
                "end_lineno": getattr(node, "end_lineno", None),
                "helper_returns": helper_returns,
            }
    return {}


def _helper_return_payloads(tree: ast.Module) -> dict[str, Any]:
    payloads: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        payload = _function_return_payload(node)
        if payload is not None:
            payloads[node.name] = payload
    return payloads


def _function_return_payload(node: ast.FunctionDef) -> Any | None:
    for child in ast.walk(node):
        if isinstance(child, ast.Return):
            payload = _literal_payload(child.value)
            if payload is not None:
                return payload
    return None


def _literal_payload(node: ast.AST | None) -> Any | None:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Dict):
        payload: dict[str, Any] = {}
        for key_node, value_node in zip(node.keys, node.values):
            key = _literal_str(key_node)
            if not key:
                return None
            payload_value = _literal_payload(value_node)
            if payload_value is None and not (
                isinstance(value_node, ast.Constant) and value_node.value is None
            ):
                return None
            payload[key] = payload_value
        return payload
    if isinstance(node, ast.List):
        values: list[Any] = []
        for item in node.elts:
            payload_value = _literal_payload(item)
            if payload_value is None and not (
                isinstance(item, ast.Constant) and item.value is None
            ):
                return None
            values.append(payload_value)
        return values
    if isinstance(node, ast.Tuple):
        values: list[Any] = []
        for item in node.elts:
            payload_value = _literal_payload(item)
            if payload_value is None and not (
                isinstance(item, ast.Constant) and item.value is None
            ):
                return None
            values.append(payload_value)
        return values
    return None


def _decorator_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return ""


def _extract_allowed_methods(source: str) -> list[str]:
    methods: list[str] = []
    seen: set[str] = set()

    for match in re.finditer(r"request\.method\s*==\s*['\"]([A-Z]+)['\"]", source):
        method = match.group(1)
        if method not in seen:
            seen.add(method)
            methods.append(method)

    for match in re.finditer(r"request\.method\s*in\s*\{([^}]+)\}", source):
        for token in re.findall(r"['\"]([A-Z]+)['\"]", match.group(1)):
            if token not in seen:
                seen.add(token)
                methods.append(token)

    if methods:
        return methods

    match = re.search(r"request\.method\s*not in\s*\{([^}]+)\}", source)
    if match:
        return [token for token in re.findall(r"['\"]([A-Z]+)['\"]", match.group(1)) if token in HTTP_METHOD_ORDER]

    match = re.search(r"request\.method\s*!=\s*['\"]([A-Z]+)['\"]", source)
    if match:
        return [match.group(1)]

    return ["GET"]


def _build_reference_entry(
    route: dict[str, Any],
    view_info: dict[str, Any] | None,
    method: str,
    route_index: int,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    method_metadata = dict((metadata.get("methods") or {}).get(method) or {})
    source = str((view_info or {}).get("source") or "")
    node = (view_info or {}).get("node")
    helper_returns = (view_info or {}).get("helper_returns") or {}
    path = _normalize_url_path(route.get("path", ""))
    path_params = _path_params(path)
    query_params = method_metadata.get("query_params") or _query_param_objects(node)
    body_fields = _body_field_objects(node)
    response_details = _response_details(node, helper_returns)
    request_body = method_metadata.get("request_body")
    if request_body is None:
        body_field_names = [item.get("name") for item in body_fields if item.get("name")]
        request_body = None if method == "GET" else _placeholder_request_body(body_field_names, str(route.get("view_name") or ""), method)
    body_fields = _merge_field_objects(
        body_fields,
        _payload_field_objects(request_body, description="Included in the example JSON body."),
    )

    response_payload = method_metadata.get("response")
    if response_payload is None:
        response_payload = response_details.get("example_payload")
    if response_payload is None:
        response_payload = _placeholder_response(response_details.get("response_keys") or [])
    response_keys = _merge_key_lists(response_details.get("response_keys") or [], _payload_keys(response_payload))

    summary = str(method_metadata.get("summary") or _generic_summary(str(route.get("view_name") or ""), path, method))
    when_to_use = str(method_metadata.get("when_to_use") or _generic_when_to_use(path, method))
    behavior_notes = list(method_metadata.get("behavior_notes") or _behavior_notes_from_source(source))
    common_errors = list(method_metadata.get("common_errors") or response_details.get("errors") or [])
    status_codes = _merge_status_codes(response_details.get("status_codes") or [], method_metadata.get("status_codes") or [])
    access_text, auth_required = _access_details(view_info or {})
    description_parts = [summary, when_to_use]
    if behavior_notes:
        description_parts.append(" ".join(behavior_notes[:2]))
    description = " ".join(part.strip() for part in description_parts if part).strip()
    group = str(metadata.get("group") or _group_for_path(path))

    entry = {
        "group": group,
        "method": method,
        "path": path,
        "route_name": route.get("route_name") or route.get("view_name"),
        "handler": route.get("view_name"),
        "description": description,
        "summary": summary,
        "when_to_use": when_to_use,
        "behavior_notes": behavior_notes,
        "auth_required": auth_required,
        "access": access_text,
        "path_params": path_params,
        "query_params": query_params,
        "request_fields": body_fields,
        "request_body": request_body,
        "response": response_payload,
        "response_keys": response_keys,
        "common_errors": common_errors,
        "status_codes": status_codes,
        "source": {
            "url_file": route.get("url_file"),
            "view_file": route.get("view_file"),
            "line": (view_info or {}).get("lineno"),
        },
        "route_order": route_index,
    }
    entry["curl_example"] = _curl_example(entry)
    return entry


def _normalize_url_path(path: str) -> str:
    normalized = "/" + str(path or "").strip().lstrip("/")
    normalized = re.sub(r"/{2,}", "/", normalized)
    if not normalized.endswith("/"):
        normalized += "/"
    return normalized


def _literal_str(node: ast.AST | None) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
        return "".join(parts)
    return ""


def _path_params(path: str) -> list[dict[str, Any]]:
    params = []
    for raw in re.findall(r"<([^>]+)>", str(path or "")):
        converter, _, name = raw.partition(":")
        if not name:
            name = converter
            converter = "str"
        params.append(
            {
                "name": name,
                "required": True,
                "description": f"Path parameter captured by Django as `{converter}`.",
            }
        )
    return params


def _query_param_objects(node: ast.AST | None) -> list[dict[str, Any]]:
    params = []
    for name in _request_get_keys(node):
        params.append({"name": name, "required": False, "description": "Read from `request.GET` inside the handler."})
    return params


def _request_get_keys(node: ast.AST | None) -> list[str]:
    if node is None:
        return []
    names: list[str] = []
    seen: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call) or not isinstance(child.func, ast.Attribute) or child.func.attr != "get":
            continue
        value = child.func.value
        if not (
            isinstance(value, ast.Attribute)
            and value.attr == "GET"
            and isinstance(value.value, ast.Name)
            and value.value.id == "request"
        ):
            continue
        key = _literal_str(child.args[0]) if child.args else ""
        if key and key not in seen:
            seen.add(key)
            names.append(key)
    return names


def _body_field_objects(node: ast.AST | None) -> list[dict[str, Any]]:
    body_fields = _body_get_keys(node)
    required = _required_body_fields(node)
    items = []
    for field in body_fields:
        items.append(
            {
                "name": field,
                "required": field in required,
                "description": "Read from the parsed JSON request body.",
            }
        )
    return items


def _body_get_keys(node: ast.AST | None) -> list[str]:
    if node is None:
        return []
    names: list[str] = []
    seen: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call) or not isinstance(child.func, ast.Attribute) or child.func.attr != "get":
            continue
        if not isinstance(child.func.value, ast.Name) or child.func.value.id != "body":
            continue
        key = _literal_str(child.args[0]) if child.args else ""
        if key and key not in seen:
            seen.add(key)
            names.append(key)
    return names


def _required_body_fields(node: ast.AST | None) -> set[str]:
    if node is None:
        return set()
    var_to_field: dict[str, str] = {}
    required: set[str] = set()

    for child in ast.walk(node):
        if isinstance(child, ast.Assign) and len(child.targets) == 1 and isinstance(child.targets[0], ast.Name):
            field = _field_from_node(child.value)
            if field:
                var_to_field[child.targets[0].id] = field

    for child in ast.walk(node):
        if not isinstance(child, ast.If):
            continue
        checked_name = _name_checked_for_truthiness(child.test)
        field = var_to_field.get(checked_name or "")
        if field:
            required.add(field)
    return required


def _field_from_node(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.args:
            return _field_from_node(node.args[0])
        if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "body":
                return _literal_str(node.args[0]) if node.args else ""
    return ""


def _name_checked_for_truthiness(node: ast.AST | None) -> str:
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not) and isinstance(node.operand, ast.Name):
        return node.operand.id
    if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name):
        if any(isinstance(op, (ast.Is, ast.Eq)) for op in node.ops):
            if any(isinstance(comp, ast.Constant) and comp.value in {None, ""} for comp in node.comparators):
                return node.left.id
    return ""


def _response_details(node: ast.AST | None, helper_returns: dict[str, Any] | None = None) -> dict[str, Any]:
    if node is None:
        return {"response_keys": [], "errors": [], "status_codes": [], "example_payload": None}

    response_keys: list[str] = []
    errors: list[str] = []
    status_codes: list[int] = []
    seen_keys: set[str] = set()
    seen_errors: set[str] = set()
    seen_status: set[int] = set()
    example_payload = None
    helper_returns = helper_returns or {}

    for child in ast.walk(node):
        if not isinstance(child, ast.Call) or _call_name(child) != "JsonResponse":
            continue

        payload = child.args[0] if child.args else None
        resolved_payload = _literal_payload(payload)
        if resolved_payload is None and isinstance(payload, ast.Call) and isinstance(payload.func, ast.Name):
            resolved_payload = helper_returns.get(payload.func.id)
        if isinstance(resolved_payload, dict):
            non_error_keys = [str(key or "").strip() for key in resolved_payload.keys() if str(key or "").strip() and str(key or "").strip() != "error"]
            if example_payload is None and non_error_keys:
                example_payload = resolved_payload
            for key, value in resolved_payload.items():
                key = str(key or "").strip()
                if not key:
                    continue
                if key == "error":
                    message = str(value or "").strip()
                    if message and message not in seen_errors:
                        seen_errors.add(message)
                        errors.append(message)
                    continue
                if key not in seen_keys:
                    seen_keys.add(key)
                    response_keys.append(key)

        for keyword in child.keywords:
            if keyword.arg == "status":
                status_value = _literal_int(keyword.value)
                if status_value is not None and status_value not in seen_status:
                    seen_status.add(status_value)
                    status_codes.append(status_value)

    if response_keys and 200 not in seen_status:
        status_codes.append(200)

    return {
        "response_keys": response_keys,
        "errors": errors,
        "status_codes": sorted(set(status_codes)),
        "example_payload": example_payload,
    }


def _literal_int(node: ast.AST | None) -> int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    return None


def _resource_phrase(view_name: str, path: str) -> str:
    segments = []
    for segment in str(path or "").strip("/").split("/"):
        normalized = segment.strip()
        if not normalized or normalized == "api" or normalized.startswith("<"):
            continue
        segments.append(normalized.replace("-", " ").replace("_", " "))
    title = " ".join(segments).strip()
    if title:
        return title
    fallback = str(view_name or "").replace("_", " ").replace("-", " ").strip()
    return fallback or "endpoint"


def _generic_summary(view_name: str, path: str, method: str) -> str:
    title = _resource_phrase(view_name, path)
    if method == "GET":
        return f"Read `{title}` data."
    if method == "POST":
        return f"Submit a request for `{title}`."
    if method == "PATCH":
        return f"Partially update `{title}` data."
    if method == "DELETE":
        return f"Delete, stop, or remove `{title}`."
    return f"Call `{title}`."


def _generic_when_to_use(path: str, method: str) -> str:
    title = _resource_phrase("", path)
    if method == "GET":
        return f"Use this when a client needs to load or refresh `{title}`."
    if method == "POST":
        return f"Use this when a client needs to submit work for `{title}`."
    if method == "PATCH":
        return f"Use this when a client needs to partially update `{title}`."
    if method == "DELETE":
        return f"Use this when a client needs to remove, stop, or cancel `{title}`."
    return f"Use this when a client needs to call `{title}`."


def _behavior_notes_from_source(source: str) -> list[str]:
    notes: list[str] = []
    if "threading.Thread" in source:
        notes.append("Starts background work instead of waiting for the full job to finish inline.")
    if "StreamingHttpResponse" in source or "text/event-stream" in source:
        notes.append("Returns a streaming response instead of a single JSON payload.")
    if "workspace_manager.write_file" in source:
        notes.append("Writes directly into the connected workspace on disk.")
    if "sandbox.run_command" in source:
        notes.append("Executes a sandboxed command inside the workspace.")
    if "sandbox.kill_process" in source:
        notes.append("Can terminate a running workspace process.")
    if "Method not allowed" in source:
        notes.append("Rejects unsupported HTTP methods with a 405 response.")
    return notes


def _access_details(view_info: dict[str, Any]) -> tuple[str, bool]:
    decorators = {str(item or "") for item in view_info.get("decorators") or []}
    if any(token in decorators for token in {"login_required", "permission_required"}):
        return ("Authentication or permission decorators were detected on this handler.", True)
    if "csrf_exempt" in decorators:
        return ("CSRF is exempted and no explicit auth or permission checks were detected in the handler.", False)
    return ("No explicit auth or permission decorators were detected in the handler.", False)


def _group_for_path(path: str) -> str:
    normalized = path.strip("/").split("/")
    if not normalized:
        return "Other"
    if normalized[0] == "api":
        normalized = normalized[1:]
    if not normalized:
        return "Other"
    if normalized[0] == "settings":
        return "Settings"
    if normalized[0] == "workspace":
        return "Workspace"
    if normalized[0] == "projects":
        if len(normalized) >= 3 and normalized[1] == "import":
            return "Imports"
        if "chat" in normalized:
            return "Chat"
        if "documentation" in normalized or "codebase" in normalized:
            return "Documentation"
        if "features" in normalized or "pipeline" in normalized:
            return "Work Items"
        if "agent" in normalized:
            return "Agents"
        return "Projects"
    return "Other"


def _placeholder_request_body(fields: list[str], view_name: str, method: str) -> dict[str, Any] | None:
    if method == "GET" or not fields:
        return None
    return {field: _placeholder_value(field, view_name=view_name, response=False) for field in fields}


def _placeholder_response(keys: list[str]) -> dict[str, Any] | None:
    if not keys:
        return None
    return {key: _placeholder_value(key, response=True) for key in keys}


def _payload_field_objects(payload: Any, *, description: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    return [
        {
            "name": str(key),
            "required": False,
            "description": description,
        }
        for key in payload.keys()
        if str(key)
    ]


def _payload_keys(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    return [str(key) for key in payload.keys() if str(key)]


def _merge_field_objects(primary: list[dict[str, Any]], secondary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    index_by_name: dict[str, int] = {}

    for item in list(primary or []) + list(secondary or []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        normalized = {
            "name": name,
            "required": bool(item.get("required")),
            "description": str(item.get("description") or "").strip(),
        }
        existing_index = index_by_name.get(name)
        if existing_index is None:
            index_by_name[name] = len(merged)
            merged.append(normalized)
            continue
        existing = merged[existing_index]
        existing["required"] = bool(existing.get("required")) or bool(normalized.get("required"))
        if not existing.get("description") and normalized.get("description"):
            existing["description"] = normalized["description"]

    return merged


def _merge_key_lists(primary: list[str], secondary: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for item in list(primary or []) + list(secondary or []):
        key = str(item or "").strip()
        if key and key not in seen:
            seen.add(key)
            merged.append(key)
    return merged


def _merge_status_codes(primary: list[int], secondary: list[int]) -> list[int]:
    merged: list[int] = []
    seen: set[int] = set()
    for item in list(primary or []) + list(secondary or []):
        try:
            code = int(item)
        except (TypeError, ValueError):
            continue
        if code not in seen:
            seen.add(code)
            merged.append(code)
    return sorted(merged)


def _placeholder_value(field: str, *, view_name: str = "", response: bool = False) -> Any:
    if field in FIELD_EXAMPLES:
        return FIELD_EXAMPLES[field]
    lowered = str(field or "").lower()
    if lowered.endswith("_id"):
        return f"{lowered[:-3] or 'item'}_123"
    if lowered.endswith("_url"):
        return "http://127.0.0.1:5173"
    if lowered in {"projects", "features", "sessions", "messages", "logs", "tests", "suggestions", "blockers"}:
        return []
    if lowered in {"ready", "available", "success", "ok"}:
        return True
    if lowered in {"status", "overall_status"}:
        return "ok" if response else "pending"
    if lowered in {"count", "score", "coverage", "progress_pct", "completed_sections", "total_sections"}:
        return 0
    if lowered == "runtime":
        return {"run_command": "npm run dev"}
    if lowered == "documentation":
        return {"available": True, "status": "completed"}
    if lowered == "blueprint":
        return {"summary": "Generated documentation summary"}
    if lowered == "doc":
        return {"name": "reference", "kind": "directory"}
    if lowered == "trace":
        return {"approach": "Derived from source evidence"}
    if lowered == "type":
        return "file"
    if lowered == "content":
        return "Sample content"
    if lowered == "ai_config":
        return FIELD_EXAMPLES["ai_config"]
    return "string"


def _curl_example(entry: dict[str, Any]) -> str:
    method = str(entry.get("method") or "GET").upper()
    path = str(entry.get("path") or "/")
    query_params = list(entry.get("query_params") or [])
    body = entry.get("request_body")
    url = f"http://localhost:8000{path}"
    if method == "GET" and query_params:
        query_bits = []
        for item in query_params:
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            query_bits.append(f"{name}=sample")
        if query_bits:
            url = f"{url}?{'&'.join(query_bits)}"

    if method == "GET":
        return f'curl -X GET "{url}"'

    if body is None:
        return f'curl -X {method} "{url}"'

    body_json = json.dumps(body, ensure_ascii=True)
    return f"curl -X {method} {url} -H \"Content-Type: application/json\" -d '{body_json}'"

