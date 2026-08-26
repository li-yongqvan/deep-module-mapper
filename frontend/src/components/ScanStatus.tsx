/**
 * Scan status banner: reflects every state of the useScanJob state machine
 * (idle / scanning / done / empty / error / jobLost / networkError / timeout).
 */
import type { CSSProperties } from 'react';
import type { ScanState } from '../hooks/useScanJob';

interface ScanStatusProps {
  state: ScanState;
  onCancel: () => void;
  onRescan: () => void;
}

export default function ScanStatus({ state, onCancel, onRescan }: ScanStatusProps) {
  switch (state.kind) {
    case 'idle':
      return <div style={hintStyle}>输入路径开始扫描</div>;
    case 'scanning':
      return (
        <div style={rowStyle}>
          <span>
            扫描中…（{state.status}）<button onClick={onCancel} style={linkButtonStyle}>放弃等待</button>
          </span>
        </div>
      );
    case 'done':
      return (
        <div style={rowStyle}>
          <span style={{ color: 'var(--good, #34d399)' }}>✓ 扫描完成</span>
        </div>
      );
    case 'empty':
      return (
        <div style={{ color: 'var(--mid, #fbbf24)' }}>
          未解析到模块（扫描结果为空）
        </div>
      );
    case 'error':
      return (
        <div style={{ color: 'var(--warn, #f87171)' }} title={state.details}>
          ✗ 扫描失败：{state.error}
          {state.details ? `（${state.details}）` : ''}
        </div>
      );
    case 'jobLost':
      return (
        <div style={{ color: 'var(--mid, #fbbf24)' }}>
          任务丢失（后端可能已重启），请重新扫描
          <button onClick={onRescan} style={linkButtonStyle}>重新扫描</button>
        </div>
      );
    case 'networkError':
      return (
        <div style={{ color: 'var(--warn, #f87171)' }}>
          ✗ 网络错误：{state.message}
          <button onClick={onRescan} style={linkButtonStyle}>重试</button>
        </div>
      );
    case 'timeout':
      return (
        <div style={{ color: 'var(--mid, #fbbf24)' }}>
          扫描超时（60 秒），请重试或扫描较小的目录
          <button onClick={onRescan} style={linkButtonStyle}>重新扫描</button>
        </div>
      );
  }
}

const hintStyle: CSSProperties = { color: 'var(--text-2, #94a3b8)', fontSize: 13 };
const rowStyle: CSSProperties = { fontSize: 13 };
const linkButtonStyle: CSSProperties = {
  marginLeft: 8,
  background: 'none',
  border: 'none',
  color: 'var(--accent, #38bdf8)',
  cursor: 'pointer',
  textDecoration: 'underline',
  fontSize: 13,
};
