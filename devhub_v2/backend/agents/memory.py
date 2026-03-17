import os
import re
from pathlib import Path

from agents.workspace import SKIP_DIRS
from django.db import OperationalError, ProgrammingError
from core.models import Changeset, ChatMessage, EpisodicMemory, Project, SemanticMemory, WorkingMemory

INDEXABLE_EXTENSIONS = {'.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.json', '.md'}
STOPWORDS = {
    'the', 'and', 'for', 'with', 'that', 'this', 'from', 'into', 'your', 'have', 'will',
    'were', 'been', 'http', 'https', 'file', 'files', 'code', 'user', 'using', 'used',
}
MEMORY_DB_ERRORS = (OperationalError, ProgrammingError)


def _tokenize(text: str) -> list[str]:
    return [
        token for token in re.findall(r'[a-zA-Z0-9_]+', (text or '').lower())
        if len(token) > 2 and token not in STOPWORDS
    ]


def _chunk_text(text: str, chunk_size: int = 1200, overlap: int = 160) -> list[str]:
    cleaned = (text or '').strip()
    if not cleaned:
        return []
    if len(cleaned) <= chunk_size:
        return [cleaned]

    chunks = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        chunks.append(cleaned[start:end])
        if end >= len(cleaned):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _extract_symbol(content: str) -> str:
    patterns = [
        r'^\s*class\s+([A-Za-z0-9_]+)',
        r'^\s*def\s+([A-Za-z0-9_]+)',
        r'^\s*function\s+([A-Za-z0-9_]+)',
        r'^\s*const\s+([A-Za-z0-9_]+)\s*=',
        r'^\s*export\s+default\s+function\s+([A-Za-z0-9_]+)',
    ]
    for line in (content or '').splitlines()[:80]:
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                return match.group(1)
    return ''


def _iter_workspace_files(workspace_path: Path) -> list[Path]:
    items: list[Path] = []
    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [directory for directory in dirs if directory not in SKIP_DIRS]
        for filename in files:
            path = Path(root) / filename
            if path.suffix.lower() in INDEXABLE_EXTENSIONS:
                items.append(path)
    return items


def index_semantic_memory(project: Project, workspace_path: Path, changed_paths: list[str] | None = None):
    try:
        SemanticMemory.objects.exists()
    except MEMORY_DB_ERRORS:
        return

    if changed_paths:
        target_paths = []
        for rel_path in changed_paths:
            normalized = str(rel_path).replace('\\', '/')
            try:
                SemanticMemory.objects.filter(project=project, file_path=normalized).delete()
            except MEMORY_DB_ERRORS:
                return
            candidate = workspace_path / rel_path
            if candidate.exists() and candidate.is_file() and candidate.suffix.lower() in INDEXABLE_EXTENSIONS:
                target_paths.append(candidate)
    else:
        target_paths = _iter_workspace_files(workspace_path)

    for file_path in target_paths:
        rel_path = str(file_path.relative_to(workspace_path)).replace('\\', '/')
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue

        try:
            SemanticMemory.objects.filter(project=project, file_path=rel_path).delete()
        except MEMORY_DB_ERRORS:
            return
        chunks = _chunk_text(content)
        if not chunks:
            continue

        symbol = _extract_symbol(content)
        entries = []
        for index, chunk in enumerate(chunks):
            entries.append(
                SemanticMemory(
                    project=project,
                    file_path=rel_path,
                    chunk_index=index,
                    symbol=symbol,
                    content=chunk[:2400],
                    keywords=_tokenize(f'{rel_path} {symbol} {chunk}')[:80],
                    metadata={'length': len(chunk)},
                )
            )
        try:
            SemanticMemory.objects.bulk_create(entries)
        except MEMORY_DB_ERRORS:
            return


def recall_semantic_memory(project: Project, query: str, selected_file: str = '', limit: int = 6) -> list[dict]:
    try:
        entries = list(SemanticMemory.objects.filter(project=project))
    except MEMORY_DB_ERRORS:
        return []

    query_tokens = set(_tokenize(f'{query} {selected_file}'))
    results = []
    for entry in entries:
        keywords = set(entry.keywords or [])
        overlap = len(query_tokens & keywords)
        if not overlap and selected_file and selected_file != entry.file_path:
            continue
        score = float(overlap)
        if entry.file_path == selected_file:
            score += 4.0
        elif selected_file and entry.file_path.startswith('/'.join(selected_file.split('/')[:-1])):
            score += 1.5
        if score <= 0:
            continue
        results.append({
            'file_path': entry.file_path,
            'symbol': entry.symbol,
            'content': entry.content[:800],
            'score': score,
        })

    results.sort(key=lambda item: (-item['score'], item['file_path']))
    return results[:limit]


def upsert_working_memory(project: Project, scope: str, summary: str, context: dict | None = None) -> WorkingMemory:
    try:
        memory, _ = WorkingMemory.objects.update_or_create(
            project=project,
            scope=scope,
            defaults={'summary': summary, 'context': context or {}},
        )
        return memory
    except MEMORY_DB_ERRORS:
        return None


def get_working_memory(project: Project, scope: str = 'implementation') -> str:
    try:
        memory = WorkingMemory.objects.filter(project=project, scope=scope).first()
        return memory.summary if memory else ''
    except MEMORY_DB_ERRORS:
        return ''


def record_episode(
    project: Project,
    memory_type: str,
    title: str,
    summary: str,
    related_files: list[str] | None = None,
    metadata: dict | None = None,
) -> EpisodicMemory:
    try:
        return EpisodicMemory.objects.create(
            project=project,
            memory_type=memory_type,
            title=title,
            summary=summary,
            related_files=related_files or [],
            metadata=metadata or {},
        )
    except MEMORY_DB_ERRORS:
        return None


def compress_recent_activity(project: Project, limit: int = 10) -> str:
    lines = [f'Project: {project.name}']

    try:
        recent_episodes = EpisodicMemory.objects.filter(project=project).order_by('-created_at')[:limit]
        if recent_episodes:
            lines.append('Recent Episodes:')
            for episode in recent_episodes:
                lines.append(f'- {episode.memory_type}: {episode.title} :: {episode.summary[:180]}')
    except MEMORY_DB_ERRORS:
        return f'Project: {project.name}'

    try:
        recent_changes = Changeset.objects.filter(project=project).order_by('-created_at')[:limit]
        if recent_changes:
            lines.append('Recent Changesets:')
            for changeset in recent_changes:
                lines.append(f'- {changeset.title} [{changeset.status}]')
    except MEMORY_DB_ERRORS:
        pass

    try:
        recent_chat = ChatMessage.objects.filter(project=project).order_by('-created_at')[:limit]
        if recent_chat:
            lines.append('Recent Chat Themes:')
            for message in reversed(recent_chat):
                lines.append(f'- {message.role}: {message.content[:140]}')
    except MEMORY_DB_ERRORS:
        pass

    summary = '\n'.join(lines)[:5000]
    upsert_working_memory(project, 'implementation', summary, {'source': 'compress_recent_activity'})
    return summary


def build_memory_context(project: Project, query: str, selected_file: str = '') -> dict:
    working_summary = get_working_memory(project) or compress_recent_activity(project)
    try:
        episodes = EpisodicMemory.objects.filter(project=project).order_by('-created_at')[:6]
        episodic_summary = '\n'.join(
            f'- {item.memory_type}: {item.title} :: {item.summary[:180]}'
            for item in episodes
        ) or 'No episodic memory yet.'
    except MEMORY_DB_ERRORS:
        episodic_summary = 'Episodic memory unavailable until migrations are applied.'
    semantic_hits = recall_semantic_memory(project, query, selected_file=selected_file)
    semantic_summary = '\n'.join(
        f"- {item['file_path']} ({item.get('symbol') or 'context'}): {item['content'][:180]}"
        for item in semantic_hits
    ) or 'No semantic matches yet.'
    return {
        'working_summary': working_summary,
        'episodic_summary': episodic_summary,
        'semantic_hits': semantic_hits,
        'semantic_summary': semantic_summary,
    }
