import base64
import json
import re

from django.utils import timezone

from agents.core.base import describe_image_attachments
from core.models import Changeset, Project

from api.project_utils import (
    CHAT_ATTACHMENT_ALLOWED_MIME_TYPES,
    CHAT_ATTACHMENT_MAX_BYTES,
    CHAT_ATTACHMENT_MAX_COUNT,
    CHAT_ATTACHMENT_MAX_TOTAL_BYTES,
)


def _parse_json_body(request):
    if not request.body:
        return {}
    return json.loads(request.body)


def _chat_attachment_data_parts(data_url: str) -> tuple[str, str]:
    value = str(data_url or "").strip()
    if not value.startswith("data:") or ";base64," not in value:
        raise ValueError("Attachments must be base64 data URLs.")
    header, encoded = value.split(",", 1)
    mime_type = str(header[5:].replace(";base64", "")).strip().lower()
    encoded = "".join(encoded.split())
    if not mime_type or not encoded:
        raise ValueError("Attachments must include a mime type and image data.")
    return mime_type, encoded


def _normalize_chat_attachments(raw_attachments) -> list[dict]:
    if raw_attachments in (None, ""):
        return []
    if not isinstance(raw_attachments, list):
        raise ValueError("attachments must be a list.")
    if len(raw_attachments) > CHAT_ATTACHMENT_MAX_COUNT:
        raise ValueError(f"You can attach up to {CHAT_ATTACHMENT_MAX_COUNT} images per message.")

    normalized: list[dict] = []
    total_bytes = 0

    for index, item in enumerate(raw_attachments, start=1):
        if not isinstance(item, dict):
            raise ValueError("Each attachment must be an object.")

        data_url = str(item.get("data_url") or item.get("dataUrl") or "").strip()
        mime_type, encoded = _chat_attachment_data_parts(data_url)
        if mime_type not in CHAT_ATTACHMENT_ALLOWED_MIME_TYPES:
            raise ValueError("Only PNG, JPEG, WEBP, and GIF images are supported.")

        try:
            binary = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise ValueError("One of the attached images could not be decoded.") from exc

        size_bytes = len(binary)
        if size_bytes > CHAT_ATTACHMENT_MAX_BYTES:
            raise ValueError("Each attached image must be 4 MB or smaller.")

        total_bytes += size_bytes
        if total_bytes > CHAT_ATTACHMENT_MAX_TOTAL_BYTES:
            raise ValueError("The total attached image payload is too large for one message.")

        raw_name = str(item.get("name") or f"image-{index}").strip() or f"image-{index}"
        safe_name = re.sub(r"[^A-Za-z0-9._ -]+", "_", raw_name)[:120].strip(" .") or f"image-{index}"
        normalized.append(
            {
                "name": safe_name,
                "mime_type": mime_type,
                "size_bytes": size_bytes,
                "data_url": f"data:{mime_type};base64,{encoded}",
            }
        )

    return normalized


def _chat_request_text(content: str, attachments: list[dict] | None = None, *, include_attachment_inventory: bool = False) -> str:
    text = str(content or "").strip()
    if not text and attachments:
        text = "Please inspect the attached image and use it as the primary context for this request."
        if len(attachments) != 1:
            text = "Please inspect the attached images and use them as the primary context for this request."

    if include_attachment_inventory:
        attachment_summary = describe_image_attachments(attachments)
        if attachment_summary:
            text = f"{text}\n\n{attachment_summary}" if text else attachment_summary
    return text


def _chat_message_attachments(item: dict | None) -> list[dict]:
    metadata = {}
    if isinstance(item, dict):
        metadata = item if "attachments" in item else dict(item.get("metadata") or {})
    attachments = metadata.get("attachments")
    if not isinstance(attachments, list):
        return []
    return [attachment for attachment in attachments if isinstance(attachment, dict) and attachment.get("data_url")]


def _chat_checkpoint_review_payload(checkpoint: dict | None, *, source: str, chat_mode: str | None, undo_label: str = 'Undo') -> dict:
    payload = {
        'source': source,
        'chat_mode': chat_mode or 'auto',
    }
    if not checkpoint:
        return payload
    payload['checkpoint'] = {
        'id': str(checkpoint.get('id') or ''),
        'created_at': checkpoint.get('created_at'),
        'label': checkpoint.get('label'),
        'source': checkpoint.get('source'),
    }
    payload['undo'] = {
        'available': True,
        'checkpoint_id': str(checkpoint.get('id') or ''),
        'label': undo_label or 'Undo',
    }
    return payload


def _chat_undo_payload_from_review(changeset_id: str, ai_review: dict | None) -> dict | None:
    ai_review = dict(ai_review or {})
    undo = dict(ai_review.get('undo') or {})
    checkpoint = dict(ai_review.get('checkpoint') or {})
    checkpoint_id = str(undo.get('checkpoint_id') or checkpoint.get('id') or '').strip()
    if not checkpoint_id:
        return None
    return {
        'available': bool(undo.get('available')),
        'changeset_id': str(changeset_id),
        'checkpoint_id': checkpoint_id,
        'label': str(undo.get('label') or 'Undo'),
        'undone_at': undo.get('undone_at'),
        'restored_by_changeset_id': undo.get('restored_by_changeset_id'),
        'source': str(ai_review.get('source') or 'chat'),
    }


def _chat_changeset_trace_metadata(changeset: Changeset | None) -> dict:
    if not changeset:
        return {}
    payload = {'changeset_id': str(changeset.id)}
    undo = _chat_undo_payload_from_review(str(changeset.id), changeset.ai_review)
    if undo:
        payload['undo'] = undo
        payload['undo_available'] = bool(undo.get('available'))
    return payload


def _changeset_by_id(project: Project, changeset_id: str) -> Changeset | None:
    normalized = str(changeset_id or '').strip()
    if not normalized:
        return None
    try:
        return Changeset.objects.filter(project=project, id=normalized).first()
    except Exception:
        return None


def _mark_changeset_undone(changeset: Changeset, restoring_changeset: Changeset | None = None) -> None:
    review = dict(changeset.ai_review or {})
    undo = dict(review.get('undo') or {})
    undo.update({
        'available': False,
        'checkpoint_id': str(undo.get('checkpoint_id') or (review.get('checkpoint') or {}).get('id') or ''),
        'label': str(undo.get('label') or 'Undo'),
        'undone_at': timezone.now().isoformat(),
        'restored_by_changeset_id': str(restoring_changeset.id) if restoring_changeset else None,
    })
    review['undo'] = undo
    changeset.ai_review = review
    changeset.save(update_fields=['ai_review'])
