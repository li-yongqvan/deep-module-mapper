/**
 * Recomposition canvas toolbar (issue #10): create a module, save to
 * localStorage, load the saved design, reset to the manifest-derived
 * suggested grouping. Floats over the canvas top-left.
 */
import type { CSSProperties } from 'react';

export interface RecomposeToolbarProps {
  onCreateModule: () => void;
  onSave: () => void;
  onLoad: () => void;
  onReset: () => void;
  /** Transient feedback like "已保存". */
  feedback?: string;
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

export default function RecomposeToolbar({
  onCreateModule,
  onSave,
  onLoad,
  onReset,
  feedback,
}: RecomposeToolbarProps) {
  return (
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
  );
}
