import json
import logging
import os
import re
import time
from pathlib import Path

from agents.core.base import ai_config_is_usable
from agents.core.checkpoints import delete_workspace_checkpoint, snapshot_previous_contents
from agents.memory.store import (
    build_blueprint_context,
    index_semantic_memory,
    read_query_relevant_file_content,
    record_episode,
    retrieve_relevant_files,
    upsert_working_memory,
)
from agents.customization.project_customization import build_project_customization_summary
from agents.core.workspace import SKIP_DIRS
from core.models import Changeset, ChatMessage, Feature, FileDiff, Project

from api.chat.helpers import (
    _changeset_by_id,
    _chat_changeset_trace_metadata,
    _chat_checkpoint_review_payload,
    _chat_message_attachments,
    _chat_request_text,
)
from api.codebase.doc_builder import _project_workspace_path
from api.project_utils import _project_ai_config
from api.workspace.memory import _read_project_instructions
from api.workspace.runtime import _runtime_response_payload, detect_runtime, runtime_process_id, setup_process_id

logger = logging.getLogger(__name__)

def _secondary_runtime_process_id(workspace_id: str, index: int = 0) -> str:
    return f"{workspace_id}_runtime_secondary_{index}"


def _collect_workspace_context(workspace_path: Path, selected_file: str = "", selected_content: str = "", limit: int = 24) -> list[dict]:
    source_exts = {".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".json", ".md"}
    context = []
    seen = set()

    def add_entry(rel_path: str, content: str):
        normalized = rel_path.replace('\\', '/')
        if normalized in seen or len(context) >= limit:
            return
        seen.add(normalized)
        context.append({"path": normalized, "content": content})

    if selected_file:
        if selected_content:
            add_entry(selected_file, selected_content)
        else:
            selected_path = workspace_path / selected_file
            if selected_path.exists() and selected_path.is_file():
                try:
                    add_entry(selected_file, selected_path.read_text(encoding='utf-8', errors='ignore'))
                except Exception:
                    pass

    priority_files = [
        "package.json", "vite.config.js", "vite.config.ts", "index.html",
        "main.py", "app.py", "requirements.txt", "manage.py", "README.md",
    ]
    for rel_path in priority_files:
        candidate = workspace_path / rel_path
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            add_entry(rel_path, candidate.read_text(encoding='utf-8', errors='ignore'))
        except Exception:
            continue

    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [d for d in sorted(dirs) if d not in SKIP_DIRS]
        for filename in sorted(files):
            if len(context) >= limit:
                return context
            path = Path(root) / filename
            rel_path = str(path.relative_to(workspace_path)).replace('\\', '/')
            if path.suffix.lower() not in source_exts:
                continue
            try:
                add_entry(rel_path, path.read_text(encoding='utf-8', errors='ignore'))
            except Exception:
                continue

    return context


def _looks_like_edit_request(message: str) -> bool:
    lower = message.lower()
    edit_verbs = (
        'add', 'build', 'change', 'create', 'edit', 'fix', 'implement',
        'make',
        'improve', 'modify', 'redesign', 'refactor', 'remove', 'rename',
        'replace', 'restyle', 'update',
    )
    question_starts = ('what', 'why', 'how', 'explain', 'show', 'where', 'which')
    return any(re.search(rf'\b{verb}\b', lower) for verb in edit_verbs) and not lower.startswith(question_starts)


def _looks_like_read_only_request(message: str) -> bool:
    lowered = str(message or '').strip().lower()
    if not lowered:
        return False

    edit_verbs = (
        'add', 'build', 'change', 'create', 'edit', 'fix', 'implement',
        'make', 'improve', 'modify', 'redesign', 'refactor', 'remove',
        'rename', 'replace', 'restyle', 'update',
    )
    if any(re.search(rf'\b{verb}\b', lowered) for verb in edit_verbs):
        return False

    explicit_read_only_prefixes = (
        'what ', 'why ', 'how ', 'where ', 'which ', 'explain ',
        'inspect ', 'analyze ', 'analyse ', 'review ', 'summarize ',
        'summarise ', 'show me ', 'tell me ', 'read through ', 'go through ',
    )
    explicit_read_only_phrases = (
        'how does',
        'what does',
        'why does',
        'can you explain',
        'could you explain',
        'can you inspect',
        'could you inspect',
        'can you review',
        'could you review',
        'just explain',
        'just inspect',
        'just analyze',
        'just review',
        'without changing',
        'without edits',
        'do not change',
        "don't change",
        'read-only',
    )
    return (
        any(lowered.startswith(prefix) for prefix in explicit_read_only_prefixes)
        or any(phrase in lowered for phrase in explicit_read_only_phrases)
    )


CHAT_SPECIAL_CONTEXTS = {
    'codebase': 'Whole-project summary and indexed repo context',
    'currentfile': 'The file currently open in the workspace',
    'readme': 'Root docs like README, CONTRIBUTING, SECURITY, and VISION',
    'rules': 'Project instructions and workspace rules',
    'conversation': 'Recent chat history in this project',
    'terminal': 'Runtime status and detected commands',
}
LEGACY_CHAT_SESSION_ID = "legacy-project-chat"


def _chat_workspace_path(project: Project) -> Path | None:
    if project.workspace_id:
        try:
            return workspace_manager.get_workspace_path(project.workspace_id)
        except Exception:
            pass
    return _project_workspace_path(project)


def _normalize_chat_mentions(raw_mentions) -> list[dict]:
    normalized = []
    for item in raw_mentions or []:
        if isinstance(item, str):
            value = item.strip()
            if not value:
                continue
            mention_type = 'special' if value.lower().lstrip('@') in CHAT_SPECIAL_CONTEXTS else 'file'
            normalized.append({'type': mention_type, 'value': value.lstrip('@'), 'label': f"@{value.lstrip('@')}"})
            continue
        if not isinstance(item, dict):
            continue
        mention_type = str(item.get('type') or '').strip().lower()
        value = str(item.get('value') or '').strip().lstrip('@')
        if mention_type not in {'special', 'file', 'folder'} or not value:
            continue
        normalized.append({
            'type': mention_type,
            'value': value,
            'label': str(item.get('label') or f"@{value}"),
        })
    return normalized


def _infer_inline_chat_mentions(content: str) -> list[dict]:
    inferred = []
    for token in re.findall(r'@([A-Za-z0-9_./-]+)', str(content or '')):
        value = token.strip()
        if not value:
            continue
        lowered = value.lower()
        if lowered in CHAT_SPECIAL_CONTEXTS:
            inferred.append({'type': 'special', 'value': value, 'label': f"@{value}"})
        elif '/' in value or '.' in value:
            inferred.append({'type': 'file', 'value': value, 'label': f"@{value}"})
    return inferred


def _dedupe_chat_mentions(*groups: list[dict]) -> list[dict]:
    seen = set()
    merged = []
    for group in groups:
        for item in group or []:
            key = (item.get('type'), item.get('value'))
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged


def _chat_session_id_from_metadata(metadata) -> str:
    if isinstance(metadata, dict):
        session_id = str(metadata.get('session_id') or '').strip()
        if session_id:
            return session_id
    return LEGACY_CHAT_SESSION_ID


def _chat_message_session_id(message) -> str:
    if isinstance(message, dict):
        return _chat_session_id_from_metadata(message.get('metadata') or {})
    return _chat_session_id_from_metadata(getattr(message, 'metadata', {}) or {})


def _chat_session_title(messages: list[dict], session_id: str) -> str:
    for item in messages:
        if str(item.get('role') or '') != 'user':
            continue
        content = str(item.get('content') or '').strip()
        attachments = _chat_message_attachments(item)
        if not content:
            if attachments:
                first_name = str((attachments[0] or {}).get('name') or 'Attached image').strip() or 'Attached image'
                if len(attachments) == 1:
                    return first_name
                return f"{first_name} (+{len(attachments) - 1} more)"
            continue
        first_line = content.splitlines()[0].strip()
        if not first_line:
            continue
        return first_line if len(first_line) <= 72 else f"{first_line[:69]}..."
    return 'Previous chat' if session_id == LEGACY_CHAT_SESSION_ID else 'New chat'


def _serialize_chat_message(project: Project, item: dict) -> dict:
    metadata = dict(item.get('metadata') or {})
    attachments = _chat_message_attachments(metadata)
    if attachments:
        metadata['attachments'] = attachments
    changeset = _changeset_by_id(project, metadata.get('changeset_id'))
    if changeset:
        metadata.update(_chat_changeset_trace_metadata(changeset))
    return {
        'id': item.get('id'),
        'role': item.get('role'),
        'content': item.get('content'),
        'metadata': metadata,
        'created_at': item.get('created_at'),
        'session_id': _chat_session_id_from_metadata(metadata),
    }


def _project_chat_messages(project: Project) -> list[dict]:
    return list(
        ChatMessage.objects.filter(project=project)
        .order_by('created_at', 'id')
        .values('id', 'role', 'content', 'metadata', 'created_at')
    )


def _group_project_chat_sessions(project: Project) -> tuple[dict[str, list[dict]], list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for item in _project_chat_messages(project):
        grouped.setdefault(_chat_message_session_id(item), []).append(item)

    sessions = []
    for session_id, messages in grouped.items():
        latest = messages[-1]
        sessions.append(
            {
                'session_id': session_id,
                'title': _chat_session_title(messages, session_id),
                'updated_at': latest.get('created_at'),
                'message_count': len(messages),
                'legacy': session_id == LEGACY_CHAT_SESSION_ID,
            }
        )
    sessions.sort(key=lambda item: item.get('updated_at') or timezone.now(), reverse=True)
    return grouped, sessions


def _safe_read_workspace_file(workspace_path: Path, rel_path: str, limit: int = 5000) -> str:
    normalized = str(rel_path or '').replace('\\', '/').strip('/')
    if not normalized:
        return ''
    candidate = workspace_path / normalized
    try:
        candidate.resolve().relative_to(workspace_path.resolve())
    except Exception:
        return ''
    try:
        if candidate.exists() and candidate.is_file():
            return candidate.read_text(encoding='utf-8', errors='ignore')[:limit]
    except Exception:
        return ''
    return ''


def _folder_context_block(codebase_context: dict, folder_path: str) -> tuple[str, list[dict]]:
    normalized = str(folder_path or '').replace('\\', '/').strip('/').rstrip('/')
    if not normalized:
        return '', []
    important_files = [
        item for item in (codebase_context.get('important_files') or [])
        if str(item.get('path') or '').startswith(f"{normalized}/")
    ][:8]
    if not important_files:
        return '', []
    lines = [f"Folder context for `{normalized}/`:"]
    evidence = []
    for item in important_files:
        path = str(item.get('path') or '')
        lines.append(f"- `{path}`: {item.get('summary') or item.get('brief') or 'Indexed file'}")
        evidence.append({
            'path': path,
            'source': 'folder',
            'reason': f"Used as representative evidence for the `{normalized}/` folder.",
        })
    return "\n".join(lines), evidence


def _lazy_chat_file_context(workspace_path: Path | None, rel_path: str, codebase_context: dict | None = None, limit: int = 5000) -> tuple[str, dict | None]:
    if not workspace_path or not rel_path:
        return "", None
    try:
        target_path = (workspace_path / rel_path).resolve()
        if workspace_path.resolve() not in target_path.parents and target_path != workspace_path.resolve():
            return "", None
        if not target_path.exists() or not target_path.is_file():
            return "", None
    except Exception:
        return "", None

    normalized = str(rel_path).replace("\\", "/").strip("/")
    summary = _cached_file_summary(codebase_context or {}, normalized) or _file_summary(target_path, workspace_path, include_excerpt=True)
    content = read_query_relevant_file_content(workspace_path, normalized, query=normalized, limit=limit)
    if not content:
        return "", summary

    blocks = [f"`{normalized}`"]
    if summary:
        blocks.append(f"Summary: {summary.get('summary') or summary.get('purpose') or 'No summary available.'}")
        if summary.get("symbol"):
            blocks.append(f"Primary symbol: {summary.get('symbol')}")
        if summary.get("routes"):
            blocks.append(f"Routes: {', '.join(summary.get('routes')[:6])}")
        if summary.get("data_models"):
            blocks.append(f"Models: {', '.join(summary.get('data_models')[:6])}")
    blocks.append("Content:")
    blocks.append(content)
    return "\n".join(blocks), summary


def _looks_like_ui_style_question(content: str) -> bool:
    lowered = str(content or '').lower()
    if not lowered:
        return False
    broad_redesign_markers = (
        'whole ui', 'entire ui', 'make it dark', 'dark theme', 'dark themed',
        'glassmorphism', 'glassmorph', 'translucent', 'topbar', 'top bar',
        'delete button', 'remove the', 'move it', 'move the', 'retheme',
        'redesign', 'restyle the whole', 'overall theme',
    )
    if any(marker in lowered for marker in broad_redesign_markers):
        return False
    style_markers = (
        'color', 'colour', 'highlight', 'background', 'bg-', 'hover', 'text color',
        'text-color', 'selected', 'active', 'border', 'hover state',
    )
    ui_markers = (
        'sidebar', 'side bar', 'nav', 'navigation', 'menu', 'tab', 'tabs',
        'item', 'items', 'button', 'buttons', 'file tree', 'explorer',
        'folder', 'panel', 'selected', 'active',
    )
    action_markers = ('change', 'edit', 'update', 'modify', 'set', 'switch', 'customize', 'tweak')
    has_style = any(marker in lowered for marker in style_markers)
    has_ui = any(marker in lowered for marker in ui_markers)
    has_action = any(marker in lowered for marker in action_markers) or 'how do i' in lowered or 'how to' in lowered
    return has_style and has_ui and has_action


def _looks_like_ui_redesign_request(content: str) -> bool:
    lowered = str(content or '').lower()
    if not lowered:
        return False
    redesign_markers = (
        'whole ui', 'entire ui', 'make it dark', 'dark theme', 'dark themed',
        'glassmorphism', 'glassmorph', 'translucent', 'topbar', 'top bar',
        'toolbar', 'header', 'delete button', 'remove the', 'move it', 'move the',
        'layout', '2 pane', 'two pane', 'two-pane', 'split pane', 'split view',
        'restyle', 'redesign', 'workspace',
    )
    action_markers = ('change', 'edit', 'update', 'modify', 'make', 'move', 'remove', 'convert')
    return any(marker in lowered for marker in redesign_markers) and any(marker in lowered for marker in action_markers)


CHAT_STATE_NEEDS_CLARIFICATION = 'needs_clarification'
CHAT_STATE_GROUNDED_ANSWER = 'grounded_answer'
CHAT_STATE_EDIT_REQUEST = 'edit_request'
CHAT_STATE_BROAD_REDESIGN = 'broad_redesign'
CHAT_STATE_AGENT_REQUEST = 'agent_request'

CHAT_MODE_ASK = 'ask'
CHAT_MODE_EDIT = 'edit'
CHAT_MODE_AGENT = 'agent'
CHAT_MODE_VALUES = {CHAT_MODE_ASK, CHAT_MODE_EDIT, CHAT_MODE_AGENT}


def _normalize_chat_mode(value) -> str | None:
    normalized = str(value or '').strip().lower()
    if normalized in CHAT_MODE_VALUES:
        return normalized
    return None


def _should_apply_changes_for_chat_mode(chat_mode: str | None, content: str, apply_changes) -> bool:
    if chat_mode == CHAT_MODE_ASK:
        return False
    if chat_mode == CHAT_MODE_EDIT:
        return True
    if chat_mode == CHAT_MODE_AGENT:
        if apply_changes is None:
            return not _looks_like_read_only_request(content)
        return bool(apply_changes)
    return _looks_like_edit_request(content) if apply_changes is None else bool(apply_changes)


def _extract_class_fragments(snippet: str) -> list[str]:
    fragments: list[str] = []
    seen: set[str] = set()
    patterns = [
        r"'([^']+)'",
        r'"([^"]+)"',
    ]
    for pattern in patterns:
        for match in re.findall(pattern, str(snippet or '')):
            normalized = str(match or '').strip()
            if not normalized or normalized in seen:
                continue
            if any(marker in normalized for marker in ('${', '?', '=>', '{', '}')):
                continue
            tokens = [token for token in normalized.split() if token]
            if not tokens:
                continue
            if not any(
                token.startswith(('bg-', 'text-', 'hover:', 'border-', 'shadow-[', 'fill-', 'ring-', 'outline-', 'from-', 'to-'))
                for token in tokens
            ):
                continue
            seen.add(normalized)
            fragments.append(normalized)
    return fragments


def _describe_ui_style_match(snippet: str) -> str:
    lowered = str(snippet or '').lower()
    if 'activetab === tab.id' in lowered:
        return 'active navigation item'
    if 'selectedfile === node.path' in lowered:
        return 'selected file row'
    if 'activesidepanel' in lowered:
        return 'active side panel icon'
    if 'hover:bg' in lowered or 'hover:text' in lowered:
        return 'hover state'
    if 'selected' in lowered:
        return 'selected item'
    if 'active' in lowered:
        return 'active item'
    return 'matching UI state'


def _extract_ui_style_evidence(workspace_path: Path | None, file_paths: list[str], query: str, limit: int = 4) -> list[dict]:
    if not workspace_path:
        return []

    unique_paths: list[str] = []
    seen_paths: set[str] = set()
    for raw_path in file_paths:
        normalized = str(raw_path or '').replace('\\', '/').strip('/')
        if not normalized or normalized in seen_paths:
            continue
        seen_paths.add(normalized)
        unique_paths.append(normalized)

    def path_score(rel_path: str) -> float:
        lowered_path = str(rel_path or '').lower()
        score = 0.0
        if 'sidebar' in str(query or '').lower():
            if any(token in lowered_path for token in ('projectview', 'workspace', 'sidebar', 'nav', 'panel')):
                score += 3.0
        if any(token in lowered_path for token in ('projectview', 'workspace', 'panel', 'layout', 'header', 'nav', 'sidebar')):
            score += 1.5
        if '/pages/' in lowered_path:
            score += 1.0
        return score

    unique_paths.sort(key=lambda path: (-path_score(path), path))

    query_terms = {
        term for term in re.findall(r'[a-z0-9_#-]+', str(query or '').lower())
        if len(term) > 2
    }
    target_terms = query_terms | {
        'sidebar', 'views', 'explorer', 'navigation', 'nav', 'tab', 'tabs',
        'item', 'items', 'selected', 'active', 'hover', 'foldertree',
    }

    evidence: list[dict] = []
    for rel_path in unique_paths[:24]:
        if not rel_path.lower().endswith(('.tsx', '.jsx', '.ts', '.js', '.css', '.scss')):
            continue
        content = _safe_read_workspace_file(workspace_path, rel_path, limit=50000)
        if not content:
            continue
        lines = content.splitlines()
        matches: list[dict] = []
        for index in range(len(lines)):
            window_start = max(0, index - 2)
            window_end = min(len(lines), index + 3)
            snippet = "\n".join(lines[window_start:window_end]).strip()
            lowered = snippet.lower()
            if not any(marker in lowered for marker in ('classname', 'class=', 'bg-', 'text-', 'hover:', 'border-', 'selected', 'active')):
                continue
            classes = _extract_class_fragments(snippet)
            if not classes and 'classname' not in lowered and 'class=' not in lowered:
                continue
            score = 0.0
            if 'classname' in lowered or 'class=' in lowered:
                score += 2.0
            if classes:
                score += 1.0
                if any(any(token.startswith(prefix) for prefix in ('bg-', 'hover:bg', 'text-white', 'border-', 'shadow-[')) for token in " ".join(classes).split()):
                    score += 1.5
            if any(marker in lowered for marker in ('selected', 'active', 'hover')):
                score += 1.5
            if any(marker in lowered for marker in ('activetab ===', 'selectedfile ===', 'activesidepanel', '=== node.path')):
                score += 3.0
            if any(term in lowered for term in target_terms):
                score += 2.0
            if any(term in rel_path.lower() for term in ('view', 'sidebar', 'workspace', 'panel', 'nav', 'explorer')):
                score += 1.0
            if score < 2.5:
                continue
            matches.append(
                {
                    'path': rel_path,
                    'line_number': index + 1,
                    'snippet': snippet,
                    'classes': classes,
                    'label': _describe_ui_style_match(snippet),
                    'score': score,
                }
            )
        matches.sort(key=lambda item: (-float(item.get('score') or 0), int(item.get('line_number') or 0)))
        evidence.extend(matches[:2])

    evidence.sort(key=lambda item: (-float(item.get('score') or 0), str(item.get('path') or ''), int(item.get('line_number') or 0)))
    return evidence[:limit]


def _answer_ui_style_question_from_evidence(
    project: Project,
    content: str,
    selected_file: str,
    context_trace: dict,
) -> str:
    if not _looks_like_ui_style_question(content):
        return ''

    workspace_path = _chat_workspace_path(project)
    if not workspace_path:
        return ''

    candidate_paths = []
    if selected_file:
        candidate_paths.append(selected_file)
    candidate_paths.extend(str(item.get('path') or '') for item in (context_trace.get('files_accessed') or []))
    evidence = _extract_ui_style_evidence(workspace_path, candidate_paths, content)
    if not evidence:
        return ''

    high_confidence = [
        item for item in evidence
        if str(item.get('label') or '') in {'active navigation item', 'selected file row', 'active side panel icon'}
    ]
    if 'sidebar' in str(content or '').lower():
        if not high_confidence:
            return ''
        evidence = high_confidence[:4]
    elif high_confidence:
        evidence = high_confidence[:4]

    lines = ["I found the current sidebar-related highlight styles directly in the codebase."]
    if len(evidence) > 1:
        lines.append("There are multiple sidebar-like surfaces in this project:")

    for item in evidence:
        path = str(item.get('path') or '')
        line_number = int(item.get('line_number') or 1)
        label = str(item.get('label') or 'matching UI state')
        classes = list(item.get('classes') or [])
        if classes:
            class_text = "`, `".join(classes[:3])
            lines.append(f"- `{path}:{line_number}` controls the {label} with `{class_text}`.")
        else:
            snippet = " ".join(str(item.get('snippet') or '').split())
            lines.append(f"- `{path}:{line_number}` controls the {label}. Current code: `{snippet[:220]}`")

    lines.append("Change those current class strings to your new Tailwind colors instead of adding a separate template example.")
    return "\n".join(lines)


def _build_ui_clarification_question(
    project: Project,
    content: str,
    selected_file: str,
    context_mentions,
    context_trace: dict,
) -> str:
    lowered = str(content or '').lower()
    if not _looks_like_ui_style_question(content):
        return ''
    if selected_file:
        return ''

    normalized_mentions = _normalize_chat_mentions(context_mentions)
    if any(item.get('type') == 'file' for item in normalized_mentions):
        return ''
    if any(token in lowered for token in ('@currentfile', '@codebase', '.tsx', '.jsx', '.ts', '.js', '/', '\\')):
        return ''
    if any(token in lowered for token in ('workspace', 'file explorer', 'explorer', 'project view', 'views nav', 'navigation menu', 'blueprint')):
        return ''

    ambiguous_terms = [term for term in ('sidebar', 'panel', 'topbar', 'top bar', 'header', 'toolbar') if term in lowered]
    if not ambiguous_terms:
        return ''

    workspace_path = _chat_workspace_path(project)
    if not workspace_path:
        return ''

    candidate_paths = [str(item.get('path') or '') for item in (context_trace.get('files_accessed') or [])]
    codebase_context = {}
    try:
        codebase_context = build_blueprint_context(project, workspace_path)
    except Exception:
        codebase_context = {}
    candidate_paths.extend(_ui_style_candidate_paths(codebase_context, candidate_paths))

    evidence = _extract_ui_style_evidence(workspace_path, candidate_paths, content, limit=8)
    if not evidence:
        return ''

    distinct: list[dict] = []
    seen = set()
    for item in evidence:
        key = (str(item.get('path') or ''), str(item.get('label') or ''))
        if key in seen:
            continue
        seen.add(key)
        distinct.append(item)

    if len({str(item.get('path') or '') for item in distinct}) < 2:
        return ''

    lines = ["I’m not fully sure which UI surface you mean."]
    lines.append("Which one should I help you change?")
    lines[0] = "I'm not fully sure which UI surface you mean."
    for item in distinct[:3]:
        path = str(item.get('path') or '')
        label = str(item.get('label') or 'UI state')
        lines.append(f"- `{path}`: {label}")
    lines.append("Reply with the one you mean, and I’ll point to the exact classes to edit.")
    lines = [line for line in lines if "Reply with the one you mean" not in line]
    lines.append("Reply with the one you mean, and I'll point to the exact classes to edit.")
    return "\n".join(lines)


def _classify_chat_state(
    project: Project,
    content: str,
    selected_file: str,
    context_mentions,
    context_trace: dict,
    should_apply_changes: bool,
) -> dict:
    if should_apply_changes and project.workspace_id:
        return {
            'state': CHAT_STATE_EDIT_REQUEST,
            'reason': 'The request looks like a code change and the project has an editable workspace.',
            'response_contract': (
                "When the change succeeds, summarize what changed and which files were touched. "
                "If the change fails, explain the failure plainly and keep the trace intact."
            ),
        }

    clarification_question = _build_ui_clarification_question(
        project,
        content,
        selected_file,
        context_mentions,
        context_trace,
    )
    if clarification_question:
        return {
            'state': CHAT_STATE_NEEDS_CLARIFICATION,
            'reason': 'The request names an ambiguous UI surface and needs a human follow-up before suggesting edits.',
            'response': clarification_question,
            'response_contract': (
                "Ask one short clarifying question, list the most likely UI surfaces, and wait for the user's reply."
            ),
        }

    if _looks_like_ui_redesign_request(content):
        return {
            'state': CHAT_STATE_BROAD_REDESIGN,
            'reason': 'The request is a broader UI or layout redesign and should use full grounded code context.',
            'response_contract': (
                "Response contract:\n"
                "1. Current implementation\n"
                "2. Files to edit\n"
                "3. Change plan\n"
                "4. Risks or follow-ups\n"
                "Use only retrieved evidence when describing the current layout, and do not invent panes or components."
            ),
        }

    direct_style_answer = _answer_ui_style_question_from_evidence(
        project,
        content,
        selected_file,
        context_trace,
    )
    if direct_style_answer:
        return {
            'state': CHAT_STATE_GROUNDED_ANSWER,
            'reason': 'Exact style evidence was extracted from retrieved files, so the answer can be grounded directly.',
            'response': direct_style_answer,
            'response_contract': (
                "Response contract:\n"
                "1. File to edit\n"
                "2. Exact current classes or tokens\n"
                "3. What to change"
            ),
            'mode': 'deterministic_ui_style',
        }

    return {
        'state': CHAT_STATE_GROUNDED_ANSWER,
        'reason': 'The question can be answered from retrieved workspace evidence without asking for clarification.',
        'response_contract': (
            "Response contract:\n"
            "1. Files or surfaces involved\n"
            "2. Current implementation\n"
            "3. Suggested next step\n"
            "Keep examples clearly labeled when they are not the current implementation."
        ),
    }


def _extract_agent_explicit_command(content: str) -> str:
    text = str(content or '').strip()
    if not text:
        return ''
    fenced = re.search(r"```(?:bash|sh|shell|powershell|cmd)?\s*\n(.+?)```", text, re.IGNORECASE | re.DOTALL)
    if fenced:
        candidate = fenced.group(1).strip()
        if candidate:
            return candidate
    inline = re.search(r"`([^`\n]+)`", text)
    if inline:
        candidate = inline.group(1).strip()
        if candidate:
            return candidate
    return ''


def _default_agent_terminal_command(content: str, runtime: dict, workspace_path: Path) -> str:
    lowered = str(content or '').lower()
    runtime_type = str(runtime.get('runtime_type') or '').lower()
    python_cmd = _python_executable_command()

    if any(marker in lowered for marker in ('run tests', 'run the tests', 'test suite', 'execute tests', 'pytest')):
        if runtime_type == 'node':
            return 'npm test'
        return 'pytest'

    if any(marker in lowered for marker in ('run build', 'build the project', 'production build')):
        if runtime_type == 'node':
            return 'npm run build'

    if any(marker in lowered for marker in ('makemigrations', 'make migrations')) and (workspace_path / 'manage.py').exists():
        return f'{python_cmd} manage.py makemigrations'

    if any(marker in lowered for marker in ('run migrations', 'migrate database', 'apply migrations', 'migrate')) and (workspace_path / 'manage.py').exists():
        return f'{python_cmd} manage.py migrate'

    return ''


def _plan_agent_workspace_actions(content: str, runtime: dict, *, edits_applied: bool = False, workspace_path: Path | None = None) -> dict:
    lowered = str(content or '').lower()
    explicit_command = _extract_agent_explicit_command(content)
    generated_command = ''
    if not explicit_command and workspace_path:
        generated_command = _default_agent_terminal_command(content, runtime, workspace_path)

    wants_stop = any(marker in lowered for marker in ('stop project', 'stop the project', 'stop app', 'stop the app', 'stop server', 'kill server', 'shut down'))
    wants_restart = any(marker in lowered for marker in ('restart project', 'restart the project', 'restart app', 'restart the app', 'restart server', 're-run the project', 'rerun the project'))
    wants_run = any(marker in lowered for marker in ('run project', 'run the project', 'start project', 'start the project', 'launch the project', 'launch app', 'open preview', 'boot the app'))
    wants_setup = any(marker in lowered for marker in ('setup project', 'install dependencies', 'prepare project', 'run setup', 'setup & start'))

    should_run_after_edits = edits_applied and bool(runtime.get('run_command'))
    terminal_command = explicit_command or generated_command
    run_setup = bool(runtime.get('setup_command')) and (
        wants_setup
        or ((wants_run or wants_restart or should_run_after_edits or bool(terminal_command)) and runtime.get('install_required'))
    )
    start_runtime = bool(runtime.get('run_command')) and not terminal_command and (wants_run or wants_restart or should_run_after_edits)
    stop_runtime = bool(runtime.get('run_command')) and (wants_stop or wants_restart)

    return {
        'explicit_command': explicit_command,
        'terminal_command': terminal_command,
        'run_setup': run_setup,
        'start_runtime': start_runtime,
        'stop_runtime': stop_runtime,
        'restart_runtime': wants_restart,
        'should_run_after_edits': should_run_after_edits,
        'actionable': any([run_setup, start_runtime, stop_runtime, bool(terminal_command), wants_restart]),
    }


def _trim_agent_output(output: str, limit: int = 320) -> str:
    text = str(output or '').strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def _agent_project_memory_text(memory_context: dict | None) -> str:
    memory_context = memory_context or {}
    sections: list[str] = []

    blueprint_summary = str(memory_context.get('blueprint_summary') or '').strip()
    if blueprint_summary and blueprint_summary != 'No cached codebase summary yet.':
        sections.append(f"Codebase Summary:\n{blueprint_summary[:9000]}")

    semantic_summary = str(memory_context.get('semantic_summary') or '').strip()
    if semantic_summary and semantic_summary != 'No semantic matches yet.':
        sections.append(f"Relevant Semantic Recall:\n{semantic_summary[:5000]}")

    if not sections:
        return ''

    sections.append(
        "Use project memory only as background context. Do not treat earlier tasks, examples, or unrelated past chat topics as current requirements unless the user repeats them in this request."
    )
    return "\n\n".join(sections)


def _agent_execution_prompt_addendum(*, should_apply_changes: bool, selected_file: str = '') -> str:
    lines = [
        "## Workspace Agent Contract",
        "You are operating in a live project workspace with permission to inspect files, edit files, create files, replace files, search code, and run non-destructive commands.",
        "- If the user asks to build, fix, change, refactor, restyle, wire up, migrate, or otherwise modify the project, perform that work directly with tools instead of stopping after analysis.",
        "- Read and search only as much as needed to find the right files, then make the change.",
        "- Use `file_edit` for focused patches.",
        "- Use `file_write` after reading a file first when a full-file rewrite is the clearest or safest way to implement the request.",
        "- Treat prior memory as background only. Do not anchor on previous examples, stale feature ideas, or earlier chats unless the user explicitly asks for them again.",
        "- Keep the request generic to the current project. Do not inject unrelated themes or canned examples.",
        "- Before finishing, inspect the changed files and run a targeted verification command when practical.",
        "- Your final response must summarize the concrete work completed, list files changed, and mention commands run or blockers.",
    ]

    if selected_file:
        lines.append(f"- The currently open file is `{selected_file}`. Use it as a hint, not as a hard limit, if the request spans other files.")

    if should_apply_changes:
        lines.append(
            "- The current user request is an execution request. Apply the requested change in the workspace before you respond; do not answer with analysis alone unless you are blocked."
        )

    return "\n".join(lines)


def _agent_response_fallback(qr, applied_files: list[str]) -> str:
    response = str(getattr(qr, 'response', '') or '').strip()
    if response:
        return response

    tool_calls = list(getattr(qr, 'tool_calls_log', []) or [])
    files_read = list(getattr(qr, 'files_read', []) or [])
    bash_calls = [entry for entry in tool_calls if entry.get('tool') == 'bash']

    if applied_files:
        preview = ", ".join(applied_files[:6])
        if bash_calls:
            return (
                f"Applied changes to {len(applied_files)} file(s): {preview}. "
                f"Ran {len(bash_calls)} command(s) to verify or update the workspace."
            )
        return f"Applied changes to {len(applied_files)} file(s): {preview}."

    if files_read or tool_calls:
        inspected = f"inspected {len(files_read)} file(s)" if files_read else f"used {len(tool_calls)} tool call(s)"
        tools_used = ", ".join(
            dict.fromkeys(str(entry.get('tool') or '') for entry in tool_calls if entry.get('tool'))
        )
        if tools_used:
            return f"The agent {inspected} using {tools_used}, but no code changes were applied."
        return f"The agent {inspected}, but no code changes were applied."

    return "The agent did not return a final summary."


def _wait_for_sandbox_process(sandbox, process_id: str, *, timeout_seconds: float = 240.0, poll_interval: float = 0.35) -> tuple[dict, str]:
    deadline = time.time() + timeout_seconds
    chunks: list[str] = []
    while time.time() < deadline:
        chunks.extend(sandbox.get_output(process_id))
        status = sandbox.get_status(process_id)
        if not status.get('running'):
            chunks.extend(sandbox.get_output(process_id))
            return sandbox.get_status(process_id), ''.join(chunks)
        time.sleep(poll_interval)
    chunks.extend(sandbox.get_output(process_id))
    return sandbox.get_status(process_id), ''.join(chunks)


def _handle_agent_chat_request(
    project: Project,
    content: str,
    *,
    selected_file: str = '',
    selected_content: str = '',
    attachments: list[dict] | None = None,
    session_id: str = '',
    should_apply_changes: bool = False,
    context_trace: dict | None = None,
    memory_context: dict | None = None,
    checkpoint: dict | None = None,
) -> dict:
    from pathlib import Path as _Path
    from sandbox.executor import sandbox

    context_trace = dict(context_trace or {})
    memory_context = memory_context or {}
    attachments = list(attachments or [])
    request_text = _chat_request_text(content, attachments)
    prompt_text = _chat_request_text(content, attachments, include_attachment_inventory=True)
    workspace_path = _chat_workspace_path(project)
    if not project.workspace_id or not workspace_path:
        return {
            'handled': True,
            'assistant_message': (
                "Agent mode needs a connected workspace before it can edit files or run sandbox commands."
            ),
            'assistant_trace': {
                'approach': 'Agent mode was requested, but this project has no active workspace attached.',
                'chat_state': CHAT_STATE_AGENT_REQUEST,
                'chat_mode': CHAT_MODE_AGENT,
                'state_reason': 'Agent mode requires an editable workspace.',
                'session_id': session_id,
                'context_mentions': context_trace.get('context_mentions') or [],
                'context_sources': context_trace.get('context_sources') or [],
                'files_accessed': context_trace.get('files_accessed') or [],
                'commands_ran': [],
                'workspace_actions': [],
                'applied_files': [],
            },
            'applied_changes': None,
            'workspace_actions': [],
        }

    # ── NEW: Use QueryEngine for tool-calling agent loop ──────────
    try:
        from agents.memory.compaction import ContextCompactor
        from agents.orchestration.coordinator import Coordinator
        from agents.customization.prompts import PromptBuilder
        from agents.memory.query_engine import QueryEngine
        from agents.tools.registry import ToolRegistry

        ai_config = _project_ai_config(project)
        registry = ToolRegistry.default_registry()
        compactor = ContextCompactor()
        prompt_builder = PromptBuilder()

        # Build conversation history from session
        conversation_history = []
        try:
            _grouped, _ = _group_project_chat_sessions(project)
            recent = _grouped.get(session_id, [])[-10:]
            for msg in recent:
                role = msg.get('role', 'user') if isinstance(msg, dict) else getattr(msg, 'role', 'user')
                msg_content = msg.get('content', '') if isinstance(msg, dict) else getattr(msg, 'content', '')
                msg_attachments = _chat_message_attachments(msg if isinstance(msg, dict) else {'metadata': getattr(msg, 'metadata', {})})
                gemini_role = 'model' if role == 'assistant' else 'user'
                conversation_history.append(
                    {
                        'role': gemini_role,
                        'content': _chat_request_text(str(msg_content), msg_attachments, include_attachment_inventory=True),
                    }
                )
        except Exception:
            logger.debug("Could not load chat history for session %s", session_id)

        # Build enhanced system prompt
        project_memory_text = _agent_project_memory_text(memory_context)
        project_instructions_text = ''
        try:
            project_instructions_text = _read_project_instructions(project, workspace_path)
        except Exception:
            pass

        customization_ctx = ''
        try:
            from agents.customization.project_customization import build_project_customization_summary
            customization_ctx = build_project_customization_summary(workspace_path)
        except Exception:
            pass

        system_prompt = prompt_builder.build_system_prompt(
            workspace_path=workspace_path,
            tools=registry.all_tools(),
            project_memory=project_memory_text,
            project_instructions=project_instructions_text,
            customization_context=customization_ctx,
        )
        system_prompt += "\n\n" + _agent_execution_prompt_addendum(
            should_apply_changes=should_apply_changes,
            selected_file=selected_file,
        )

        # Add file context if a file is selected
        if selected_file:
            file_context = f"\n\n## Active File Context\nThe user has file `{selected_file}` open."
            if selected_content:
                file_context += f"\nContent:\n```\n{selected_content[:4000]}\n```"
            system_prompt += file_context

        # Collect events for the trace
        tool_events: list[dict] = []

        def on_tool_start(name, args):
            tool_events.append({'type': 'tool_start', 'tool': name, 'args_preview': {k: str(v)[:100] for k, v in args.items()}})

        def on_tool_end(name, result):
            tool_events.append({'type': 'tool_end', 'tool': name, 'success': result.success, 'preview': (result.output or '')[:200]})

        engine = QueryEngine(
            tool_registry=registry,
            prompt_builder=prompt_builder,
            compactor=compactor,
            ai_config=ai_config,
            workspace_id=project.workspace_id,
            workspace_path=workspace_path,
            on_tool_start=on_tool_start,
            on_tool_end=on_tool_end,
        )

        qr = engine.run(
            user_message=prompt_text,
            attachments=attachments,
            conversation_history=conversation_history,
            system_prompt=system_prompt,
            max_turns=25,
        )

        # Build response
        applied_files = list(qr.files_modified)
        workspace_actions = []
        for tc in qr.tool_calls_log:
            workspace_actions.append({
                'type': tc.get('tool', 'tool_call'),
                'status': 'completed' if tc.get('success') else 'failed',
                'command': str(tc.get('args', {}).get('command', ''))[:200] if tc.get('tool') == 'bash' else '',
                'detail': tc.get('output_preview', '')[:200],
            })

        assistant_trace = {
            'approach': f"Agent used {len(qr.tool_calls_log)} tool calls across {qr.turns_used} turns. {'Context was auto-compacted.' if qr.compacted else ''}",
            'chat_state': CHAT_STATE_AGENT_REQUEST,
            'chat_mode': CHAT_MODE_AGENT,
            'state_reason': 'Agentic tool-calling loop completed.',
            'session_id': session_id,
            'context_mentions': context_trace.get('context_mentions') or [],
            'context_sources': context_trace.get('context_sources') or [],
            'files_accessed': [{'path': p, 'reason': 'Read by agent'} for p in qr.files_read[:12]],
            'commands_ran': [
                {'command': tc.get('args', {}).get('command', tc.get('tool', '')), 'status': 'passed' if tc.get('success') else 'failed', 'detail': tc.get('output_preview', '')[:200]}
                for tc in qr.tool_calls_log if tc.get('tool') == 'bash'
            ],
            'workspace_actions': workspace_actions,
            'applied_files': applied_files,
            'tool_events': tool_events[-20:],
            'turns_used': qr.turns_used,
            'compacted': qr.compacted,
            'duration_ms': qr.total_duration_ms,
            'semantic_hits': [
                {'path': item.get('file_path'), 'symbol': item.get('symbol')}
                for item in (memory_context.get('semantic_hits') or [])[:8]
            ],
        }

        applied_changes = None
        if applied_files:
            changeset = _record_chat_changes(
                project,
                content,
                workspace_path,
                snapshot_previous_contents(str(project.id), str((checkpoint or {}).get('id') or ''), applied_files),
                applied_files,
                ai_review=_chat_checkpoint_review_payload(
                    checkpoint,
                    source='chat_agent',
                    chat_mode=CHAT_MODE_AGENT,
                    undo_label='Undo',
                ),
            )
            if changeset:
                applied_changes = {
                    'applied_files': applied_files,
                    'count': len(applied_files),
                    'changeset_id': str(changeset.id),
                    'undo': _chat_changeset_trace_metadata(changeset).get('undo'),
                }
                assistant_trace.update(_chat_changeset_trace_metadata(changeset))
                try:
                    _update_project_memory(project, workspace_path, content, applied_files, [])
                except Exception:
                    logger.exception("Failed to update project memory for agent changes in project %s", project.id)
                try:
                    index_semantic_memory(project, workspace_path, changed_paths=applied_files)
                except Exception:
                    logger.exception("Failed to re-index semantic memory for project %s", project.id)
                try:
                    record_episode(
                        project=project,
                        memory_type='implementation',
                        title='Workspace agent execution',
                        summary=f"Agent mode applied changes for '{request_text[:120]}'. Files: {', '.join(applied_files)}.",
                        related_files=applied_files,
                        metadata={'source': 'chat_agent', 'workspace_actions': workspace_actions},
                    )
                    upsert_working_memory(
                        project,
                        'implementation',
                        (
                            f"Latest implementation request: {request_text[:240]}\n"
                            f"Files touched: {', '.join(applied_files)}\n"
                            "Validation summary:\nNo structured validation was recorded for this direct agent tool execution.\n"
                            "Reviewer summary: No structured review was recorded for this direct agent tool execution."
                        ),
                        {'latest_request': request_text[:240], 'files': applied_files, 'source': 'chat_agent'},
                    )
                except Exception:
                    logger.exception("Failed to persist memory updates for agent changes in project %s", project.id)
        assistant_message_override = ''

        if should_apply_changes and not applied_files:
            try:
                fallback_changes = apply_chat_changes(
                    project,
                    request_text,
                    selected_file=selected_file,
                    selected_content=selected_content,
                    request_attachments=attachments,
                    checkpoint=checkpoint,
                    chat_mode=CHAT_MODE_AGENT,
                    changeset_source='chat_agent',
                )
                fallback_applied_files = list(fallback_changes.get('applied_files') or [])
                if fallback_applied_files:
                    applied_files = fallback_applied_files
                    applied_changes = fallback_changes
                    fallback_trace = _build_chat_trace_from_changes(fallback_changes, context_trace, memory_context)
                    workspace_actions.append({
                        'type': 'implementation_fallback',
                        'status': 'completed',
                        'detail': 'The tool-calling loop inspected the workspace but made no edits, so the structured implementation pipeline applied the requested code changes.',
                    })
                    assistant_trace.update({
                        'approach': 'Agent mode inspected the workspace with tools first, then completed the edit through the structured implementation pipeline because the tool loop returned without file changes.',
                        'state_reason': 'Tool-calling loop completed without file edits; implementation fallback applied.',
                        'files_accessed': [
                            *list(assistant_trace.get('files_accessed') or []),
                            *list(fallback_trace.get('files_accessed') or []),
                        ][:24],
                        'commands_ran': list(fallback_trace.get('commands_ran') or []),
                        'workspace_actions': workspace_actions,
                        'applied_files': applied_files,
                        'plan': fallback_trace.get('plan') or {},
                        'review': fallback_trace.get('review') or {},
                        'semantic_hits': list(fallback_trace.get('semantic_hits') or assistant_trace.get('semantic_hits') or []),
                    })
                    assistant_trace.update({
                        key: value
                        for key, value in fallback_trace.items()
                        if key in {'changeset_id', 'undo', 'undo_available'}
                    })
                    assistant_message_override = (
                        f"Applied the requested update to {len(applied_files)} file(s): "
                        f"{', '.join(applied_files[:6])}."
                    )
            except Exception as fallback_exc:
                logger.exception("Agent mode implementation fallback failed for project %s", project.id)
                workspace_actions.append({
                    'type': 'implementation_fallback',
                    'status': 'failed',
                    'detail': str(fallback_exc)[:220],
                })
                assistant_trace['state_reason'] = 'Tool-calling loop completed without file edits, and the implementation fallback also failed.'
                assistant_trace['fallback_error'] = str(fallback_exc)
                assistant_trace['workspace_actions'] = workspace_actions
        elif checkpoint and not applied_files:
            delete_workspace_checkpoint(str(project.id), str(checkpoint.get('id') or ''))

        # After edits, also handle sandbox actions (setup + runtime)
        runtime = detect_runtime(workspace_path)
        if applied_files:
            action_plan = _plan_agent_workspace_actions(
                request_text, runtime, edits_applied=True, workspace_path=workspace_path,
            )
            runtime_pid = runtime_process_id(project.workspace_id)
            setup_pid = setup_process_id(project.workspace_id)

            if action_plan.get('run_setup') and runtime.get('setup_command'):
                sandbox.run_command(setup_pid, str(runtime.get('setup_command')), str(workspace_path), kind='setup')
                setup_status, setup_output = _wait_for_sandbox_process(sandbox, setup_pid)
                setup_success = int(setup_status.get('returncode') or 0) == 0
                workspace_actions.append({
                    'type': 'setup',
                    'status': 'completed' if setup_success else 'failed',
                    'command': runtime.get('setup_command'),
                    'detail': _trim_agent_output(setup_output) or ('Setup completed.' if setup_success else 'Setup failed.'),
                })

            if action_plan.get('start_runtime') and runtime.get('run_command'):
                for index, secondary_runtime in enumerate(runtime.get('secondary_runtimes') or []):
                    secondary_command = secondary_runtime.get('run_command')
                    if not secondary_command:
                        continue
                    secondary_pid = _secondary_runtime_process_id(project.workspace_id, index)
                    sandbox.run_command(
                        secondary_pid,
                        str(secondary_command),
                        str(workspace_path),
                        kind='runtime',
                        preview_url=secondary_runtime.get('preview_url'),
                    )
                sandbox.run_command(runtime_pid, str(runtime.get('run_command')), str(workspace_path), kind='runtime', preview_url=runtime.get('preview_url'))
                runtime_payload = _runtime_response_payload(runtime, runtime_pid, sandbox, wait_for_preview=True)
                runtime_ready = bool(runtime_payload.get('ready'))
                workspace_actions.append({
                    'type': 'runtime_start',
                    'status': 'completed' if runtime_ready else 'running',
                    'command': runtime.get('run_command'),
                    'preview_url': runtime_payload.get('preview_url'),
                    'detail': 'Preview is ready.' if runtime_ready else 'Runtime started.',
                })

            assistant_trace['workspace_actions'] = workspace_actions

        return {
            'handled': True,
            'assistant_message': assistant_message_override or _agent_response_fallback(qr, applied_files),
            'assistant_trace': assistant_trace,
            'applied_changes': applied_changes,
            'workspace_actions': workspace_actions,
        }

    except Exception as exc:
        logger.exception("QueryEngine agent mode failed for project %s — falling back", project.id)

        # ── FALLBACK: Original agent handler for when engine fails ──
        runtime = detect_runtime(workspace_path)
        applied_changes = None
        applied_files_fallback: list[str] = []
        commands_ran_fallback = list(context_trace.get('commands_ran') or [])
        workspace_actions_fallback: list[dict[str, Any]] = []
        assistant_trace_fallback = {
            'approach': f'Agent mode QueryEngine failed ({exc}), fell back to direct handler.',
            'chat_state': CHAT_STATE_AGENT_REQUEST,
            'chat_mode': CHAT_MODE_AGENT,
            'state_reason': 'Agent mode fallback.',
            'session_id': session_id,
            'context_mentions': context_trace.get('context_mentions') or [],
            'context_sources': context_trace.get('context_sources') or [],
            'files_accessed': context_trace.get('files_accessed') or [],
            'commands_ran': commands_ran_fallback,
            'workspace_actions': workspace_actions_fallback,
            'applied_files': applied_files_fallback,
            'error': str(exc),
        }

        if should_apply_changes:
            try:
                applied_changes = apply_chat_changes(
                    project,
                    request_text,
                    selected_file=selected_file,
                    selected_content=selected_content,
                    request_attachments=attachments,
                    checkpoint=checkpoint,
                    chat_mode=CHAT_MODE_AGENT,
                    changeset_source='chat_agent',
                )
                applied_files_fallback = list(applied_changes.get('applied_files') or [])
                assistant_trace_fallback['applied_files'] = applied_files_fallback
                assistant_trace_fallback.update({
                    key: value
                    for key, value in applied_changes.items()
                    if key in {'changeset_id', 'undo'}
                })
                assistant_trace_fallback['undo_available'] = bool((applied_changes.get('undo') or {}).get('available'))
            except Exception as apply_exc:
                assistant_trace_fallback['error'] = str(apply_exc)
        elif checkpoint:
            delete_workspace_checkpoint(str(project.id), str(checkpoint.get('id') or ''))

        action_plan = _plan_agent_workspace_actions(request_text, runtime, edits_applied=bool(applied_files_fallback), workspace_path=workspace_path)
        if not action_plan.get('actionable') and not applied_files_fallback:
            if checkpoint and not applied_files_fallback:
                delete_workspace_checkpoint(str(project.id), str(checkpoint.get('id') or ''))
            return {'handled': False, 'assistant_message': '', 'assistant_trace': assistant_trace_fallback, 'applied_changes': None, 'workspace_actions': []}

        summary_parts = []
        if applied_files_fallback:
            summary_parts.append(f"Updated {len(applied_files_fallback)} file(s): {', '.join(applied_files_fallback[:6])}.")
        summary_parts.append(f"(Note: the advanced agent engine encountered an error: {exc})")

        return {
            'handled': True,
            'assistant_message': " ".join(summary_parts) or f"Agent mode encountered an issue: {exc}",
            'assistant_trace': assistant_trace_fallback,
            'applied_changes': applied_changes,
            'workspace_actions': workspace_actions_fallback,
        }


def _build_chat_evidence_index(context_trace: dict, limit: int = 12) -> str:
    evidence_index_lines = []
    for item in (context_trace.get('files_accessed') or [])[:limit]:
        path = str(item.get('path') or '').strip()
        if not path:
            continue
        reason = str(item.get('reason') or 'Retrieved as relevant evidence for this question.').strip()
        evidence_index_lines.append(f"- {path}: {reason}")
    return "\n".join(evidence_index_lines) or "- No explicit file evidence was captured for this turn."


def _build_chat_llm_prompt(
    project: Project,
    content: str,
    attachments: list[dict] | None,
    selected_file: str,
    selected_content: str,
    session_id: str,
    context_trace: dict,
    memory_context: dict,
    resolved_context_text: str,
    chat_mode: str | None,
    chat_state: str,
    response_contract: str,
) -> tuple[str, str]:
    blueprint = project.blueprint or {}
    arch = json.dumps(blueprint.get('architecture_overview', ''))[:800]
    tech = ", ".join(project.tech_stack) if project.tech_stack else "Unknown"

    grouped_sessions, _ = _group_project_chat_sessions(project)
    recent = grouped_sessions.get(session_id, [])[-10:]
    history_text = "\n".join(
        [
            f"{message['role']}: {_chat_request_text(message.get('content', ''), _chat_message_attachments(message), include_attachment_inventory=True)}"
            for message in recent
        ]
    )

    file_context = "No file selected."
    if selected_file:
        file_context = f"Active file: {selected_file}\n"
        if selected_content:
            file_context += selected_content[:4000]
        elif project.workspace_id:
            try:
                file_context += workspace_manager.read_file(project.workspace_id, selected_file)[:4000]
            except Exception:
                file_context += "(Unable to read file content.)"
    if resolved_context_text:
        file_context += f"\n\nExplicit context mentions:\n{resolved_context_text[:48000]}"
    attachment_context = describe_image_attachments(attachments) or "No image attachments were supplied for this turn."

    evidence_index = _build_chat_evidence_index(context_trace)
    system_instruction = f"""You are the DevHub AI assistant for the project "{project.name}".
Tech Stack: {tech}
Architecture: {arch}
Working Memory: {memory_context.get('working_summary', '')[:2000]}
Cached Codebase Summary: {memory_context.get('blueprint_summary', '')[:3000]}
Episodic Memory: {memory_context.get('episodic_summary', '')[:1200]}

Help the developer understand, plan and implement features, debug issues, and reason about the current code.
Default to depth, not brevity: unless the user explicitly asks for a short or compact answer, give a thorough answer.
For implementation or architecture questions, explain the real code path step by step using the retrieved evidence, not generic possibilities.
When the question is system-level or end-to-end, cover all relevant layers that appear in context, including backend and frontend pieces when both are involved.
Prefer sections like overview, backend, frontend, flow, and files to change when that helps clarity.
When @codebase is mentioned, provide thorough, evidence-based answers citing specific file paths, function names, and code patterns you can see in the context.
When relevant, use the active file context and keep answers action-oriented and detailed.
If the current user turn includes attached images, treat them as first-class context and incorporate what you can directly observe from them.
For codebase questions, prefer the exact implementation over examples:
- name the real file path(s) first,
- quote the current className, function, route, or variable that controls the behavior when it is present in context,
- do not invent alternative code unless you clearly label it as an example,
- if the evidence is incomplete, say what is confirmed versus what is inferred.
If the retrieved evidence shows a concrete implementation that matches the question, answer from that implementation first and do not hedge with phrases like "might be in" or "it will look something like".
Only mention multiple candidate files when the evidence truly shows multiple distinct implementations that fit the question.
For UI or styling questions, identify the exact component and the current classes or style tokens that control the color, spacing, or state change before suggesting edits, and quote the current class string when available.
For broader UI/layout redesign requests, first describe the current layout using only retrieved evidence, then name the exact file(s) to edit, and do not invent panes, panels, or components that are not present in the code you were given.
DevHub can inspect the current workspace, and in Edit or Agent mode it can also modify files and run sandboxed project commands.
Never say that you lack access to the local codebase or cannot make edits; instead respect the current mode:
- Ask mode: answer only and suggest switching modes if the user wants action.
- Edit mode: treat the request as an implementation request against the actual codebase.
- Agent mode: assume DevHub may edit files and drive the sandboxed runtime when the request is actionable.

Current chat mode: {chat_mode or 'auto'}
Current chat state: {chat_state}
{response_contract}"""
    prompt = (
        f"Current chat mode: {chat_mode or 'auto'}\n"
        f"Current chat state: {chat_state}\n"
        f"{response_contract}\n\n"
        f"Attached images for this turn:\n{attachment_context}\n\n"
        f"Retrieved evidence index:\n{evidence_index}\n\n"
        f"Chat history:\n{history_text}\n\n"
        f"Semantic recall:\n{memory_context.get('semantic_summary', 'No semantic recall.')}\n\n"
        f"Active workspace context:\n{file_context}\n\nUser: {content}"
    )
    return system_instruction, prompt


def _query_prefers_full_primary_files(content: str) -> bool:
    lowered = str(content or '').lower()
    if not lowered:
        return False
    if _looks_like_ui_style_question(content):
        return True
    if _looks_like_ui_redesign_request(content):
        return True
    if _looks_like_edit_request(content):
        return True
    markers = (
        'how do i change', 'how to change', 'where do i change', 'which file',
        'where is', 'where are', 'how do i update', 'how to update',
        'how do i modify', 'how to modify', 'how do i edit', 'how to edit',
        'how do i fix', 'how to fix', 'how does this work', 'trace this',
        'follow this', 'walk me through',
    )
    return any(marker in lowered for marker in markers)


def _chat_primary_file_paths(
    retrieval: dict,
    explicit_paths: list[str] | None,
    query: str,
    max_primary: int = 2,
) -> set[str]:
    primary: list[str] = []
    seen: set[str] = set()
    for path in explicit_paths or []:
        normalized = str(path or '').replace('\\', '/').strip('/')
        if normalized and normalized not in seen:
            seen.add(normalized)
            primary.append(normalized)
    if _query_prefers_full_primary_files(query):
        for item in retrieval.get('files', []):
            path = str(item.get('path') or '').replace('\\', '/').strip('/')
            if not path or path in seen:
                continue
            seen.add(path)
            primary.append(path)
            if len(primary) >= max_primary:
                break
    return set(primary[:max_primary])


def _ui_style_candidate_paths(cache: dict, existing_paths: list[str] | None = None, max_extra: int = 6) -> list[str]:
    seen = {
        str(path or '').replace('\\', '/').strip('/')
        for path in (existing_paths or [])
        if str(path or '').strip()
    }
    extras: list[str] = []
    pool: list[dict] = []
    for item in list(cache.get('all_file_summaries') or []) + list(cache.get('important_files') or []):
        if not isinstance(item, dict):
            continue
        pool.append(item)
        if len(pool) >= 240:
            break
    for item in pool:
        path = str(item.get('path') or '').replace('\\', '/').strip('/')
        lowered = path.lower()
        if not path or path in seen:
            continue
        if not lowered.endswith(('.tsx', '.jsx', '.ts', '.js')):
            continue
        if '/frontend/' not in f'/{lowered}':
            continue
        if not any(token in lowered for token in ('view', 'workspace', 'panel', 'layout', 'header', 'nav', 'sidebar')):
            continue
        seen.add(path)
        extras.append(path)
        if len(extras) >= max_extra:
            break
    return extras


def _resolve_chat_context(
    project: Project,
    content: str,
    selected_file: str = '',
    selected_content: str = '',
    context_mentions=None,
    session_id: str = '',
) -> tuple[str, dict]:
    workspace_path = _chat_workspace_path(project)
    codebase_context = {}
    runtime = {}
    project_instructions = ''
    if workspace_path:
        try:
            codebase_context = build_blueprint_context(project, workspace_path)
        except Exception:
            logger.exception("Failed to build codebase context for chat in project %s", project.id)
        try:
            runtime = detect_runtime(workspace_path)
        except Exception:
            runtime = {}
        try:
            project_instructions = _read_project_instructions(project, workspace_path)
        except Exception:
            project_instructions = ''

    mentions = _dedupe_chat_mentions(
        _normalize_chat_mentions(context_mentions),
        _infer_inline_chat_mentions(content),
    )

    trace = {
        'approach': 'Resolved explicit context mentions, loaded relevant project context, and answered against the current workspace.',
        'context_mentions': mentions,
        'files_accessed': [],
        'context_sources': [],
        'commands_ran': [],
    }
    context_blocks = []
    explicit_file_mentions: list[str] = []
    broad_listing = _query_requests_broad_listing(content)
    system_explanation = _query_requests_system_explanation(content)
    retrieval_max_files = 14 if broad_listing else (10 if system_explanation else 6)
    retrieval_file_limit = 2600 if broad_listing else (2800 if system_explanation else 2200)
    if system_explanation:
        trace['approach'] = 'Resolved explicit context mentions, pulled both architectural context and concrete file evidence, and answered against the current workspace.'

    for mention in mentions:
        mention_type = mention.get('type')
        value = str(mention.get('value') or '')
        lowered = value.lower()
        if mention_type == 'special' and lowered == 'codebase':
            summary = str((codebase_context or {}).get('compact_summary') or '')
            retrieval = retrieve_relevant_files(
                codebase_context or {},
                workspace_path,
                content,
                section_key='knowledge',
                max_files=16 if broad_listing else 8,
                include_neighbors=True,
            ) if workspace_path and codebase_context else {'files': [], 'trace': []}
            codebase_parts = []
            if summary:
                codebase_parts.append(f"=== PROJECT OVERVIEW ===\n{summary[:4000]}")
            if retrieval.get('files') and workspace_path:
                codebase_parts.append("\n=== PLANNED READING LIST ===")
                chars_used = 0
                max_chars = 32000 if system_explanation else 22000
                files_included = 0
                full_primary_paths = _chat_primary_file_paths(retrieval, explicit_file_mentions, content)
                for file_item in retrieval.get('files', []):
                    if chars_used >= max_chars:
                        break
                    rel_path = str(file_item.get('path') or '')
                    if not rel_path:
                        continue
                    use_full_content = rel_path in full_primary_paths
                    file_content = read_query_relevant_file_content(
                        workspace_path,
                        rel_path,
                        query=content,
                        limit=12000 if use_full_content else (3200 if not broad_listing else 2600),
                        force_full=use_full_content,
                    )
                    if not file_content:
                        continue
                    file_summary = file_item.get('summary') or file_item.get('purpose') or ''
                    block_kind = "FULL FILE" if use_full_content else "FILE"
                    block = f"\n--- {block_kind}: {rel_path} ---\nSummary: {file_summary}\nContent:\n{file_content}\n--- END {block_kind} ---"
                    codebase_parts.append(block)
                    chars_used += len(block)
                    files_included += 1
                for item in retrieval.get('trace', [])[:20]:
                    item_path = str(item.get('path') or '')
                    trace['files_accessed'].append({
                        'path': item_path,
                        'source': item.get('source') or 'retrieval',
                        'mode': 'full' if item_path in full_primary_paths else 'chunked',
                        'reason': item.get('reason') or 'Selected by codebase retrieval.',
                    })
            if codebase_parts:
                context_blocks.append(f"@codebase\n" + "\n".join(codebase_parts))
                trace['context_sources'].append({'label': '@codebase', 'detail': f'Used manifest-backed retrieval plus contents of {files_included} planned files.'})
        elif mention_type == 'special' and lowered == 'currentfile':
            if selected_file:
                explicit_file_mentions.append(selected_file)
                if selected_content:
                    context_blocks.append(f"@currentFile `{selected_file}`\n{selected_content}")
                    trace['files_accessed'].append({'path': selected_file, 'source': 'current_file', 'reason': 'Explicit current file context requested.'})
                else:
                    current_block, current_summary = _lazy_chat_file_context(workspace_path, selected_file, codebase_context, limit=5000)
                    if current_block:
                        context_blocks.append(f"@currentFile\n{current_block}")
                        trace['files_accessed'].append({
                            'path': selected_file,
                            'source': 'lazy_file',
                            'reason': 'Explicit current file context requested, loaded directly from the workspace on demand.',
                        })
                        if current_summary and not _cached_file_summary(codebase_context, selected_file):
                            trace['context_sources'].append({'label': '@currentFile', 'detail': 'Loaded a file on demand even though it was not part of the cached blueprint index.'})
        elif mention_type == 'special' and lowered == 'readme':
            if workspace_path:
                doc_files = ['README.md', 'CONTRIBUTING.md', 'SECURITY.md', 'VISION.md', 'AGENTS.md']
                doc_chunks = []
                for rel_path in doc_files:
                    excerpt = _safe_read_workspace_file(workspace_path, rel_path, limit=2500)
                    if not excerpt:
                        continue
                    doc_chunks.append(f"## {rel_path}\n{excerpt}")
                    trace['files_accessed'].append({'path': rel_path, 'source': 'docs', 'reason': 'Explicit root documentation context requested.'})
                if doc_chunks:
                    context_blocks.append("@readme\n" + "\n\n".join(doc_chunks))
                    trace['context_sources'].append({'label': '@readme', 'detail': 'Loaded root documentation and contributor guidance files.'})
        elif mention_type == 'special' and lowered == 'rules':
            if project_instructions:
                context_blocks.append(f"@rules\n{project_instructions[:4000]}")
                trace['context_sources'].append({'label': '@rules', 'detail': 'Loaded workspace rules and project instruction files.'})
        elif mention_type == 'special' and lowered == 'conversation':
            grouped_sessions, _ = _group_project_chat_sessions(project)
            recent = [
                {'role': item.get('role'), 'content': item.get('content')}
                for item in grouped_sessions.get(session_id or LEGACY_CHAT_SESSION_ID, [])[-8:]
            ]
            if recent:
                history_text = "\n".join(f"{item['role']}: {item['content'][:500]}" for item in recent)
                context_blocks.append(f"@conversation\n{history_text}")
                trace['context_sources'].append({'label': '@conversation', 'detail': 'Loaded recent chat history from the active session.'})
        elif mention_type == 'special' and lowered == 'terminal':
            if runtime:
                context_blocks.append(f"@terminal\n{json.dumps(runtime, indent=2)[:3000]}")
                trace['context_sources'].append({'label': '@terminal', 'detail': 'Loaded detected runtime command, preview status, and process state.'})
        elif mention_type == 'folder':
            folder_block, evidence = _folder_context_block(codebase_context, value)
            if folder_block:
                context_blocks.append(f"@{value}\n{folder_block}")
                trace['files_accessed'].extend(evidence)
        elif mention_type == 'file' and workspace_path:
            explicit_file_mentions.append(value)
            file_block, file_summary = _lazy_chat_file_context(workspace_path, value, codebase_context, limit=5000)
            if file_block:
                context_blocks.append(f"@{value}\n{file_block}")
                trace['files_accessed'].append({
                    'path': value,
                    'source': 'lazy_file',
                    'reason': 'Explicit file mention requested and loaded directly from the workspace on demand.',
                })
                if file_summary and not _cached_file_summary(codebase_context, value):
                    trace['context_sources'].append({'label': f'@{value}', 'detail': 'Loaded a skipped or uncached file lazily from disk for this chat turn.'})

    if workspace_path and codebase_context and not any(block.startswith('@codebase') for block in context_blocks):
        if _looks_like_ui_style_question(content) or _looks_like_ui_redesign_request(content):
            for rel_path in _ui_style_candidate_paths(codebase_context, explicit_file_mentions):
                if rel_path not in explicit_file_mentions:
                    explicit_file_mentions.append(rel_path)
        retrieval = retrieve_relevant_files(
            codebase_context,
            workspace_path,
            content,
            explicit_paths=explicit_file_mentions,
            max_files=retrieval_max_files,
            include_neighbors=True,
        )
        if _looks_like_ui_style_question(content):
            existing_ui_paths = [str(item.get('path') or '') for item in trace['files_accessed']]
            for rel_path in _ui_style_candidate_paths(codebase_context, existing_ui_paths):
                trace['files_accessed'].append({
                    'path': rel_path,
                    'source': 'ui_candidate',
                    'mode': 'candidate',
                    'reason': 'Added as a likely UI surface for a styling question.',
                })
        planned_blocks = []
        full_primary_paths = _chat_primary_file_paths(retrieval, explicit_file_mentions, content)
        for item in retrieval.get('files', [])[:retrieval_max_files]:
            rel_path = str(item.get('path') or '')
            if not rel_path:
                continue
            use_full_content = rel_path in full_primary_paths
            file_content = read_query_relevant_file_content(
                workspace_path,
                rel_path,
                query=content,
                limit=12000 if use_full_content else retrieval_file_limit,
                force_full=use_full_content,
            )
            if not file_content:
                continue
            planned_blocks.append(
                f"--- {'FULL FILE' if use_full_content else 'FILE'}: {rel_path} ---\n"
                f"Summary: {item.get('summary') or item.get('purpose') or 'No summary available.'}\n"
                f"Content:\n{file_content}\n"
                f"--- END {'FULL FILE' if use_full_content else 'FILE'} ---"
            )
        if planned_blocks:
            context_blocks.append("@codebase-planned\n" + "\n\n".join(planned_blocks))
            trace['context_sources'].append({'label': '@codebase-planned', 'detail': f"Planned and loaded {len(planned_blocks)} files based on the current question before answering."})
            existing_paths = {str(item.get('path') or '') for item in trace['files_accessed']}
            for item in retrieval.get('trace', [])[:16]:
                rel_path = str(item.get('path') or '')
                if rel_path in existing_paths:
                    continue
                trace['files_accessed'].append({
                    'path': rel_path,
                    'source': item.get('source') or 'retrieval',
                    'mode': 'full' if rel_path in full_primary_paths else 'chunked',
                    'reason': item.get('reason') or 'Selected by manifest-backed retrieval for this chat turn.',
                })

    return "\n\n".join(block for block in context_blocks if block).strip(), trace


def _build_chat_trace_from_changes(
    applied_changes: dict | None,
    context_trace: dict | None,
    memory_context: dict | None,
) -> dict:
    applied_changes = applied_changes or {}
    context_trace = dict(context_trace or {})
    memory_context = memory_context or {}
    commands_ran = list(context_trace.get('commands_ran') or [])
    for result in applied_changes.get('validation_results') or []:
        commands_ran.append({
            'command': result.get('command'),
            'status': 'passed' if result.get('success') else 'failed',
            'detail': str(result.get('stderr') or result.get('stdout') or '')[:280],
        })

    trace = {
        'approach': context_trace.get('approach') or 'Applied a workspace change request and validated the result.',
        'context_mentions': context_trace.get('context_mentions') or [],
        'context_sources': context_trace.get('context_sources') or [],
        'files_accessed': [
            *list(context_trace.get('files_accessed') or []),
            *[
                {'path': path, 'source': 'implementation_context', 'reason': 'Used as code context while preparing the edit plan.'}
                for path in (applied_changes.get('context_files') or [])[:12]
            ],
        ],
        'commands_ran': commands_ran,
        'plan': applied_changes.get('plan') or {},
        'applied_files': applied_changes.get('applied_files') or [],
        'review': applied_changes.get('review') or {},
        'semantic_hits': [
            {
                'path': item.get('file_path'),
                'symbol': item.get('symbol'),
            }
            for item in (memory_context.get('semantic_hits') or [])[:8]
        ],
    }
    if applied_changes.get('changeset_id'):
        trace['changeset_id'] = applied_changes.get('changeset_id')
    if isinstance(applied_changes.get('undo'), dict):
        trace['undo'] = applied_changes.get('undo')
        trace['undo_available'] = bool((applied_changes.get('undo') or {}).get('available'))
    return trace


def _record_chat_changes(
    project: Project,
    request_text: str,
    workspace_path: Path,
    previous_contents: dict | None,
    applied_files: list[str],
    *,
    ai_review: dict | None = None,
):
    if not applied_files:
        return None

    before_contents = dict(previous_contents or {})
    checkpoint_review = dict(ai_review or {})
    checkpoint_id = str(((checkpoint_review.get('checkpoint') or {}).get('id')) or '').strip()
    if checkpoint_id:
        checkpoint_contents = snapshot_previous_contents(str(project.id), checkpoint_id, applied_files)
        for rel_path, content in checkpoint_contents.items():
            before_contents.setdefault(rel_path, content)

    changeset = Changeset.objects.create(
        project=project,
        title=(request_text[:252] + '...') if len(request_text) > 255 else request_text,
        description=request_text,
        status='approved',
        ai_review=checkpoint_review or {'source': 'chat'},
    )

    for rel_path in applied_files:
        new_path = workspace_path / rel_path
        before = before_contents.get(rel_path, "")
        after = ""
        action = 'modified'

        if new_path.exists():
            after = new_path.read_text(encoding='utf-8', errors='ignore')
            action = 'modified' if rel_path in before_contents else 'added'
        else:
            action = 'deleted'

        diff = ''.join(
            unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f'a/{rel_path}',
                tofile=f'b/{rel_path}',
            )
        )

        FileDiff.objects.create(
            changeset=changeset,
            file_path=rel_path,
            diff_content=diff or f'{action}: {rel_path}',
            action=action,
        )

    return changeset


def apply_chat_changes(
    project: Project,
    request_text: str,
    selected_file: str = "",
    selected_content: str = "",
    *,
    request_attachments: list[dict] | None = None,
    checkpoint: dict | None = None,
    chat_mode: str | None = None,
    changeset_source: str = 'chat',
) -> dict:
    result = _run_multi_agent_implementation(
        project=project,
        request_title="Chat-requested update",
        request_text=request_text,
        spec={
            "source": "chat",
            "request": request_text,
            "selected_file": selected_file or None,
            "instruction": "Apply the requested changes directly in code. Update related UI, logic, styles, routing, and supporting files so the project stays consistent and runnable.",
        },
        selected_file=selected_file,
        selected_content=selected_content,
        request_attachments=request_attachments,
        checkpoint=checkpoint,
        chat_mode=chat_mode,
        changeset_source=changeset_source,
    )
    return {
        "applied_files": result.get("applied_files", []),
        "count": result.get("count", 0),
        "plan": result.get("plan", {}),
        "review": result.get("review", {}),
        "validation_results": result.get("validation_results", []),
        "context_files": result.get("context_files", []),
        "changeset_id": result.get("changeset_id"),
        "undo": result.get("undo"),
    }


def run_ai_test_simulation(feature: Feature, tech_stack):
    try:
        from agents.core.base import BaseAgent

        agent = BaseAgent(
            role="QA Lead",
            system_instruction="You are a QA lead. Evaluate feature specs and simulate test results. Always return valid JSON.",
            ai_config=_project_ai_config(feature.project),
        )
        prompt = f"""Evaluate this feature and simulate test results.

Feature: {feature.title}
Description: {feature.description}
Spec: {json.dumps(feature.spec, indent=2) if feature.spec else 'No spec'}
Tech Stack: {', '.join(tech_stack)}

Return ONLY valid JSON with overall_status, score, summary, tests, coverage, suggestions, and blockers."""

        result = agent.generate(prompt)
        return agent.parse_json(result)
    except Exception as exc:
        return {
            "overall_status": "warning",
            "score": 0,
            "summary": f"Test simulation failed: {str(exc)}",
            "tests": [],
            "coverage": 0,
            "suggestions": [],
            "blockers": [],
        }


