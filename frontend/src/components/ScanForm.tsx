/**
 * Scan form: local repo path input + submit. Empty paths cannot be
 * submitted (invariant #4).
 */
import { useState, type CSSProperties, type FormEvent } from 'react';

interface ScanFormProps {
  onSubmit: (path: string) => void;
  disabled?: boolean;
}

export default function ScanForm({ onSubmit, disabled }: ScanFormProps) {
  const [path, setPath] = useState('');

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = path.trim();
    if (trimmed && !disabled) onSubmit(trimmed);
  }

  return (
    <form
      onSubmit={handleSubmit}
      style={{ display: 'flex', gap: 8, flex: 1, minWidth: 0 }}
    >
      <input
        aria-label="代码目录路径"
        type="text"
        value={path}
        onChange={(e) => setPath(e.target.value)}
        placeholder="输入本地代码目录路径，如 parser/tests/fixtures/sample_pkg"
        style={inputStyle}
      />
      <button type="submit" disabled={disabled || !path.trim()} style={buttonStyle}>
        扫描
      </button>
    </form>
  );
}

const inputStyle: CSSProperties = {
  flex: 1,
  padding: '8px 12px',
  borderRadius: 6,
  border: '1px solid var(--border, #475569)',
  background: 'var(--panel-2, #334155)',
  color: 'var(--text, #f8fafc)',
  fontSize: 13,
  minWidth: 0,
};

const buttonStyle: CSSProperties = {
  padding: '8px 16px',
  borderRadius: 6,
  border: '1px solid var(--border, #475569)',
  background: 'var(--accent, #38bdf8)',
  color: '#000',
  fontWeight: 600,
  fontSize: 13,
  cursor: 'pointer',
};
