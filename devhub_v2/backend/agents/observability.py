"""Structured agent execution events for logging and SSE streaming."""

from __future__ import annotations

import logging
import queue
import time
from typing import Any, Callable

logger = logging.getLogger('devhub.agents')


class AgentObserver:
    """Collect and emit structured events during a single agent execution run.

    Set ``live_queue`` to a ``queue.Queue`` to receive events in real-time as
    they happen (not just after section completion).  The SSE view drains this
    queue and forwards events to the client immediately.
    """

    def __init__(self, project_id: str, run_id: str | None = None,
                 live_queue: 'queue.Queue | None' = None):
        self.project_id = project_id
        self.run_id = run_id or f'run_{int(time.time())}'
        self.events: list[dict[str, Any]] = []
        self._current_section: str = ''
        self.live_queue = live_queue

    def _emit(self, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        event = {'type': event_type, 'ts': time.time(), 'run_id': self.run_id, **data}
        self.events.append(event)
        section = data.get('section_key', '')
        detail = data.get('message') or data.get('details') or ''
        if event_type == 'extraction':
            detail = f"{data.get('extractor', '')} → {data.get('count', 0)} items"
        elif event_type == 'llm_call':
            detail = f"model={data.get('model', '?')}"
        elif event_type == 'validation':
            warnings = data.get('warnings') or []
            detail = f"{data.get('validator', '')} warnings={len(warnings)}"
        elif event_type == 'file_access':
            detail = f"{data.get('path', '')} ({data.get('chars', 0)} chars)"
        elif event_type == 'section_done':
            detail = f"{data.get('duration_s', '?')}s status={data.get('status', '?')}"
        logger.info('[AGENT:%s] %s %s', event_type.upper(), section, detail)
        # Push to live queue immediately so the SSE stream can forward it now
        if self.live_queue is not None:
            try:
                self.live_queue.put_nowait(event)
            except Exception:
                pass
        return event

    def thinking(self, section_key: str, message: str) -> dict:
        self._current_section = section_key
        return self._emit('thinking', {'section_key': section_key, 'message': message})

    def file_access(self, section_key: str, path: str, chars: int) -> dict:
        return self._emit('file_access', {'section_key': section_key, 'path': path, 'chars': chars})

    def extraction(self, section_key: str, extractor: str, count: int, details: str = '') -> dict:
        return self._emit('extraction', {
            'section_key': section_key, 'extractor': extractor, 'count': count, 'details': details,
        })

    def llm_call(self, section_key: str, model: str, prompt_tokens: int = 0, response_tokens: int = 0) -> dict:
        return self._emit('llm_call', {
            'section_key': section_key, 'model': model,
            'prompt_tokens': prompt_tokens, 'response_tokens': response_tokens,
        })

    def validation(self, section_key: str, validator: str, warnings: list[str]) -> dict:
        return self._emit('validation', {
            'section_key': section_key, 'validator': validator, 'warnings': warnings,
        })

    def section_done(self, section_key: str, duration_s: float, status: str) -> dict:
        return self._emit('section_done', {
            'section_key': section_key, 'duration_s': round(duration_s, 2), 'status': status,
        })

    def events_for_section(self, section_key: str) -> list[dict]:
        return [e for e in self.events if e.get('section_key') == section_key]
