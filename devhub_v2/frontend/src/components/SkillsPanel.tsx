import { useEffect, useState } from 'react';
import { BookOpen, ChevronDown, ChevronRight, Pin, PinOff, Plus, Trash2, X, Zap } from 'lucide-react';

const API = 'http://localhost:8000/api';

type GlobalSkill = {
  name: string;
  slug: string;
  description: string;
  rel_path: string;
  content?: string;
};

type Props = {
  isWorkspaceMode?: boolean;
  pinnedSlugs: string[];
  onPinToggle: (slug: string) => void;
  onCreateClick: () => void;
  onClose: () => void;
};

export default function SkillsPanel({ isWorkspaceMode, pinnedSlugs, onPinToggle, onCreateClick, onClose }: Props) {
  const [skills, setSkills] = useState<GlobalSkill[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [skillDetail, setSkillDetail] = useState<Record<string, GlobalSkill>>({});
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const dark = Boolean(isWorkspaceMode);

  useEffect(() => {
    setLoading(true);
    fetch(`${API}/skills/`)
      .then((r) => r.json())
      .then((d) => setSkills(d.skills || []))
      .catch(() => setSkills([]))
      .finally(() => setLoading(false));
  }, []);

  const toggleExpand = async (slug: string) => {
    if (expanded === slug) { setExpanded(null); return; }
    setExpanded(slug);
    if (!skillDetail[slug]) {
      try {
        const r = await fetch(`${API}/skills/${slug}/`);
        const d = await r.json();
        if (d.skill) setSkillDetail((prev) => ({ ...prev, [slug]: d.skill }));
      } catch {}
    }
  };

  const deleteSkill = async (slug: string) => {
    try {
      await fetch(`${API}/skills/${slug}/`, { method: 'DELETE' });
      setSkills((prev) => prev.filter((s) => s.slug !== slug));
      setDeleteConfirm(null);
      if (expanded === slug) setExpanded(null);
    } catch {}
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        overflow: 'hidden',
        borderRadius: 16,
        border: `1px solid ${dark ? 'rgba(255,255,255,0.1)' : '#e2e8f0'}`,
        background: dark ? '#1a1a1e' : '#ffffff',
        boxShadow: dark ? '0 24px 48px rgba(0,0,0,0.6)' : '0 12px 32px rgba(0,0,0,0.12)',
        color: dark ? '#e2e8f0' : '#1e293b',
      }}
    >
      {/* ── Header ─────────────────────────────────────── */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '10px 12px',
        borderBottom: `1px solid ${dark ? 'rgba(255,255,255,0.08)' : '#e2e8f0'}`,
        flexShrink: 0,
        background: dark ? '#141416' : '#f8fafc',
      }}>
        <Zap style={{ width: 14, height: 14, color: '#d9a4b2', flexShrink: 0 }} />
        <span style={{ flex: 1, fontSize: 12, fontWeight: 700, color: dark ? '#f1f5f9' : '#1e293b' }}>
          Global Skills
          <span style={{ marginLeft: 6, fontSize: 10, fontWeight: 400, color: dark ? '#64748b' : '#94a3b8' }}>
            ({skills.length})
          </span>
        </span>
        <button
          type="button"
          onClick={onCreateClick}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 4,
            padding: '4px 8px', borderRadius: 8, fontSize: 10, fontWeight: 600,
            border: `1px solid ${dark ? 'rgba(255,255,255,0.12)' : '#cbd5e1'}`,
            background: dark ? 'rgba(255,255,255,0.06)' : '#f1f5f9',
            color: dark ? '#cbd5e1' : '#475569',
            cursor: 'pointer',
          }}
        >
          <Plus style={{ width: 11, height: 11 }} />
          New
        </button>
        <button
          type="button"
          onClick={onClose}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            width: 24, height: 24, borderRadius: 6, border: 'none', cursor: 'pointer',
            background: 'transparent',
            color: dark ? '#64748b' : '#94a3b8',
          }}
        >
          <X style={{ width: 14, height: 14 }} />
        </button>
      </div>

      {/* ── Pinned strip ───────────────────────────────── */}
      {pinnedSlugs.length > 0 && (
        <div style={{
          padding: '8px 12px',
          borderBottom: `1px solid ${dark ? 'rgba(255,255,255,0.06)' : '#f1f5f9'}`,
          flexShrink: 0,
        }}>
          <p style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: dark ? '#475569' : '#94a3b8', marginBottom: 6 }}>
            Always active
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {pinnedSlugs.map((slug) => {
              const sk = skills.find((s) => s.slug === slug);
              return (
                <button
                  key={slug}
                  type="button"
                  onClick={() => onPinToggle(slug)}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: 4,
                    padding: '2px 8px', borderRadius: 999, fontSize: 10, fontWeight: 500,
                    border: '1px solid rgba(217,164,178,0.3)',
                    background: 'rgba(112,67,79,0.25)',
                    color: '#d9a4b2', cursor: 'pointer',
                  }}
                >
                  {sk?.name || slug}
                  <X style={{ width: 10, height: 10 }} />
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Skill list ─────────────────────────────────── */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 8, display: 'flex', flexDirection: 'column', gap: 4, minHeight: 0 }}>
        {loading && (
          <p style={{ textAlign: 'center', padding: '24px 0', fontSize: 11, color: dark ? '#475569' : '#94a3b8' }}>
            Loading skills…
          </p>
        )}
        {!loading && skills.length === 0 && (
          <p style={{ textAlign: 'center', padding: '24px 0', fontSize: 11, color: dark ? '#475569' : '#94a3b8' }}>
            No skills found.
          </p>
        )}

        {skills.map((skill) => {
          const isPinned = pinnedSlugs.includes(skill.slug);
          const isOpen = expanded === skill.slug;
          const detail = skillDetail[skill.slug];

          return (
            <div
              key={skill.slug}
              style={{
                borderRadius: 10,
                border: `1px solid ${isPinned ? 'rgba(217,164,178,0.3)' : dark ? 'rgba(255,255,255,0.07)' : '#e2e8f0'}`,
                background: dark ? (isPinned ? 'rgba(112,67,79,0.15)' : '#1e1e22') : (isPinned ? '#fdf2f4' : '#f8fafc'),
                overflow: 'hidden',
              }}
            >
              {/* Card header */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 10px' }}>
                {/* expand chevron */}
                <button
                  type="button"
                  onClick={() => toggleExpand(skill.slug)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2, flexShrink: 0, display: 'flex' }}
                >
                  {isOpen
                    ? <ChevronDown style={{ width: 12, height: 12, color: dark ? '#64748b' : '#94a3b8' }} />
                    : <ChevronRight style={{ width: 12, height: 12, color: dark ? '#64748b' : '#94a3b8' }} />}
                </button>

                {/* Skill name — primary label */}
                <span style={{
                  flex: 1,
                  minWidth: 0,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  fontSize: 12,
                  fontWeight: 700,
                  color: dark ? '#f1f5f9' : '#1e293b',
                }}>
                  {skill.name}
                </span>

                {/* Pin button */}
                <button
                  type="button"
                  onClick={() => onPinToggle(skill.slug)}
                  title={isPinned ? 'Unpin' : 'Pin — always active'}
                  style={{
                    background: isPinned ? 'rgba(112,67,79,0.3)' : 'none',
                    border: isPinned ? '1px solid rgba(217,164,178,0.3)' : 'none',
                    borderRadius: 6,
                    cursor: 'pointer',
                    padding: 4,
                    display: 'flex',
                    flexShrink: 0,
                    color: isPinned ? '#d9a4b2' : dark ? '#475569' : '#94a3b8',
                  }}
                >
                  {isPinned
                    ? <PinOff style={{ width: 11, height: 11 }} />
                    : <Pin style={{ width: 11, height: 11 }} />}
                </button>

                {/* Delete */}
                {deleteConfirm === skill.slug ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
                    <button
                      type="button"
                      onClick={() => deleteSkill(skill.slug)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 9, fontWeight: 700, color: '#f87171', padding: '2px 4px' }}
                    >
                      Delete
                    </button>
                    <button
                      type="button"
                      onClick={() => setDeleteConfirm(null)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 9, color: dark ? '#475569' : '#94a3b8', padding: '2px 4px' }}
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setDeleteConfirm(skill.slug)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4, display: 'flex', flexShrink: 0, color: dark ? '#374151' : '#cbd5e1' }}
                  >
                    <Trash2 style={{ width: 11, height: 11 }} />
                  </button>
                )}
              </div>

              {/* Description — always visible */}
              <p style={{
                margin: 0,
                padding: '0 10px 8px 10px',
                fontSize: 10,
                lineHeight: 1.5,
                color: dark ? '#64748b' : '#64748b',
              }}>
                {skill.description.slice(0, 110)}{skill.description.length > 110 ? '…' : ''}
              </p>

              {/* Expanded body */}
              {isOpen && (
                <div style={{
                  borderTop: `1px solid ${dark ? 'rgba(255,255,255,0.05)' : '#e2e8f0'}`,
                  padding: '8px 10px',
                }}>
                  {detail
                    ? <pre style={{
                        margin: 0,
                        maxHeight: 180,
                        overflowY: 'auto',
                        whiteSpace: 'pre-wrap',
                        fontSize: 9.5,
                        lineHeight: 1.6,
                        color: dark ? '#64748b' : '#475569',
                        fontFamily: 'monospace',
                      }}>
                        {(detail.content || '').slice(0, 1600)}
                        {(detail.content?.length || 0) > 1600 ? '\n…' : ''}
                      </pre>
                    : <span style={{ fontSize: 10, color: dark ? '#475569' : '#94a3b8' }}>Loading…</span>
                  }
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* ── Footer ─────────────────────────────────────── */}
      <div style={{
        padding: '8px 12px',
        borderTop: `1px solid ${dark ? 'rgba(255,255,255,0.06)' : '#e2e8f0'}`,
        flexShrink: 0,
        background: dark ? '#141416' : '#f8fafc',
      }}>
        <p style={{ margin: 0, fontSize: 9, color: dark ? '#374151' : '#94a3b8', display: 'flex', alignItems: 'center', gap: 4 }}>
          <BookOpen style={{ width: 10, height: 10, flexShrink: 0 }} />
          Pinned = always on. Skills also auto-activate per request.
        </p>
      </div>
    </div>
  );
}
