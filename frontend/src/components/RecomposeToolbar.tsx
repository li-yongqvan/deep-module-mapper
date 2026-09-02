/**
 * Recomposition canvas toolbar (issue #10 + #21): create a module, save to
 * localStorage, load the saved design, reset to the manifest-derived
 * suggested grouping, and show structural diagnostics counters. Floats over
 * the canvas top-left.
 */
import { useEffect, useRef, useState, type CSSProperties } from 'react';
import type { ModuleFindings } from '../lib/recompose/detect';

export interface RecomposeToolbarProps {
  onCreateModule: () => void;
  onSave: () => void;
  onLoad: () => void;
  onReset: () => void;
  /** Transient feedback like "已保存". */
  feedback?: string;
  /** Issue #21 structural diagnostics. */
  diagnostics?: ModuleFindings;
  /** Issue #21: select + center a module from the diagnostics list. */
  onSelectModule?: (moduleId: string) => void;
}

const toolbarStyle: CSSProperties = {
  position: 'absolute',
  top: 12,
  left: 12,
  zIndex: 5,
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  padding: '6px 8px',
  background: 'rgba(15, 23, 42, 0.85)',
  border: '1px solid var(--border, #475569)',
  borderRadius: 8,
  boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
};

const buttonStyle: CSSProperties = {
  padding: '4px 10px',
  borderRadius: 6,
  border: '1px solid var(--border, #475569)',
  background: 'transparent',
  color: 'var(--text-2, #94a3b8)',
  fontSize: 11,
  cursor: 'pointer',
};

const primaryStyle: CSSProperties = {
  ...buttonStyle,
  background: 'var(--accent, #38bdf8)',
  border: '1px solid var(--accent, #38bdf8)',
  color: '#000',
  fontWeight: 600,
};

const feedbackStyle: CSSProperties = {
  fontSize: 11,
  color: 'var(--good, #34d399)',
  marginLeft: 4,
};

const pillBarStyle: CSSProperties = {
  display: 'flex',
  gap: 6,
  marginTop: 8,
};

function pillStyle(color: string, active: boolean, clickable: boolean): CSSProperties {
  return {
    padding: '4px 10px',
    borderRadius: 6,
    border: `1px solid ${color}`,
    background: active ? `${color}33` : 'rgba(15, 23, 42, 0.85)',
    color,
    fontSize: 11,
    cursor: clickable ? 'pointer' : 'default',
    opacity: clickable ? 1 : 0.5,
  };
}

const listStyle: CSSProperties = {
  position: 'absolute',
  top: 'calc(100% + 6px)',
  left: 0,
  margin: 0,
  padding: '6px 0',
  listStyle: 'none',
  minWidth: 180,
  background: 'rgba(15, 23, 42, 0.95)',
  border: '1px solid var(--border, #475569)',
  borderRadius: 8,
  boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
  zIndex: 10,
};

const listItemStyle: CSSProperties = {
  margin: 0,
  padding: 0,
};

const listButtonStyle: CSSProperties = {
  width: '100%',
  textAlign: 'left',
  padding: '5px 12px',
  border: 'none',
  background: 'transparent',
  color: 'var(--text, #f8fafc)',
  fontSize: 11,
  cursor: 'pointer',
};

export default function RecomposeToolbar({
  onCreateModule,
  onSave,
  onLoad,
  onReset,
  feedback,
  diagnostics,
  onSelectModule,
}: RecomposeToolbarProps) {
  const [expanded, setExpanded] = useState<'cycle' | 'orphan' | 'third-party-only' | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setExpanded(null);
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setExpanded(null);
    }
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  const pills = [
    {
      key: 'cycle' as const,
      label: '在环里',
      count: diagnostics?.count.cycles ?? 0,
      findings: diagnostics?.cycles ?? [],
      color: 'var(--warn, #f87171)',
    },
    {
      key: 'orphan' as const,
      label: '孤立',
      count: diagnostics?.count.orphan ?? 0,
      findings: diagnostics?.orphans ?? [],
      color: 'var(--text-2, #94a3b8)',
    },
    {
      key: 'third-party-only' as const,
      label: '仅连第三方',
      count: diagnostics?.count.thirdPartyOnly ?? 0,
      findings: diagnostics?.thirdPartyOnly ?? [],
      color: 'var(--mid, #fbbf24)',
    },
  ];

  return (
    <div ref={wrapperRef} style={{ position: 'absolute', top: 12, left: 12, zIndex: 5 }}>
      <div style={toolbarStyle} className="recompose-toolbar" role="toolbar" aria-label="重组画布工具">
        <button style={primaryStyle} onClick={onCreateModule}>
          ＋ 新建模块
        </button>
        <button style={buttonStyle} onClick={onSave}>
          保存
        </button>
        <button style={buttonStyle} onClick={onLoad}>
          加载
        </button>
        <button style={buttonStyle} onClick={onReset}>
          重置为建议分组
        </button>
        {feedback && <span style={feedbackStyle}>{feedback}</span>}
      </div>
      {diagnostics && (
        <div style={pillBarStyle}>
          {pills.map((pill) => {
            const clickable = pill.count > 0 && onSelectModule != null;
            return (
              <div key={pill.key} style={{ position: 'relative' }}>
                <button
                  style={pillStyle(pill.color, expanded === pill.key, clickable)}
                  disabled={!clickable}
                  onClick={() => setExpanded(expanded === pill.key ? null : pill.key)}
                  aria-expanded={expanded === pill.key}
                >
                  {pill.label} {pill.count}
                </button>
                {expanded === pill.key && clickable && (
                  <ul style={listStyle}>
                    {pill.findings.flatMap((finding) =>
                      finding.subject.moduleIds.map((id) => (
                        <li key={id} style={listItemStyle}>
                          <button
                            style={listButtonStyle}
                            onClick={() => {
                              setExpanded(null);
                              onSelectModule?.(id);
                            }}
                          >
                            [{pill.label}] {id}
                          </button>
                        </li>
                      )),
                    )}
                  </ul>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
